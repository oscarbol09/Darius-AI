"""
sound_effects.py — Motor de Efectos de Sonido Procedurales en Memoria para DARIUS AI
=====================================================================================
Genera efectos de audio tácticos y de interfaz directamente mediante síntesis matemática
de ondas (senoidales, cuadradas, triangulares) con envolvente exponencial anti-clipping.
Implementado mediante el motor de síntesis matemática procedural de Darius AI.

Ventajas:
  1. Cero archivos de audio (.wav/.mp3) en disco (0 KB de footprint).
  2. Latencia ultra-baja (<5 ms) en memoria con NumPy y sounddevice.
  3. Ejecución no bloqueante en hilos de fondo desacoplados.
  4. Fallback transparente a winsound.Beep o degradación silenciosa si no hay hardware de audio.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Literal

import numpy as np

log = logging.getLogger("DARIUS.SFX")

WaveType = Literal["sine", "square", "triangle"]

_SOUNDDEVICE_AVAILABLE = False
try:
    import sounddevice

    _SOUNDDEVICE_AVAILABLE = True
except ImportError:
    sounddevice = None  # type: ignore
    _SOUNDDEVICE_AVAILABLE = False

_WINSOUND_AVAILABLE = False
try:
    import winsound

    _WINSOUND_AVAILABLE = True
except ImportError:
    winsound = None  # type: ignore
    _WINSOUND_AVAILABLE = False


def generate_tone_wave(
    freq: float,
    duration: float,
    wave_type: WaveType = "sine",
    sample_rate: int = 44100,
    gain: float = 0.25,
) -> np.ndarray:
    """
    Genera una forma de onda normalizada en NumPy con envolvente suave (Attack-Decay)
    para evitar chasquidos acústicos en los bordes.
    """
    total_samples = max(1, int(sample_rate * duration))
    t = np.linspace(0, duration, total_samples, endpoint=False, dtype=np.float32)

    # 1. Generación de la onda pura según tipo
    if wave_type == "sine":
        wave = np.sin(2.0 * np.pi * freq * t, dtype=np.float32)
    elif wave_type == "square":
        wave = np.sign(np.sin(2.0 * np.pi * freq * t, dtype=np.float32))
    elif wave_type == "triangle":
        # Forma triangular: 2/pi * arcsin(sin(2*pi*f*t))
        wave = (2.0 / np.pi) * np.arcsin(np.sin(2.0 * np.pi * freq * t, dtype=np.float32))
    else:
        wave = np.sin(2.0 * np.pi * freq * t, dtype=np.float32)

    # 2. Envolvente suave exponencial (10% ataque, 90% decaimiento)
    attack_samples = max(1, int(total_samples * 0.10))
    decay_samples = total_samples - attack_samples

    attack_env = np.linspace(0.0, 1.0, attack_samples, dtype=np.float32)
    decay_env = np.exp(np.linspace(0.0, -3.5, decay_samples, dtype=np.float32))

    envelope = np.concatenate([attack_env, decay_env])
    if len(envelope) > total_samples:
        envelope = envelope[:total_samples]
    elif len(envelope) < total_samples:
        envelope = np.pad(envelope, (0, total_samples - len(envelope)), mode="edge")

    processed_wave = (wave * envelope * gain).astype(np.float32)
    # Limitar rigurosamente en rango [-1.0, 1.0]
    return np.clip(processed_wave, -1.0, 1.0)


class ProceduralSFX:
    """
    Motor central de efectos de sonido procedurales para la interfaz de Darius.
    """

    def __init__(self, enabled: bool = True, volume: float = 0.6, sample_rate: int = 44100):
        self._enabled = enabled
        self._volume = max(0.0, min(1.0, volume))
        self._sample_rate = sample_rate
        self._lock = threading.Lock()

    @property
    def volume(self) -> float:
        return self._volume

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def _play_buffer(self, samples: np.ndarray) -> None:
        """Envía el buffer de audio a sounddevice o fallback."""
        if not self._enabled or len(samples) == 0:
            return

        effective_gain = self._volume
        amplified = np.clip(samples * effective_gain, -1.0, 1.0)

        if _SOUNDDEVICE_AVAILABLE and sounddevice is not None:
            try:
                sounddevice.play(amplified, samplerate=self._sample_rate, blocking=True)
                return
            except Exception as e:
                log.debug(f"[SFX] sounddevice no disponible o falló: {e}")

        # Fallback para Windows en caso de fallo de sounddevice
        if _WINSOUND_AVAILABLE and winsound is not None:
            with contextlib.suppress(Exception):
                winsound.Beep(800, 80)

    def _run_async(self, target_func, *args, blocking: bool = False) -> None:
        """Ejecuta la función de sonido de forma no bloqueante o bloqueante."""
        if not self._enabled:
            return
        if blocking:
            try:
                target_func(*args)
            except Exception as e:
                log.debug(f"[SFX] Error al reproducir audio: {e}")
        else:
            threading.Thread(target=target_func, args=args, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  CATÁLOGO DE EFECTOS TÁCTICOS Y DE INTERFAZ
    # ─────────────────────────────────────────────────────────────────────────

    def play_target_lock(self, blocking: bool = False) -> None:
        """Tono doble ascendente (600 Hz -> 900 Hz) para fijación o confirmación."""
        def _exec():
            tone1 = generate_tone_wave(600.0, duration=0.10, wave_type="sine", gain=0.3)
            tone2 = generate_tone_wave(900.0, duration=0.14, wave_type="sine", gain=0.3)
            gap = np.zeros(int(self._sample_rate * 0.02), dtype=np.float32)
            full = np.concatenate([tone1, gap, tone2])
            self._play_buffer(full)

        self._run_async(_exec, blocking=blocking)

    def play_success_chime(self, blocking: bool = False) -> None:
        """Arpegio armónico C5 -> E5 -> G5 (523 Hz, 659 Hz, 784 Hz)."""
        def _exec():
            c5 = generate_tone_wave(523.25, duration=0.11, wave_type="sine", gain=0.25)
            e5 = generate_tone_wave(659.25, duration=0.11, wave_type="sine", gain=0.25)
            g5 = generate_tone_wave(783.99, duration=0.18, wave_type="sine", gain=0.25)
            gap = np.zeros(int(self._sample_rate * 0.015), dtype=np.float32)
            full = np.concatenate([c5, gap, e5, gap, g5])
            self._play_buffer(full)

        self._run_async(_exec, blocking=blocking)

    def play_scan_pulse(self, blocking: bool = False) -> None:
        """Pulso corto de radar/escaneo a 1200 Hz tipo onda cuadrada filtrada."""
        def _exec():
            pulse = generate_tone_wave(1200.0, duration=0.06, wave_type="square", gain=0.15)
            self._play_buffer(pulse)

        self._run_async(_exec, blocking=blocking)

    def play_alert_tone(self, blocking: bool = False) -> None:
        """Tono dual de advertencia o atención a 440 Hz / 880 Hz."""
        def _exec():
            t1 = generate_tone_wave(440.0, duration=0.12, wave_type="triangle", gain=0.28)
            t2 = generate_tone_wave(880.0, duration=0.15, wave_type="sine", gain=0.28)
            gap = np.zeros(int(self._sample_rate * 0.03), dtype=np.float32)
            full = np.concatenate([t1, gap, t2])
            self._play_buffer(full)

        self._run_async(_exec, blocking=blocking)

    def play_click_tone(self, blocking: bool = False) -> None:
        """Tono percusivo ultra-corto para respuesta táctil en botones."""
        def _exec():
            click = generate_tone_wave(900.0, duration=0.025, wave_type="triangle", gain=0.18)
            self._play_buffer(click)

        self._run_async(_exec, blocking=blocking)

    def play_earcon_tick(self, blocking: bool = False) -> None:
        """
        Pulso acústico discreto de doble tono (880 Hz -> 1320 Hz) para telemetría
        en segundo plano, integrado en la telemetría acústica de Darius AI.
        """
        def _exec():
            tick1 = generate_tone_wave(880.0, duration=0.05, wave_type="sine", gain=0.12)
            gap = np.zeros(int(self._sample_rate * 0.04), dtype=np.float32)
            tick2 = generate_tone_wave(1320.0, duration=0.06, wave_type="sine", gain=0.12)
            full = np.concatenate([tick1, gap, tick2])
            self._play_buffer(full)

        self._run_async(_exec, blocking=blocking)

    def play_sonar_ping(self, blocking: bool = False) -> None:
        """
        Ping de radar/sonar cibernético a 480 Hz con armónico sutil a 960 Hz y decaimiento
        para telemetría acústica de Darius AI.
        """
        def _exec():
            sub = generate_tone_wave(480.0, duration=0.35, wave_type="sine", gain=0.22)
            harmonic = generate_tone_wave(960.0, duration=0.25, wave_type="sine", gain=0.08)
            # Mezclar armónico al inicio
            pad_len = len(sub) - len(harmonic)
            if pad_len > 0:
                harmonic = np.pad(harmonic, (0, pad_len), mode="constant")
            full = sub + harmonic
            self._play_buffer(full)

        self._run_async(_exec, blocking=blocking)


# Instancia única Singleton
_GLOBAL_SFX: ProceduralSFX | None = None
_GLOBAL_SFX_LOCK = threading.Lock()


def get_sfx_engine() -> ProceduralSFX:
    """Retorna la instancia global del motor de efectos de sonido."""
    global _GLOBAL_SFX
    if _GLOBAL_SFX is None:
        with _GLOBAL_SFX_LOCK:
            if _GLOBAL_SFX is None:
                _GLOBAL_SFX = ProceduralSFX()
    return _GLOBAL_SFX
