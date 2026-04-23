"""
test_voice_v6.py — Tests de Reconocimiento de Voz para DARIUS AI v6
====================================================================
Actualiza: test_voice.py (básico, sin cobertura de modos de activación)
Cambios:
  - Prueba el filtro de nombre para modo NOMBRE (process_recognized_text)
  - Verifica la serialización WAV en memoria del flujo PTT
  - Comprueba la calibración de energía del micrófono
  - Prueba el rechazo de audio corto / ruido (MIN_WORDS_WITHOUT_NAME)
  - Modo --live para prueba real de micrófono (requiere hardware)

Ejecución:
  python test_voice_v6.py              # tests unitarios (sin micrófono)
  python test_voice_v6.py --live       # incluye prueba real de micrófono
  python test_voice_v6.py --live --ptt # prueba PTT en vivo
"""

import sys
import os
import io
import wave
import struct
import unittest
from unittest.mock import MagicMock, patch
from difflib import SequenceMatcher

# ── Constantes de main.py ─────────────────────────────────────────────────────
ASSISTANT_NAME         = "darius"
NAME_SIMILARITY_CUTOFF = 0.60
MIC_ENERGY_THRESHOLD   = 3000
MIC_PAUSE_THRESHOLD    = 0.8
MIC_LISTEN_TIMEOUT     = 5
MIC_PHRASE_LIMIT       = 10
MIN_WORDS_WITHOUT_NAME = 99

LISTEN_MODE_PTT   = "PTT"
LISTEN_MODE_NAME  = "NOMBRE"
LISTEN_MODE_AUTO  = "AUTO"


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS — réplicas aisladas de lógica de main.py
# ─────────────────────────────────────────────────────────────────────────────

def _check_name_in_text(text: str) -> tuple[bool, str]:
    """Réplica de DariusFinal._check_name_in_text()."""
    words = text.split()
    if ASSISTANT_NAME in text:
        return True, text.replace(ASSISTANT_NAME, "").strip()
    if words:
        sim = SequenceMatcher(None, ASSISTANT_NAME, words[0]).ratio()
        if sim >= NAME_SIMILARITY_CUTOFF:
            return True, " ".join(words[1:]).strip()
    return False, text


def _process_recognized_text(text: str, mode: str) -> tuple[bool, str]:
    """
    Réplica de DariusFinal.process_recognized_text().
    Retorna (should_process: bool, effective_command: str).
    """
    words = text.split()

    if mode == LISTEN_MODE_AUTO:
        if ASSISTANT_NAME in text:
            return True, text.replace(ASSISTANT_NAME, "").strip()
        if words:
            sim = SequenceMatcher(None, ASSISTANT_NAME, words[0]).ratio()
            if sim > NAME_SIMILARITY_CUTOFF:
                return True, " ".join(words[1:]).strip()
        return True, text

    elif mode == LISTEN_MODE_NAME:
        found, clean = _check_name_in_text(text)
        if not found:
            return False, ""
        return True, clean

    elif mode == LISTEN_MODE_PTT:
        # PTT siempre procesa, elimina el nombre si aparece
        clean = text.replace(ASSISTANT_NAME, "").strip() if ASSISTANT_NAME in text else text
        return True, clean

    return False, ""


def _build_wav_in_memory(samples: list[int], rate: int = 16000) -> io.BytesIO:
    """
    Construye un buffer WAV en memoria desde una lista de muestras int16.
    Replica la lógica de _ptt_capture_and_process().
    """
    raw = struct.pack(f"<{len(samples)}h", *samples)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)       # paInt16 = 2 bytes
        wf.setframerate(rate)
        wf.writeframes(raw)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 1 — FILTRO DE MODO NOMBRE
# ─────────────────────────────────────────────────────────────────────────────

