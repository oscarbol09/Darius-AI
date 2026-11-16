"""
conftest.py — Configuración compartida de pytest para DARIUS AI
================================================================
Define marcadores, fixtures globales y configuración de plataforma.
"""

import copy
import json
import os
import platform
import sys

import pytest

# Añade la raíz del proyecto al path para que los tests puedan
# importar módulos como windows_commands, config_loader, etc.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def pytest_configure(config):
    """Registra marcadores personalizados para categorizar tests por plataforma."""
    config.addinivalue_line("markers", "windows: test que solo funciona en Windows")
    config.addinivalue_line("markers", "live: test que requiere API key real o hardware")


def pytest_collection_modifyitems(config, items):
    """Salta tests marcados como windows si no estamos en Windows."""
    if platform.system() != "Windows":
        skip_windows = pytest.mark.skip(reason="Solo disponible en Windows")
        for item in items:
            if "windows" in item.keywords:
                item.add_marker(skip_windows)


@pytest.fixture(autouse=True)
def isolate_user_data_dir(tmp_path, monkeypatch):
    """Aísla datos mutables, bóveda Obsidian, i18n y credenciales por cada prueba."""
    from src.darius_ai.core import config_loader
    from src.darius_ai.core.i18n import get_i18n
    from src.darius_ai.core.obsidian_brain import brain

    data_dir = tmp_path / "darius_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = tmp_path / "obsidian_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    temp_config = data_dir / "config.json"

    base_data = copy.deepcopy(config_loader._DEFAULTS)
    root_template = os.path.join(_PROJECT_ROOT, "config.template.json")
    root_config = os.path.join(_PROJECT_ROOT, "config.json")
    template_source = root_template if os.path.exists(root_template) else root_config
    if os.path.exists(template_source):
        with open(template_source, encoding="utf-8") as f:
            loaded = json.loads(f.read())
            loaded.pop("_comment", None)
            base_data = config_loader._deep_merge(base_data, loaded)

    # Aislar bóveda Obsidian para evitar fugas desde el disco real del usuario
    base_data.setdefault("obsidian", {})["vault_path"] = str(vault_dir)
    isolated_data = config_loader._validate_types(base_data, config_loader._SCHEMA)
    temp_config.write_text(json.dumps(isolated_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Aislar variables de entorno con claves reales salvo ejecución explícita --live
    if os.getenv("DARIUS_RUN_LIVE_TESTS") != "1":
        for env_key in (
            "GEMINI_API_KEY",
            "ANTIGRAVITY_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "NVIDIA_API_KEY",
            "NVIDIA_NIM_API_KEY",
            "GROQ_API_KEY",
            "CUSTOM_API_KEY",
            "ELEVENLABS_API_KEY",
        ):
            monkeypatch.delenv(env_key, raising=False)

    monkeypatch.setattr("src.darius_ai.core.config_loader.get_user_data_dir", lambda: data_dir)
    monkeypatch.setattr("src.darius_ai.core.config_loader._CONFIG_FILE", temp_config)

    with config_loader.cfg._lock:
        orig_cfg_data = copy.deepcopy(config_loader.cfg._data)
        config_loader.cfg._data = copy.deepcopy(isolated_data)

    orig_vault_dir = brain._vault_dir
    orig_custom_path = brain._custom_path
    brain._vault_dir = None
    brain._custom_path = None
    get_i18n().set_language(config_loader.cfg.language)

    try:
        yield data_dir
    finally:
        with config_loader.cfg._lock:
            config_loader.cfg._data = orig_cfg_data
        brain._vault_dir = orig_vault_dir
        brain._custom_path = orig_custom_path
        get_i18n().set_language(config_loader.cfg.language)
