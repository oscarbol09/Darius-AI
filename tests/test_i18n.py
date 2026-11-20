"""Tests unitarios para el motor de internacionalización (i18n) y soporte bilingüe EN/ES."""

from __future__ import annotations

import contextlib
import threading
import types
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.core.i18n import TRANSLATIONS, I18nEngine, _, get_i18n, t


def test_i18n_init_and_language_switching():
    engine = I18nEngine(initial_lang="invalid")
    assert engine.language == "en"

    assert engine.set_language("es-CO") is True
    assert engine.language == "es"
    assert engine.set_language("es") is False

    assert engine.set_language("en") is True
    assert engine.language == "en"


@pytest.mark.parametrize(
    "lang, key, default, kwargs, expected_substr",
    [
        ("es", "speech.time", None, {"time": "14:00"}, "14:00"),
        ("en", "speech.time", None, {"time": "14:00"}, "14:00"),
        ("es", "nonexistent.key", "Valor por defecto", {}, "Valor por defecto"),
        ("en", "nonexistent.key", None, {}, "nonexistent.key"),
        ("es", "speech.time", None, {"wrong_arg": "x"}, "{time}"),
    ],
    ids=["es_interpolated", "en_interpolated", "missing_with_default", "missing_returns_key", "bad_format_safe"],
)
def test_i18n_lookup_and_fallbacks(lang: str, key: str, default: str | None, kwargs: dict, expected_substr: str):
    engine = I18nEngine(initial_lang=lang)
    val = engine.get(key, default=default, **kwargs)
    assert expected_substr in val


def test_i18n_spanish_falls_back_to_english_key(monkeypatch):
    from src.darius_ai.core import i18n as i18n_mod

    monkeypatch.setitem(i18n_mod.TRANSLATIONS["en"], "test.only_en", "English Only")
    engine = I18nEngine(initial_lang="es")
    assert engine.get("test.only_en") == "English Only"


def test_i18n_listeners_notify_and_survive_callback_errors():
    engine = I18nEngine(initial_lang="en")
    good_cb = MagicMock()
    bad_cb = MagicMock(side_effect=RuntimeError("boom"))

    engine.register_listener(bad_cb)
    engine.register_listener(good_cb)
    engine.register_listener(good_cb)  # Idempotente

    assert engine.set_language("es") is True
    bad_cb.assert_called_once_with("es")
    good_cb.assert_called_once_with("es")

    engine.unregister_listener(good_cb)
    assert engine.set_language("en") is True
    good_cb.assert_called_once()


def test_global_i18n_helpers():
    inst = get_i18n()
    assert inst is get_i18n()
    assert t("nonexistent.x", default="ok") == "ok"
    assert _("nonexistent.y", default="ok2") == "ok2"


def test_i18n_catalog_parity_and_gui_keys():
    en_keys = set(TRANSLATIONS["en"].keys())
    es_keys = set(TRANSLATIONS["es"].keys())
    assert en_keys == es_keys

    required = {
        "topbar.caption",
        "topbar.user_online",
        "sidebar.inicio",
        "sidebar.configuracion",
        "sidebar.quote",
        "capsule.placeholder",
        "bento.darius_protocol",
        "bento.situational_briefing",
        "settings.title",
        "settings.language_label",
        "settings.save_btn",
    }
    assert required.issubset(en_keys)


def test_edge_tts_and_stt_bilingual_defaults():
    from src.darius_ai.audio.edge_tts_engine import EdgeTTS
    from src.darius_ai.audio.stt_engine import STTEngine

    assert "en-GB-RyanNeural" in EdgeTTS.VOICES
    assert "en-US-JennyNeural" in EdgeTTS.VOICES
    assert EdgeTTS.get_default_voice("en") == "en-GB-RyanNeural"
    assert EdgeTTS.get_default_voice("es") == "es-MX-DaliaNeural"

    assert STTEngine.resolve_locale("en") == "en-US"
    assert STTEngine.resolve_locale("es") == "es-ES"

    fake_sr = types.ModuleType("speech_recognition")
    fake_sr.WaitTimeoutError = type("WaitTimeoutError", (Exception,), {})  # type: ignore[attr-defined]
    fake_sr.UnknownValueError = type("UnknownValueError", (Exception,), {})  # type: ignore[attr-defined]
    mock_rec = MagicMock()
    mock_rec.listen.return_value = b"audio-en"
    mock_rec.recognize_google.return_value = "darius what time is it"
    fake_sr.Recognizer = MagicMock(return_value=mock_rec)  # type: ignore[attr-defined]
    mock_mic = MagicMock()
    mock_mic.__enter__.return_value = MagicMock()
    fake_sr.Microphone = MagicMock(return_value=mock_mic)  # type: ignore[attr-defined]

    stt_en = STTEngine(backend="google", language="en")
    assert stt_en.language == "en-US"
    with patch.dict("sys.modules", {"speech_recognition": fake_sr}):
        assert stt_en.listen(timeout=1.0) == "darius what time is it"
    mock_rec.recognize_google.assert_called_once_with(b"audio-en", language="en-US")


