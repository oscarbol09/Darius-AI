"""
test_windows_commands_actions.py — Hermetic tests for windows_commands dispatch & launch paths.
"""

from __future__ import annotations

import subprocess
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.darius_ai.system import windows_commands as wc


def test_run_action_python_workspace_and_core_commands(monkeypatch, tmp_path):
    mock_cfg = SimpleNamespace(
        workspace_song_uri="spotify:track:1",
        workspace_claude_url="https://claude.ai",
        workspace_monitor_claude=1,
        workspace_monitor_secondary=2,
        workspace_secondary_url="https://github.com",
        workspace_welcome_phrase="Bienvenido",
    )
    mock_digest = MagicMock()
    mock_digest.collect_metrics.return_value = {"tasks": 2}
    mock_digest.generate_spoken_narrative.return_value = "Resumen matutino"

    mock_profile_engine = MagicMock()
    mock_profile_engine.read_profile.return_value = {"nombre": ["Dario"], "vacio": []}

    mock_media = MagicMock()
    mock_media.play_pause.return_value = (True, "play_pause")
    mock_media.next_track.return_value = (True, "next")
    mock_media.prev_track.return_value = (True, "prev")
    mock_media.stop.return_value = (True, "stop")
    mock_media.volume_up.return_value = (True, "vol_up")
    mock_media.volume_down.return_value = (True, "vol_down")
    mock_media.toggle_mute.return_value = (True, "mute")
    mock_media.search_and_play_youtube.return_value = (True, "yt")

    mock_darius = MagicMock()
    mock_darius.run_diagnostic.return_value = {"cpu": 12}
    mock_darius.generate_vocal_briefing.return_value = "Darius OK"

    mock_news = MagicMock()
    mock_news.get_top_headlines.return_value = []
    mock_news.format_vocal_briefing.return_value = "Noticias OK"

    mock_lex = MagicMock()
    mock_lex.lookup.return_value = (True, {"word": "IA"}, [])
    mock_lex.format_vocal_definition.return_value = "Definición IA"

    mock_ocr = MagicMock()
    mock_ocr.ocr_screen_region.return_value = SimpleNamespace(text="Hola pantalla", word_count=2)

    mock_bio = MagicMock()
    mock_bio.verify_live_user.return_value = True
    mock_bio.get_biometric_greeting.return_value = "Bienvenido Dario"

    mock_timer_mgr = MagicMock()
    timer_obj = SimpleNamespace(id="t1")
    mock_timer_mgr.create_timer.return_value = timer_obj
    mock_timer_mgr.format_timer_speech.return_value = "Timer t1"
    mock_timer_mgr.list_active_timers.return_value = [timer_obj]

    mock_wol = MagicMock()
    mock_wol.dispatch_wake.return_value = (True, "WOL sent")

    mock_lockdown = MagicMock()
    mock_lockdown.trigger_tactical_silence.return_value = (True, "Silence")
    mock_lockdown.trigger_emergency_lockdown.return_value = (True, "Lockdown")

    mock_radar = MagicMock()
    iss = SimpleNamespace(altitude_km=420.0, latitude=10.0, longitude=20.0)
    mock_radar.get_iss_position.return_value = (True, iss, "fallback")
    mock_radar.format_vocal_telemetry.return_value = "ISS OK"

    mock_air = MagicMock()
    mock_air.scan_overhead.return_value = (True, [{"callsign": "A1"}], "clear")
    mock_air.format_vocal_radar.return_value = "Air OK"

    mock_seismic = MagicMock()
    mock_seismic.get_recent_earthquakes.return_value = (True, [{"mag": 5.0}], "calm")
    mock_seismic.format_vocal_alert.return_value = "Quake OK"

    mock_space = MagicMock()
    sw = SimpleNamespace(kp_index=3.0, storm_level="G0")
    mock_space.get_current_space_weather.return_value = (True, sw, "nominal")
    mock_space.format_vocal_briefing.return_value = "Space OK"

    mock_sfx = MagicMock()
    mock_live = MagicMock()
    mock_live.start_live_session.return_value = (True, "OK")
    mock_live.stop_live_session.return_value = (True, "OK")

    mock_ag = MagicMock()
    mock_ag.is_available.return_value = True

    mock_sentinel = MagicMock()
    mock_sentinel.start.return_value = True

    mock_dossier_eng = MagicMock()
    dossier_obj = MagicMock(target_name="Darius AI Core")
    dossier_obj.to_speech_summary.return_value = "Resumen dossier"
    mock_dossier_eng.synthesize_dossier.return_value = dossier_obj

    class InstantThread:
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    patches = [
        patch("src.darius_ai.core.config_loader.cfg", mock_cfg),
        patch("src.darius_ai.system.workspace_manager.run_darius_welcome_protocol"),
        patch("src.darius_ai.system.workspace_manager.run_dev_mode"),
        patch("src.darius_ai.system.workspace_manager.run_trading_mode"),
        patch("src.darius_ai.system.workspace_manager.focus_or_launch_cursor"),
        patch("src.darius_ai.system.workspace_manager.get_monitor_rects", return_value=[(0, 0, 1920, 1080)]),
        patch("src.darius_ai.core.daily_digest.DailyDigestEngine", return_value=mock_digest),
        patch("src.darius_ai.core.user_profile_engine.UserProfileEngine", return_value=mock_profile_engine),
        patch("src.darius_ai.system.media_controller.media_controller", mock_media),
        patch("src.darius_ai.core.darius_protocol.get_darius_engine", return_value=mock_darius),
        patch("src.darius_ai.core.darius_persona.DariusPersona.get_witty_retort", return_value="Chiste"),
        patch("src.darius_ai.core.news_sentinel.NewsSentinel", return_value=mock_news),
        patch("src.darius_ai.core.lexicon_oracle.LexiconOracle", return_value=mock_lex),
        patch("src.darius_ai.core.visual_intel_ocr.VisualIntelOCR", return_value=mock_ocr),
        patch("src.darius_ai.core.face_biometrics.get_face_biometrics_engine", return_value=mock_bio),
        patch("src.darius_ai.core.darius_timer.get_darius_timer_manager", return_value=mock_timer_mgr),
        patch("src.darius_ai.system.wol_dispatcher.get_wol_dispatcher", return_value=mock_wol),
        patch("src.darius_ai.core.darius_lockdown.get_darius_lockdown_engine", return_value=mock_lockdown),
        patch("src.darius_ai.core.orbital_radar.get_orbital_radar", return_value=mock_radar),
        patch("src.darius_ai.core.air_traffic_sentinel.get_air_traffic_sentinel", return_value=mock_air),
        patch("src.darius_ai.core.seismic_sensor.get_seismic_sensor", return_value=mock_seismic),
        patch("src.darius_ai.core.space_weather_oracle.get_space_weather_oracle", return_value=mock_space),
        patch("src.darius_ai.audio.sound_effects.get_sfx_engine", return_value=mock_sfx),
        patch("src.darius_ai.core.gemini_live_engine.get_gemini_live_engine", return_value=mock_live),
        patch("src.darius_ai.core.antigravity_bridge.get_antigravity_bridge", return_value=mock_ag),
        patch("src.darius_ai.core.webcam_sentinel.get_webcam_sentinel", return_value=mock_sentinel),
        patch("src.darius_ai.core.target_dossier.get_dossier_engine", return_value=mock_dossier_eng),
        patch("threading.Thread", InstantThread),
    ]
    with ExitStack() as stack:
        entered = [stack.enter_context(p) for p in patches]
        m_welc, m_dev, m_trade, m_cur = entered[1], entered[2], entered[3], entered[4]
        for cmd in [
            "workspace_welcome",
            "workspace_dev",
            "workspace_trading",
            "workspace_cursor",
            "workspace_monitors",
            "daily_digest",
            "user_profile",
            "security_audit",
            "media_play_pause",
            "media_next",
            "media_prev",
            "media_stop",
            "media_vol_up",
            "media_vol_down",
            "media_mute",
            "darius_protocol",
            "darius_wit",
            "news_headlines",
            "lexicon_lookup",
            "youtube_search",
            "ocr_screen",
            "biometric_auth",
            "darius_timer_create",
            "darius_timer_status",
            "darius_timer_cancel",
            "wake_on_lan",
            "tactical_silence",
            "emergency_lockdown",
            "orbital_iss",
            "air_traffic",
            "seismic_alert",
            "space_weather",
            "gods_eye_protocol",
            "gemini_live_start",
            "gemini_live_stop",
            "antigravity_agent_status",
            "sentinel_activate",
            "sentinel_deactivate",
            "generate_dossier",
        ]:
            ok, msg = wc.run_action({"action": {"type": "python", "run": cmd}})
            assert ok is True, f"{cmd} failed: {msg}"

        m_welc.assert_called_once()
        m_dev.assert_called_once()
        m_trade.assert_called_once()
        m_cur.assert_called_once()

        # Miss / fallback branches
        mock_lex.lookup.return_value = (False, None, [])
        mock_ocr.ocr_screen_region.return_value = SimpleNamespace(text="   ", word_count=0)
        mock_timer_mgr.list_active_timers.return_value = []
        mock_ag.is_available.return_value = False
        mock_sentinel.start.return_value = False
        mock_radar.get_iss_position.return_value = (False, None, "no iss")
        mock_air.scan_overhead.return_value = (False, [], "no air")
        mock_seismic.get_recent_earthquakes.return_value = (False, [], "no quake")
        mock_space.get_current_space_weather.return_value = (False, None, "no sw")

        assert "No se encontró" in wc.run_action({"action": {"type": "python", "run": "lexicon_lookup"}})[1]
        assert "No se detectó" in wc.run_action({"action": {"type": "python", "run": "ocr_screen"}})[1]
        assert "No hay temporizadores" in wc.run_action({"action": {"type": "python", "run": "darius_timer_status"}})[1]
        assert wc.run_action({"action": {"type": "python", "run": "antigravity_agent_status"}})[0] is False
        assert wc.run_action({"action": {"type": "python", "run": "sentinel_activate"}})[0] is False
        assert wc.run_action({"action": {"type": "python", "run": "orbital_iss"}})[1] == "no iss"
        assert "despejado" in wc.run_action({"action": {"type": "python", "run": "gods_eye_protocol"}})[1]

        # Custom callable & no-op
        assert wc.run_action({"action": {"type": "python", "fn": lambda: 42}}) == (True, "42")
        assert wc.run_action({"action": {"type": "python", "run": "unmapped_noop"}}) == (True, "")


