"""
test_media_controller.py — Pruebas unitarias para el controlador multimedia Win32 de Darius AI
================================================================================================
Cubre la emisión de teclas virtuales de medios, ajuste y lectura de volumen maestro,
y limpieza de expresiones de voz para reproducción musical.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.system.media_controller import (
    MediaController,
    clean_media_query,
    clean_youtube_query,
    get_media_controller,
)


class TestMediaKeyDispatcher:
    @pytest.fixture
    def controller(self):
        return MediaController()

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk")
    def test_play_pause_calls_vk_0xb3(self, mock_send_vk, controller):
        mock_send_vk.return_value = (True, "OK")
        success, msg = controller.play_pause()
        assert success is True
        mock_send_vk.assert_called_once_with(0xB3, "Play/Pause")

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk")
    def test_next_track_calls_vk_0xb0(self, mock_send_vk, controller):
        mock_send_vk.return_value = (True, "OK")
        success, msg = controller.next_track()
        assert success is True
        mock_send_vk.assert_called_once_with(0xB0, "Next Track")

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk")
    def test_prev_track_calls_vk_0xb1(self, mock_send_vk, controller):
        mock_send_vk.return_value = (True, "OK")
        success, msg = controller.prev_track()
        assert success is True
        mock_send_vk.assert_called_once_with(0xB1, "Previous Track")

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk")
    def test_stop_calls_vk_0xb2(self, mock_send_vk, controller):
        mock_send_vk.return_value = (True, "OK")
        success, msg = controller.stop()
        assert success is True
        mock_send_vk.assert_called_once_with(0xB2, "Stop")

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk")
    def test_toggle_mute_calls_vk_0xad(self, mock_send_vk, controller):
        mock_send_vk.return_value = (True, "OK")
        success, msg = controller.toggle_mute()
        assert success is True
        mock_send_vk.assert_called_once_with(0xAD, "Mute")

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk")
    def test_volume_up_repeats_step_times(self, mock_send_vk, controller):
        mock_send_vk.return_value = (True, "OK")
        success, msg = controller.volume_up(step=3)
        assert success is True
        assert mock_send_vk.call_count == 3
        mock_send_vk.assert_called_with(0xAF, "Volume Up")

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk")
    def test_volume_down_repeats_step_times(self, mock_send_vk, controller):
        mock_send_vk.return_value = (True, "OK")
        success, msg = controller.volume_down(step=2)
        assert success is True
        assert mock_send_vk.call_count == 2
        mock_send_vk.assert_called_with(0xAE, "Volume Down")

    @patch("ctypes.windll", create=True)
    def test_send_vk_real_calls_keybd_event(self, mock_windll, controller):
        mock_user32 = MagicMock()
        mock_windll.user32 = mock_user32

        success, msg = controller._send_vk(0xB3, "Play/Pause")
        assert success is True
        # Debe llamar presionar (flag 0) y soltar (flag 2)
        assert mock_user32.keybd_event.call_count == 2

    def test_send_vk_handles_exception_gracefully(self, controller):
        with patch("src.darius_ai.system.media_controller.ctypes.windll", create=True) as mock_windll:
            mock_windll.user32.keybd_event.side_effect = RuntimeError("Windows API error")
            success, msg = controller._send_vk(0xB3, "Play/Pause")
            assert success is False
            assert "Windows API error" in msg or "Error" in msg


class TestVolumeLevelControl:
    @pytest.fixture
    def controller(self):
        return MediaController()

    @patch("src.darius_ai.system.media_controller.MediaController._get_pycaw_endpoint")
    def test_set_volume_percent_via_pycaw(self, mock_endpoint, controller):
        mock_ep = MagicMock()
        mock_endpoint.return_value = mock_ep

        success, msg = controller.set_volume_percent(70)
        assert success is True
        assert "70%" in msg
        mock_ep.SetMasterVolumeLevelScalar.assert_called_once()
        args, _ = mock_ep.SetMasterVolumeLevelScalar.call_args
        assert pytest.approx(args[0], 0.01) == 0.70

    @patch("src.darius_ai.system.media_controller.MediaController._get_pycaw_endpoint")
    def test_set_volume_percent_clamping(self, mock_endpoint, controller):
        mock_ep = MagicMock()
        mock_endpoint.return_value = mock_ep

        # Clamp superior
        controller.set_volume_percent(150)
        args, _ = mock_ep.SetMasterVolumeLevelScalar.call_args
        assert pytest.approx(args[0], 0.01) == 1.0

        # Clamp inferior
        controller.set_volume_percent(-20)
        args, _ = mock_ep.SetMasterVolumeLevelScalar.call_args
        assert pytest.approx(args[0], 0.01) == 0.0

    @patch("src.darius_ai.system.media_controller.MediaController._get_pycaw_endpoint")
    def test_get_volume_percent_via_pycaw(self, mock_endpoint, controller):
        mock_ep = MagicMock()
        mock_ep.GetMasterVolumeLevelScalar.return_value = 0.42
        mock_endpoint.return_value = mock_ep

        vol = controller.get_volume_percent()
        assert vol == 42

    @patch("src.darius_ai.system.media_controller.subprocess.run")
    @patch("src.darius_ai.system.media_controller.MediaController._get_pycaw_endpoint", return_value=None)
    def test_set_volume_fallback_powershell(self, mock_pycaw, mock_subproc, controller):
        mock_subproc.return_value = MagicMock(returncode=0, stdout="")
        success, msg = controller.set_volume_percent(50)
        assert success is True
        assert mock_subproc.called


class TestCleanMediaQuery:
    @pytest.mark.parametrize(
        ("raw_input", "expected"),
        [
            ("reproduce música de Daft Punk", "Daft Punk"),
            ("pon la canción Bohemian Rhapsody", "Bohemian Rhapsody"),
            ("escuchar a Queen", "Queen"),
            ("reproducir el tema Hotel California", "Hotel California"),
            ("pon música de Pink Floyd en spotify", "Pink Floyd"),
            ("pon canciones de The Beatles en youtube", "The Beatles"),
            ("play music by Hans Zimmer", "Hans Zimmer"),
            ("toca algo de Michael Jackson", "Michael Jackson"),
            ("pon 'Billie Jean'", "Billie Jean"),
            ("reproduce", ""),
            ("", ""),
        ],
    )
    def test_clean_media_query_variations(self, raw_input, expected):
        result = clean_media_query(raw_input)
        assert result.strip() == expected.strip()

    def test_clean_media_query_method_on_controller(self):
        controller = MediaController()
        assert controller.clean_media_query("pon música de AC/DC") == "AC/DC"


class TestSingleton:
    def test_get_media_controller_singleton(self):
        c1 = get_media_controller()
        c2 = get_media_controller()
        assert c1 is c2
        assert isinstance(c1, MediaController)


class TestMediaControllerEdgeCases:
    @pytest.fixture
    def controller(self):
        return MediaController()

    def test_send_vk_non_windows_simulation(self, controller):
        controller._is_windows = False
        success, msg = controller._send_vk(0xB3, "Play/Pause")
        assert success is True
        assert "Simulado" in msg

    def test_send_vk_no_user32_simulation(self, controller):
        controller._is_windows = True
        with patch("src.darius_ai.system.media_controller.ctypes.windll", None):
            success, msg = controller._send_vk(0xB3, "Play/Pause")
            assert success is True
            assert "Simulado" in msg

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk", return_value=(False, "Failed"))
    def test_volume_up_failure_branch(self, mock_send, controller):
        success, msg = controller.volume_up(step=1)
        assert success is False
        assert msg == "Failed"

    @patch("src.darius_ai.system.media_controller.MediaController._send_vk", return_value=(False, "Failed"))
    def test_volume_down_failure_branch(self, mock_send, controller):
        success, msg = controller.volume_down(step=1)
        assert success is False
        assert msg == "Failed"

    def test_get_pycaw_endpoint_live_or_safe(self, controller):
        # Ejecuta la función real de pycaw en el entorno
        ep = controller._get_pycaw_endpoint()
        # Debe devolver un objeto endpoint válido o None en CI/sin hardware
        if ep is not None:
            assert hasattr(ep, "GetMasterVolumeLevelScalar") or hasattr(ep, "SetMasterVolumeLevelScalar")

    @patch("src.darius_ai.system.media_controller.MediaController._get_pycaw_endpoint")
    @patch("src.darius_ai.system.media_controller.subprocess.run")
    def test_set_volume_pycaw_exception_falls_back_to_powershell(self, mock_subproc, mock_endpoint, controller):
        mock_ep = MagicMock()
        mock_ep.SetMasterVolumeLevelScalar.side_effect = RuntimeError("COM Error")
        mock_endpoint.return_value = mock_ep
        mock_subproc.return_value = MagicMock(returncode=0)

        success, msg = controller.set_volume_percent(50)
        assert success is True
        assert "PowerShell" in msg

    @patch("src.darius_ai.system.media_controller.MediaController._get_pycaw_endpoint")
    @patch("src.darius_ai.system.media_controller.subprocess.run", side_effect=Exception("PowerShell failed"))
    def test_set_volume_both_fail(self, mock_subproc, mock_endpoint, controller):
        mock_ep = MagicMock()
        mock_ep.SetMasterVolumeLevelScalar.side_effect = RuntimeError("COM Error")
        mock_endpoint.return_value = mock_ep

        success, msg = controller.set_volume_percent(50)
        assert success is False
        assert "No se pudo ajustar" in msg

    @patch("src.darius_ai.system.media_controller.MediaController._get_pycaw_endpoint")
    def test_get_volume_percent_exception_returns_default(self, mock_endpoint, controller):
        mock_ep = MagicMock()
        mock_ep.GetMasterVolumeLevelScalar.side_effect = RuntimeError("Device not found")
        mock_endpoint.return_value = mock_ep

        vol = controller.get_volume_percent()
        assert vol == 50


class TestCleanYoutubeQuery:
    @pytest.mark.parametrize(
        ("raw_input", "expected"),
        [
            ("busca en youtube bohemian rhapsody", "bohemian rhapsody"),
            ("reproduce en youtube Imagine Dragons", "Imagine Dragons"),
            ("pon Bohemian Rhapsody en youtube", "Bohemian Rhapsody"),
            ("search on youtube interstellar theme", "interstellar theme"),
            ("ver video de trailer matrix en youtube", "trailer matrix"),
            ("youtube lofi hip hop", "lofi hip hop"),
            ("pon música de Daft Punk", "Daft Punk"),
            ("youtube", ""),
            ("", ""),
        ],
    )
    def test_clean_youtube_query_variations(self, raw_input, expected):
        res = clean_youtube_query(raw_input)
        assert res.strip() == expected.strip()

    def test_clean_youtube_query_controller_method(self):
        controller = MediaController()
        res = controller.clean_youtube_query("reproduce en youtube Queen")
        assert res == "Queen"


class TestSearchAndPlayYouTube:
    @pytest.fixture
    def controller(self):
        return MediaController()

    @patch("webbrowser.open")
    @patch.object(MediaController, "play_pause")
    def test_search_and_play_youtube_success_autoplay(self, mock_play_pause, mock_web_open, controller):
        mock_web_open.return_value = True
        mock_play_pause.return_value = (True, "Play/Pause sent")

        success, msg = controller.search_and_play_youtube("reproduce en youtube Bohemian Rhapsody", auto_play=True)
        assert success is True
        assert "Bohemian Rhapsody" in msg
        assert "youtube.com/results?search_query=Bohemian+Rhapsody" in msg
        mock_web_open.assert_called_once_with("https://www.youtube.com/results?search_query=Bohemian+Rhapsody")
        mock_play_pause.assert_called_once()

    @patch("webbrowser.open")
    @patch.object(MediaController, "play_pause")
    def test_search_and_play_youtube_no_autoplay(self, mock_play_pause, mock_web_open, controller):
        mock_web_open.return_value = True

        success, msg = controller.search_and_play_youtube("busca en youtube Daft Punk", auto_play=False)
        assert success is True
        assert "Daft Punk" in msg
        mock_web_open.assert_called_once()
        mock_play_pause.assert_not_called()

    def test_search_and_play_youtube_empty_query(self, controller):
        success, msg = controller.search_and_play_youtube("   ")
        assert success is False
        assert "vacía o inválida" in msg

    def test_search_and_play_youtube_only_noise(self, controller):
        success, msg = controller.search_and_play_youtube("busca en youtube")
        assert success is False
        assert "vacía o inválida" in msg

    @patch("src.darius_ai.system.media_controller.is_safe_url")
    def test_search_and_play_youtube_antissrf_blocked(self, mock_is_safe, controller):
        mock_is_safe.return_value = (False, "Blocked metadata IP")
        success, msg = controller.search_and_play_youtube("test query")
        assert success is False
        assert "Anti-SSRF" in msg

    @patch("webbrowser.open", side_effect=Exception("Browser launch failed"))
    def test_search_and_play_youtube_browser_exception(self, mock_web_open, controller):
        success, msg = controller.search_and_play_youtube("lofi hip hop")
        assert success is False
        assert "Error al abrir YouTube" in msg