def test_darius_persona_english_prompts_and_retorts():
    from src.darius_ai.core.darius_persona import DariusPersona

    prompt_en = DariusPersona.build_darius_system_prompt(user_name="Sir", language="en")
    assert "You are DARIUS" in prompt_en
    assert "'Sir'" in prompt_en

    ack_en = DariusPersona.get_tactical_acknowledgment("system", user_name="Sir", language="en")
    assert "Sir" in ack_en

    retort = DariusPersona.get_witty_retort("tell me a joke", user_name="Sir", fallback=False, language="en")
    assert retort is not None
    assert "Sir" in retort

    cleaned = DariusPersona.format_butler_response(
        "Certainly! Your CPU load is 12%. I hope this helps!", user_name="Sir", language="en"
    )
    assert cleaned == "Your CPU load is 12%."


def test_darius_final_english_command_routing():
    from src.darius_ai.gui.app import DariusFinal

    app = object.__new__(DariusFinal)
    app.running = True
    app.installed_apps = {}
    app._pending_action = None
    app._pending_lock = threading.RLock()
    app.talk = MagicMock()
    app.set_status = MagicMock()
    app.add_to_chat = MagicMock()
    app.reset_conversation = MagicMock()
    app.tts_worker = MagicMock()

    app.execute_command("darius what time is it")
    assert "It is " in app.talk.call_args[0][0]

    app.talk.reset_mock()
    app.execute_command("what is today's date")
    assert "Today is " in app.talk.call_args[0][0]

    app.execute_command("new conversation")
    app.reset_conversation.assert_called_once()

    with (
        patch("src.darius_ai.gui.app.volume_up") as mock_up,
        patch("src.darius_ai.gui.app.volume_down") as mock_down,
        patch("src.darius_ai.gui.app.volume_mute") as mock_mute,
    ):
        app.execute_command("volume up")
        mock_up.assert_called_once()
        app.execute_command("volume down")
        mock_down.assert_called_once()
        app.execute_command("mute volume")
        mock_mute.assert_called_once()

    with patch("src.darius_ai.gui.app.threading.Thread") as mock_thread:
        app.execute_command("what is the capital of France")
        assert any(call.kwargs.get("name") == "gemini" for call in mock_thread.call_args_list)


def test_hud_widgets_set_language_en_and_es():
    import customtkinter as ctk

    from src.darius_ai.gui.cyber_sidebar import CyberSidebar
    from src.darius_ai.gui.cyber_top_bar import CyberTopBar, format_clock_string, format_status_badge
    from src.darius_ai.gui.floating_voice_capsule import FloatingVoiceCapsule

    en_badge = format_status_badge(system_status="Operativo", is_online=True, model="GPT-4o", language="en")
    assert en_badge == "System: Nominal | Net: Connected | AI: GPT-4o"

    _, en_date = format_clock_string(datetime(2026, 12, 5, 9, 30), language="en")
    assert en_date == "05 Dec 2026"

    try:
        root = ctk.CTk()
        root.withdraw()
    except Exception as exc:
        pytest.skip(f"Tkinter display unavailable: {exc}")

    try:
        top_bar = CyberTopBar(root, language="en")
        assert top_bar.lbl_brand_caption.cget("text") == TRANSLATIONS["en"]["topbar.caption"]
        top_bar.set_language("es")
        assert top_bar.lbl_brand_caption.cget("text") == TRANSLATIONS["es"]["topbar.caption"]

        sidebar = CyberSidebar(root)
        sidebar.set_language("en")
        assert "Home" in sidebar.nav_buttons["inicio"].cget("text")
        sidebar.set_language("es")
        assert "Inicio" in sidebar.nav_buttons["inicio"].cget("text")

        capsule = FloatingVoiceCapsule(root)
        capsule.set_language("en")
        assert capsule.entry.cget("placeholder_text") == TRANSLATIONS["en"]["capsule.placeholder"]
    finally:
        with contextlib.suppress(Exception):
            root.destroy()
