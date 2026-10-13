"""
test_sound_effects.py — Pruebas unitarias para el motor de efectos de sonido procedurales
"""

from unittest.mock import patch

import numpy as np
import pytest

from src.darius_ai.audio.sound_effects import (
    ProceduralSFX,
    generate_tone_wave,
    get_sfx_engine,
)


class TestWaveGeneration:
    def test_sine_wave_shape_and_range(self):
        duration = 0.1
        sample_rate = 44100
        wave = generate_tone_wave(freq=440.0, duration=duration, wave_type="sine", sample_rate=sample_rate)
        expected_samples = int(duration * sample_rate)
        assert len(wave) == expected_samples
        assert isinstance(wave, np.ndarray)
        assert wave.dtype == np.float32
        assert np.max(wave) <= 1.0
        assert np.min(wave) >= -1.0

    def test_square_wave_generation(self):
        wave = generate_tone_wave(freq=1000.0, duration=0.05, wave_type="square")
        assert len(wave) > 0
        assert np.max(wave) <= 1.0
        assert np.min(wave) >= -1.0

    def test_triangle_wave_generation(self):
        wave = generate_tone_wave(freq=440.0, duration=0.05, wave_type="triangle")
        assert len(wave) > 0
        assert np.max(wave) <= 1.0
        assert np.min(wave) >= -1.0

    def test_envelope_prevents_clicks_at_boundaries(self):
        wave = generate_tone_wave(freq=440.0, duration=0.1, wave_type="sine")
        # El inicio y el final deben converger hacia 0 gracias a la envolvente
        assert abs(wave[0]) < 0.05
        assert abs(wave[-1]) < 0.05


class TestProceduralSFXEngine:
    @pytest.fixture
    def sfx(self):
        return ProceduralSFX(enabled=True, volume=0.5)

    def test_toggle_enabled(self, sfx):
        assert sfx.is_enabled() is True
        sfx.set_enabled(False)
        assert sfx.is_enabled() is False

    def test_volume_clamping(self, sfx):
        sfx.set_volume(1.5)
        assert sfx.volume == 1.0
        sfx.set_volume(-0.5)
        assert sfx.volume == 0.0
        sfx.set_volume(0.8)
        assert sfx.volume == 0.8

    @patch("src.darius_ai.audio.sound_effects.sounddevice.play")
    def test_target_lock_plays_tones(self, mock_play, sfx):
        sfx.play_target_lock(blocking=True)
        assert mock_play.called

    @patch("src.darius_ai.audio.sound_effects.sounddevice.play")
    def test_success_chime_plays_arpeggio(self, mock_play, sfx):
        sfx.play_success_chime(blocking=True)
        assert mock_play.call_count >= 1

    @patch("src.darius_ai.audio.sound_effects.sounddevice.play")
    def test_scan_pulse_plays(self, mock_play, sfx):
        sfx.play_scan_pulse(blocking=True)
        assert mock_play.called

    @patch("src.darius_ai.audio.sound_effects.sounddevice.play")
    def test_earcon_tick_plays(self, mock_play, sfx):
        sfx.play_earcon_tick(blocking=True)
        assert mock_play.called

    @patch("src.darius_ai.audio.sound_effects.sounddevice.play")
    def test_sonar_ping_plays(self, mock_play, sfx):
        sfx.play_sonar_ping(blocking=True)
        assert mock_play.called

    @patch("src.darius_ai.audio.sound_effects.sounddevice.play")
    def test_disabled_sfx_does_not_play(self, mock_play, sfx):
        sfx.set_enabled(False)
        sfx.play_scan_pulse(blocking=True)
        assert not mock_play.called

    @patch("src.darius_ai.audio.sound_effects.sounddevice.play", side_effect=Exception("Audio device error"))
    def test_graceful_handling_on_audio_failure(self, mock_play, sfx):
        # No debe lanzar excepción aunque el hardware de audio falle
        sfx.play_target_lock(blocking=True)


class TestSingletonAccessor:
    def test_get_sfx_engine_returns_singleton(self):
        engine1 = get_sfx_engine()
        engine2 = get_sfx_engine()
        assert engine1 is engine2
        assert isinstance(engine1, ProceduralSFX)
