"""
acoustic_trigger.py — Detector Acústico de Doble Aplauso y Calibración de Micrófono
===================================================================================
Escucha el micrófono en tiempo real y detecta transitorios acústicos rápidos
(como un doble aplauso) utilizando adaptación continua del suelo de ruido.

Permite activar rutinas automatizadas ("Protocolo Darius") o despertar al asistente
sin necesidad de comandos de teclado.

Incluye sondeo y auto-selección inteligente de micrófono para evitar bloqueos
en caso de micrófonos mudos o desconectados.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import numpy as np

log = logging.getLogger("DARIUS.AcousticTrigger")

# Parámetros acústicos calibrados para manos humanas y prevención de ecos
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_BLOCK_MS = 40
DEFAULT_SPIKE_RATIO = 8.5
DEFAULT_COOLDOWN_S = 2.0
DEFAULT_MIN_DOUBLE_GAP_S = 0.14
DEFAULT_MAX_DOUBLE_GAP_S = 0.65
DEFAULT_RETRIGGER_RATIO = 0.50
DEFAULT_NOISE_FLOOR_ALPHA = 0.992
DEFAULT_MIN_RMS = 0.025
QUIET_GATE_MULT = 2.2
INPUT_PROBE_S = 0.4
INPUT_SILENT_RMS = 0.001


def rms_mono(block: np.ndarray) -> float:
    """Calcula el valor eficaz (RMS) de un bloque de audio."""
    block = np.mean(block.astype(np.float64), axis=1) if block.ndim > 1 else block.astype(np.float64)
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(block**2)))


def get_input_devices() -> list[tuple[int, dict]]:
    """Retorna la lista de dispositivos de audio de entrada disponibles."""
    try:
        import sounddevice as sd

        return [
            (i, dev)
            for i, dev in enumerate(sd.query_devices())
            if dev.get("max_input_channels", 0) >= 1
        ]
    except Exception as exc:
        log.warning(f"Error consultando dispositivos de audio: {exc}")
        return []


def resolve_input_device_index(spec: str) -> int:
    """Resuelve un identificador de micrófono a partir de su índice o subcadena de nombre."""
    spec = spec.strip()
    try:
        import sounddevice as sd
    except ImportError:
        return 0

    if spec.isdigit():
        idx = int(spec)
        sd.query_devices(idx)
        return idx

    needle = spec.lower()
    for idx, dev in get_input_devices():
        if needle in dev.get("name", "").lower():
            return idx
    raise ValueError(f"No se encontró ningún micrófono que coincida con: '{spec}'")


def probe_device_max_rms(
    device_index: int,
    blocksize: int,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    probe_s: float = INPUT_PROBE_S,
) -> float | None:
    """Sondea un dispositivo durante un breve lapso para medir su nivel pico de RMS."""
    try:
        import sounddevice as sd

        with sd.InputStream(
            device=device_index,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=blocksize,
        ) as stream:
            peak = 0.0
            deadline = time.monotonic() + probe_s
            while time.monotonic() < deadline:
                data, _ = stream.read(blocksize)
                peak = max(peak, rms_mono(data))
            return peak
    except Exception as exc:
        log.debug(f"Sondeo de micrófono [{device_index}] falló: {exc}")
        return None


def auto_select_best_mic(
    device_override: str = "",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    block_ms: int = DEFAULT_BLOCK_MS,
) -> int | None:
    """
    Selecciona el mejor micrófono funcional.
    Si el dispositivo configurado o predeterminado está en silencio,
    escanea los demás y elige el de mayor señal activa.
    """
    try:
        import sounddevice as sd
    except ImportError:
        log.warning("sounddevice no disponible para auto-selección de micrófono.")
        return None

    blocksize = max(int(sample_rate * block_ms / 1000), 1)

    # 1. Override explícito por configuración
    if device_override.strip():
        try:
            idx = resolve_input_device_index(device_override)
            name = sd.query_devices(idx).get("name", f"Dispositivo {idx}")
            peak = probe_device_max_rms(idx, blocksize, sample_rate)
            log.info(f"Usando micrófono configurado [{idx}]: {name} (rms={peak})")
            return idx
        except Exception as e:
            log.warning(f"Error resolviendo micrófono configurado '{device_override}': {e}")

    # 2. Comprobar micrófono predeterminado de Windows
    default_dev = sd.default.device[0] if sd.default.device else None
    if default_dev is not None and default_dev >= 0:
        default_name = sd.query_devices(default_dev).get("name", "Default")
        peak = probe_device_max_rms(default_dev, blocksize, sample_rate)
        if peak is not None and peak >= INPUT_SILENT_RMS:
            log.info(f"Micrófono predeterminado OK [{default_dev}]: {default_name} (rms={peak:.5f})")
            return default_dev
        log.warning(
            f"Micrófono predeterminado [{default_dev}] {default_name} parece mudo (rms={peak}); "
            "escaneando otros dispositivos..."
        )

    # 3. Escanear y buscar el micrófono con mayor actividad acústica
    best_idx: int | None = None
    best_peak = -1.0
    for idx, _dev in get_input_devices():
        if default_dev is not None and idx == default_dev:
            continue
        peak = probe_device_max_rms(idx, blocksize, sample_rate)
        if peak is not None and peak > best_peak:
            best_peak = peak
            best_idx = idx

    if best_idx is not None and best_peak >= INPUT_SILENT_RMS:
        best_name = sd.query_devices(best_idx).get("name", f"Dispositivo {best_idx}")
        log.info(f"Auto-seleccionado micrófono activo [{best_idx}]: {best_name} (rms={best_peak:.5f})")
        return best_idx

    # Fallback al default
    return default_dev if default_dev is not None and default_dev >= 0 else 0


class AcousticDoubleClapDetector:
    """
    Detector en segundo plano de doble aplauso acústico con adaptación dinámica.
    """

    def __init__(
        self,
        on_trigger: Callable[[], None] | None = None,
        spike_ratio: float = DEFAULT_SPIKE_RATIO,
        cooldown_s: float = DEFAULT_COOLDOWN_S,
        min_double_gap_s: float = DEFAULT_MIN_DOUBLE_GAP_S,
        max_double_gap_s: float = DEFAULT_MAX_DOUBLE_GAP_S,
        device_spec: str = "",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        block_ms: int = DEFAULT_BLOCK_MS,
        is_speaking_fn: Callable[[], bool] | None = None,
    ):
        self.on_trigger = on_trigger
        self.spike_ratio = spike_ratio
        self.cooldown_s = cooldown_s
        self.min_double_gap_s = min_double_gap_s
        self.max_double_gap_s = max_double_gap_s
        self.device_spec = device_spec
        self.sample_rate = sample_rate
        self.block_ms = block_ms
        self.is_speaking_fn = is_speaking_fn

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Inicia el detector en un hilo desacoplado."""
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="acoustic-clap")
            self._thread.start()
            return True

    def stop(self):
        """Detiene el detector."""
        with self._lock:
            self._running = False

    def is_running(self) -> bool:
        return self._running

    def _listen_loop(self):
        try:
            import sounddevice as sd
        except ImportError:
            log.warning("sounddevice no disponible. Detección de aplausos desactivada.")
            self._running = False
            return

        blocksize = max(int(self.sample_rate * self.block_ms / 1000), 1)
        input_idx = auto_select_best_mic(self.device_spec, self.sample_rate, self.block_ms)

        noise_floor = 1e-4
        last_logged_double = 0.0
        last_speaking_time = 0.0
        first_clap_time: float | None = None
        spike_armed = True

        log.info(
            f"[ClapDetector] Escuchando doble aplauso (rate={self.sample_rate}, "
            f"ratio={self.spike_ratio}, gap={self.min_double_gap_s}-{self.max_double_gap_s}s)"
        )

        try:
            with sd.InputStream(
                device=input_idx,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
            ) as stream:
                while self._running:
                    data, overflowed = stream.read(blocksize)
                    if overflowed:
                        continue

                    now = time.monotonic()

                    # Supresión de eco acústico: si el asistente está hablando por los altavoces
                    # o terminó de hablar hace menos de 1.8 segundos, ignorar audio para evitar bucles.
                    if self.is_speaking_fn and self.is_speaking_fn():
                        last_speaking_time = now
                        first_clap_time = None
                        spike_armed = False
                        continue

                    if (now - last_speaking_time) < 1.8:
                        first_clap_time = None
                        spike_armed = False
                        continue

                    level = rms_mono(data)

                    # Adaptar el piso de ruido si el nivel está por debajo de la puerta de silencio
                    quiet_gate = noise_floor * QUIET_GATE_MULT
                    if level < quiet_gate:
                        noise_floor = DEFAULT_NOISE_FLOOR_ALPHA * noise_floor + (
                            1.0 - DEFAULT_NOISE_FLOOR_ALPHA
                        ) * level
                        noise_floor = max(noise_floor, 1e-7)

                    threshold = max(noise_floor * self.spike_ratio, DEFAULT_MIN_RMS)
                    now = time.monotonic()
                    retrigger_level = threshold * DEFAULT_RETRIGGER_RATIO

                    if level < retrigger_level:
                        spike_armed = True

                    if (
                        spike_armed
                        and level >= threshold
                        and (now - last_logged_double) >= self.cooldown_s
                    ):
                        spike_armed = False
                        if first_clap_time is None:
                            first_clap_time = now
                        else:
                            gap = now - first_clap_time
                            if gap < self.min_double_gap_s:
                                pass
                            elif gap <= self.max_double_gap_s:
                                first_clap_time = None
                                last_logged_double = now
                                log.info(
                                    f"👏 [ClapDetector] ¡Doble aplauso detectado! "
                                    f"(gap={gap:.3f}s, rms={level:.5f}, piso={noise_floor:.5f})"
                                )
                                if self.on_trigger:
                                    threading.Thread(
                                        target=self.on_trigger,
                                        daemon=True,
                                        name="clap-trigger-action",
                                    ).start()
                            else:
                                first_clap_time = now

        except Exception as e:
            log.error(f"[ClapDetector] Error en stream de audio: {e}")
        finally:
            self._running = False
