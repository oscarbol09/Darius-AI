"""Tests unitarios para el motor de internacionalización (i18n)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.darius_ai.core.i18n import I18nEngine, _, get_i18n, t


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