async def _async_noop():
    return None


def test_run_action_shell_paths_and_launch_variants(tmp_path):
    with (
        patch("subprocess.Popen") as m_popen,
        patch("subprocess.run", return_value=SimpleNamespace(stdout="x" * 350, stderr="")) as m_run,
    ):
        assert wc.run_action({"action": {"type": "powershell", "run": "Get-Date"}, "open_window": True}) == (True, "")
        assert wc.run_action({"action": {"type": "cmd", "run": "dir"}, "open_window": True}) == (True, "")
        assert wc.run_action({"action": {"type": "powershell", "run": "Hidden"}}) == (True, "")
        assert wc.run_action({"action": {"type": "cmd", "run": "echo hi"}}) == (True, "")
        assert m_popen.call_count == 4

        ok_ps, out_ps = wc.run_action({"action": {"type": "powershell", "run": "echo hi"}, "return_output": True})
        assert ok_ps is True and out_ps.endswith("…")
        ok_cmd, _ = wc.run_action({"action": {"type": "cmd", "run": "echo hi"}, "return_output": True})
        assert ok_cmd is True and m_run.call_count == 2

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=15)):
        assert wc.run_action({"action": {"type": "cmd", "run": "sleep"}, "return_output": True})[0] is False

    with patch("subprocess.Popen", side_effect=RuntimeError("boom")):
        assert wc.run_action({"action": {"type": "cmd", "run": "bad"}}) == (False, "boom")

    # _launch branches
    exe_file = tmp_path / "tool.exe"
    exe_file.write_text("bin", encoding="utf-8")
    with patch("os.startfile", create=True) as m_start, patch("subprocess.Popen") as m_popen2:
        assert wc._launch("ms-settings:network") is True
        assert wc._launch("services.msc") is True
        assert wc._launch("ncpa.cpl") is True
        assert wc._launch(str(exe_file)) is True
        assert wc._launch("calc") is True
        assert m_start.call_count == 2
        assert m_popen2.call_count == 3

    with patch("subprocess.Popen", side_effect=[FileNotFoundError("no"), MagicMock()]):
        assert wc._launch("missing_tool", fallback_cmd="calc.exe") is True

    with patch("subprocess.Popen", side_effect=[FileNotFoundError("no"), OSError("fail")]):
        assert wc._launch("missing_tool", fallback_cmd="bad.exe") is False

    with patch("os.startfile", side_effect=RuntimeError("unexpected"), create=True):
        assert wc._launch("ms-settings:bad") is False