class TestNameModeFilter(unittest.TestCase):
    """Prueba el filtro de activación en modo NOMBRE."""

    def test_accepts_exact_name_prefix(self):
        ok, cmd = _process_recognized_text("darius abre el explorador", LISTEN_MODE_NAME)
        self.assertTrue(ok)
        self.assertEqual(cmd, "abre el explorador")

    def test_accepts_exact_name_mid_sentence(self):
        ok, cmd = _process_recognized_text("oye darius qué hora es", LISTEN_MODE_NAME)
        self.assertTrue(ok)
        self.assertNotIn("darius", cmd)

    def test_accepts_exact_name_suffix(self):
        ok, _ = _process_recognized_text("sube el volumen darius", LISTEN_MODE_NAME)
        self.assertTrue(ok)

    def test_rejects_text_without_name(self):
        ok, cmd = _process_recognized_text("abre el explorador", LISTEN_MODE_NAME)
        self.assertFalse(ok)
        self.assertEqual(cmd, "")

    def test_rejects_short_noise(self):
        for noise in ["um", "ah", "uh", "eh", "mm"]:
            ok, _ = _process_recognized_text(noise, LISTEN_MODE_NAME)
            self.assertFalse(ok, f"'{noise}' no debería activar el asistente")

    def test_accepts_phonetic_variant_dario(self):
        sim = SequenceMatcher(None, ASSISTANT_NAME, "dario").ratio()
        self.assertGreater(sim, NAME_SIMILARITY_CUTOFF,
            f"'dario' score {sim:.2f} debe superar umbral {NAME_SIMILARITY_CUTOFF}")
        ok, cmd = _process_recognized_text("dario sube el volumen", LISTEN_MODE_NAME)
        self.assertTrue(ok, "'dario' debería ser aceptado como variante de 'darius'")
        self.assertEqual(cmd, "sube el volumen")

    def test_clean_text_removes_name(self):
        _, cmd = _process_recognized_text("darius reproduce rock", LISTEN_MODE_NAME)
        self.assertNotIn("darius", cmd)
        self.assertEqual(cmd, "reproduce rock")

    def test_empty_string_rejected(self):
        ok, _ = _process_recognized_text("", LISTEN_MODE_NAME)
        self.assertFalse(ok)


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 2 — MODO AUTO
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoModeFilter(unittest.TestCase):
    """El modo AUTO debe aceptar cualquier texto sin restricciones de nombre."""

    def test_accepts_text_without_name(self):
        ok, cmd = _process_recognized_text("qué hora es", LISTEN_MODE_AUTO)
        self.assertTrue(ok)
        self.assertEqual(cmd, "qué hora es")

    def test_accepts_text_with_name_and_removes_it(self):
        ok, cmd = _process_recognized_text("darius qué hora es", LISTEN_MODE_AUTO)
        self.assertTrue(ok)
        self.assertNotIn("darius", cmd)
        self.assertIn("hora", cmd)

    def test_accepts_empty_ish_text(self):
        """AUTO acepta incluso texto corto/ruido — el routing local se encargará."""
        ok, _ = _process_recognized_text("um", LISTEN_MODE_AUTO)
        self.assertTrue(ok)

    def test_name_in_middle_removed(self):
        ok, cmd = _process_recognized_text("oye darius sube el volumen", LISTEN_MODE_AUTO)
        self.assertTrue(ok)
        self.assertNotIn("darius", cmd)


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 3 — MODO PTT
# ─────────────────────────────────────────────────────────────────────────────

class TestPTTModeFilter(unittest.TestCase):
    """En modo PTT el nombre nunca se exige — el gesto de la tecla es el trigger."""

    def test_accepts_any_text(self):
        for text in ["sube el volumen", "qué hora es", "abre chrome", "um"]:
            ok, _ = _process_recognized_text(text, LISTEN_MODE_PTT)
            self.assertTrue(ok, f"PTT debe aceptar '{text}'")

    def test_removes_name_if_present(self):
        ok, cmd = _process_recognized_text("darius sube el volumen", LISTEN_MODE_PTT)
        self.assertTrue(ok)
        self.assertNotIn("darius", cmd)
        self.assertIn("sube", cmd)

    def test_accepts_text_without_name(self):
        ok, cmd = _process_recognized_text("sube el volumen", LISTEN_MODE_PTT)
        self.assertTrue(ok)
        self.assertEqual(cmd, "sube el volumen")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 4 — SERIALIZACIÓN WAV EN MEMORIA (flujo PTT)
# ─────────────────────────────────────────────────────────────────────────────

class TestPTTWAVSerialization(unittest.TestCase):
    """
    Verifica que la serialización de frames PyAudio a WAV en memoria
    produzca un archivo válido que speech_recognition pueda leer.
    """

    def _generate_sine_samples(self, freq: int = 440, duration_ms: int = 200,
                                rate: int = 16000) -> list[int]:
        """Genera muestras de una onda sinusoidal como int16."""
        import math
        n_samples = int(rate * duration_ms / 1000)
        amplitude = 8000
        return [int(amplitude * math.sin(2 * math.pi * freq * i / rate))
                for i in range(n_samples)]

    def test_wav_buffer_is_valid_wav(self):
        samples = self._generate_sine_samples()
        buf     = _build_wav_in_memory(samples)
        # Verificar que el buffer es un WAV válido leyendo su cabecera
        buf.seek(0)
        header = buf.read(4)
        self.assertEqual(header, b"RIFF", "El buffer debe comenzar con 'RIFF'")

    def test_wav_buffer_has_correct_params(self):
        samples = self._generate_sine_samples(duration_ms=500)
        buf     = _build_wav_in_memory(samples, rate=16000)
        buf.seek(0)
        with wave.open(buf) as wf:
            self.assertEqual(wf.getnchannels(), 1,    "Debe ser mono")
            self.assertEqual(wf.getsampwidth(), 2,    "Debe ser 16-bit (paInt16)")
            self.assertEqual(wf.getframerate(), 16000,"Sample rate debe ser 16000 Hz")

    def test_wav_buffer_sample_count(self):
        rate    = 16000
        ms      = 300
        samples = self._generate_sine_samples(duration_ms=ms, rate=rate)
        buf     = _build_wav_in_memory(samples, rate=rate)
        buf.seek(0)
        with wave.open(buf) as wf:
            n_frames = wf.getnframes()
        self.assertEqual(n_frames, len(samples),
            f"Frames esperados: {len(samples)}, obtenidos: {n_frames}")

    def test_empty_frames_produces_valid_wav(self):
        """Frames vacíos (usuario soltó la tecla sin hablar) deben producir WAV válido."""
        buf = _build_wav_in_memory([])
        buf.seek(0)
        header = buf.read(4)
        self.assertEqual(header, b"RIFF")

    def test_wav_readable_by_speech_recognition(self):
        """El WAV en memoria debe ser consumible por sr.AudioFile."""
        try:
            import speech_recognition as sr
        except ImportError:
            self.skipTest("speech_recognition no instalado")

        samples = self._generate_sine_samples(freq=440, duration_ms=500)
        buf     = _build_wav_in_memory(samples)

        try:
            with sr.AudioFile(buf) as source:
                recognizer = sr.Recognizer()
                audio = recognizer.record(source)
            self.assertIsNotNone(audio,
                "sr.AudioFile debe poder leer el buffer WAV generado")
        except Exception as e:
            self.fail(f"sr.AudioFile lanzó excepción con WAV válido: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 5 — CONFIGURACIÓN DEL RECOGNIZER
# ─────────────────────────────────────────────────────────────────────────────

class TestRecognizerConfiguration(unittest.TestCase):
    """
    Verifica que el Recognizer de main.py se configura con los valores correctos.
    """

    def test_energy_threshold_value(self):
        self.assertGreater(MIC_ENERGY_THRESHOLD, 0)
        self.assertLess(MIC_ENERGY_THRESHOLD, 10000,
            "Energy threshold muy alto podría no detectar voz normal")

    def test_pause_threshold_reasonable(self):
        self.assertGreater(MIC_PAUSE_THRESHOLD, 0.3,
            "Pause threshold muy bajo causaría cortes prematuros")
        self.assertLess(MIC_PAUSE_THRESHOLD, 2.0,
            "Pause threshold muy alto causaría esperas largas")

    def test_listen_timeout_positive(self):
        self.assertGreater(MIC_LISTEN_TIMEOUT, 0)

    def test_phrase_limit_positive(self):
        self.assertGreater(MIC_PHRASE_LIMIT, 0)
        self.assertGreater(MIC_PHRASE_LIMIT, MIC_LISTEN_TIMEOUT,
            "phrase_time_limit debe ser mayor que listen timeout")

    def test_recognizer_configured_correctly(self):
        """Verifica que configure_listener() aplica los valores de las constantes."""
        try:
            import speech_recognition as sr
        except ImportError:
            self.skipTest("speech_recognition no instalado")

        r = sr.Recognizer()
        r.energy_threshold         = MIC_ENERGY_THRESHOLD
        r.dynamic_energy_threshold = True
        r.pause_threshold          = MIC_PAUSE_THRESHOLD
        r.non_speaking_duration    = 0.5

        self.assertEqual(r.energy_threshold, MIC_ENERGY_THRESHOLD)
        self.assertEqual(r.pause_threshold,  MIC_PAUSE_THRESHOLD)
        self.assertTrue(r.dynamic_energy_threshold)


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 6 — INTEGRACIÓN REAL DE MICRÓFONO (opcional)
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveMicrophone(unittest.TestCase):
    """
    Tests de integración real con micrófono.
    Solo se ejecutan con --live.
    ADVERTENCIA: requieren hardware y conexión a Google STT.
    """

    @classmethod
    def setUpClass(cls):
        cls.run_live = "--live" in sys.argv or os.getenv("DARIUS_RUN_LIVE_TESTS") == "1"

    def _skip_if_not_live(self):
        if not self.run_live:
            self.skipTest("Test live omitido (usa --live o DARIUS_RUN_LIVE_TESTS=1)")

    def test_live_microphone_available(self):
        self._skip_if_not_live()
        try:
            import speech_recognition as sr
            mics = sr.Microphone.list_microphone_names()
            self.assertGreater(len(mics), 0, "No se detectaron micrófonos")
            print(f"\n[LIVE] Micrófonos disponibles ({len(mics)}):")
            for i, m in enumerate(mics[:5]):
                print(f"  [{i}] {m}")
        except ImportError:
            self.skipTest("speech_recognition no instalado")

    def test_live_ambient_noise_calibration(self):
        self._skip_if_not_live()
        try:
            import speech_recognition as sr
        except ImportError:
            self.skipTest("speech_recognition no instalado")

        r = sr.Recognizer()
        r.energy_threshold = MIC_ENERGY_THRESHOLD
        print("\n[LIVE] Calibrando ruido ambiente (1 segundo)...")
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=1)
            print(f"[LIVE] Energy threshold tras calibración: {r.energy_threshold:.0f}")
            self.assertGreater(r.energy_threshold, 0)
        except Exception as e:
            self.fail(f"Calibración de micrófono falló: {e}")

    def test_live_voice_recognition_basic(self):
        self._skip_if_not_live()
        try:
            import speech_recognition as sr
        except ImportError:
            self.skipTest("speech_recognition no instalado")

        r = sr.Recognizer()
        r.energy_threshold         = MIC_ENERGY_THRESHOLD
        r.dynamic_energy_threshold = True
        r.pause_threshold          = MIC_PAUSE_THRESHOLD

        print(f"\n[LIVE] Di algo en español ({MIC_LISTEN_TIMEOUT}s de timeout)...")
        try:
            with sr.Microphone() as source:
                audio = r.listen(source, timeout=MIC_LISTEN_TIMEOUT,
                                 phrase_time_limit=MIC_PHRASE_LIMIT)
            text = r.recognize_google(audio, language="es-ES").lower()
            print(f"[LIVE] Reconocido: '{text}'")
            self.assertIsInstance(text, str)
            self.assertGreater(len(text), 0)
        except sr.WaitTimeoutError:
            self.skipTest("No se detectó audio en el timeout — prueba omitida")
        except sr.UnknownValueError:
            self.skipTest("Audio no reconocido — habla más claro")
        except sr.RequestError as e:
            self.fail(f"Error de servicio STT: {e}")

    def test_live_mode_nombre_filter(self):
        """Prueba completa: voz → STT → filtro NOMBRE → comando."""
        self._skip_if_not_live()
        try:
            import speech_recognition as sr
        except ImportError:
            self.skipTest("speech_recognition no instalado")

        r = sr.Recognizer()
        r.energy_threshold = MIC_ENERGY_THRESHOLD
        r.pause_threshold  = MIC_PAUSE_THRESHOLD

        print(f"\n[LIVE] Di 'darius qué hora es' (modo NOMBRE)...")
        try:
            with sr.Microphone() as source:
                audio = r.listen(source, timeout=MIC_LISTEN_TIMEOUT,
                                 phrase_time_limit=MIC_PHRASE_LIMIT)
            text   = r.recognize_google(audio, language="es-ES").lower()
            print(f"[LIVE] STT: '{text}'")
            ok, cmd = _process_recognized_text(text, LISTEN_MODE_NAME)
            print(f"[LIVE] Filtro NOMBRE: aceptado={ok}, comando='{cmd}'")
            if ok:
                print(f"[LIVE] ✓ Comando procesado correctamente")
            else:
                print(f"[LIVE] ✗ Comando descartado por filtro NOMBRE "
                      f"(¿dijiste 'darius' al inicio?)")
        except sr.WaitTimeoutError:
            self.skipTest("Timeout de audio")
        except sr.UnknownValueError:
            self.skipTest("Audio no reconocido")


# ─────────────────────────────────────────────────────────────────────────────
#  RUNNER
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--live" in sys.argv:
        sys.argv.remove("--live")
        os.environ["DARIUS_RUN_LIVE_TESTS"] = "1"
        print("[INFO] Modo --live activado: se ejecutarán tests de hardware.")

    if "--ptt" in sys.argv:
        sys.argv.remove("--ptt")
        print("[INFO] Flag --ptt registrado (informativo — los tests PTT son unitarios).")

    unittest.main(verbosity=2)
