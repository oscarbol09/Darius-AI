"""
config_loader.py — Cargador de configuración local para DARIUS AI
=================================================================
Lee config.json del directorio del proyecto y expone un objeto `cfg`
con acceso tipado a todos los parámetros configurables.

Si config.json no existe, lo crea con los valores por defecto, de forma
que el usuario siempre disponga de un archivo editable en disco.

Uso en main.py:
    from config_loader import cfg

    assistant_name = cfg.assistant_name   # "darius"
    user_name      = cfg.user_name        # "Oscar"
    vault_path     = cfg.obsidian_vault_path
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("DARIUS.Config")

_BASE_DIR = Path(__file__).parent
_CONFIG_FILE = _BASE_DIR / "config.json"

# Valores por defecto: garantizan arranque seguro aunque falte config.json
_DEFAULTS: dict = {
    "assistant": {
        "name": "darius",
        "user_name": "Oscar",
    },
    "gemini": {
        "model": "gemini-2.5-flash",
        "max_tokens": 800,
        "temperature": 0.7,
        "history_turns": 10,
    },
    "llm": {
        "active_provider": "gemini",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "openai_api_key": "",
        "openai_model": "gpt-4o-mini",
        "openrouter_api_key": "",
        "openrouter_model": "google/gemma-3-27b-it:free",
        "nvidia_api_key": "",
        "nvidia_model": "meta/llama-3.1-70b-instruct",
        "groq_api_key": "",
        "groq_model": "llama-3.3-70b-versatile",
        "ollama_base_url": "http://localhost:11434/v1",
        "ollama_model": "llama3.2",
        "custom_base_url": "http://localhost:1234/v1",
        "custom_api_key": "",
        "custom_model": "local-model",
        "fallback_enabled": True,
    },
    "tts": {
        "rate": 1,
        "volume": 100,
    },
    "microphone": {
        "energy_threshold": 3000,
        "pause_threshold": 0.8,
        "listen_timeout": 5,
        "phrase_limit": 10,
    },
    "obsidian": {
        "vault_path": "",
        "daily_notes_folder": "Diario",
        "memories_folder": "Darius/Memorias",
        "auto_inject_context": True,
    },
    "app_cache_hours": 6,
    "speaking_tail_secs": 0.4,
    "listen_mode": "NOMBRE",
    "listen_key": "right ctrl",
    "name_similarity_cutoff": 0.60,
    "min_words_without_name": 99,
}


# ==============================================================================
#  Clase de configuración
# ==============================================================================

class _Config:
    """
    Acceso tipado a la configuración con fallback automático a defaults.
    Todos los valores son propiedades de solo lectura; para cambiarlos
    en runtime usa cfg.set(valor, *claves).
    """

    def __init__(self, data: dict):
        self._data = data

    # ── Acceso genérico ───────────────────────────────────────────────────────

    def get(self, *keys, default=None):
        """Accede a un valor anidado por claves. Retorna default si no existe."""
        node = self._data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def set(self, value, *keys):
        """
        Actualiza un valor en la config en runtime y lo persiste en config.json.
        Ejemplo: cfg.set("Miguel", "assistant", "user_name")
        """
        if not keys:
            return
        node = self._data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
        self._save()

    def _save(self):
        """Persiste el estado actual en config.json."""
        try:
            data_to_write = {
                k: v for k, v in self._data.items()
                if not k.startswith("_comment")
            }
            _CONFIG_FILE.write_text(
                json.dumps(data_to_write, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("config.json actualizado.")
        except Exception as e:
            log.warning(f"No se pudo guardar config.json: {e}")

    # ── Propiedades con tipo estático ─────────────────────────────────────────

    @property
    def assistant_name(self) -> str:
        return str(self.get("assistant", "name", default="darius"))

    @property
    def user_name(self) -> str:
        return str(self.get("assistant", "user_name", default="Oscar"))

    @property
    def gemini_model(self) -> str:
        return str(self.get("gemini", "model", default="gemini-2.5-flash"))

    @property
    def gemini_max_tokens(self) -> int:
        return int(self.get("gemini", "max_tokens", default=800))

    @property
    def gemini_temperature(self) -> float:
        return float(self.get("gemini", "temperature", default=0.7))

    @property
    def gemini_history_turns(self) -> int:
        return int(self.get("gemini", "history_turns", default=10))

    @property
    def tts_rate(self) -> int:
        return int(self.get("tts", "rate", default=1))

    @property
    def tts_volume(self) -> int:
        return int(self.get("tts", "volume", default=100))

    @property
    def mic_energy_threshold(self) -> int:
        return int(self.get("microphone", "energy_threshold", default=3000))

    @property
    def mic_pause_threshold(self) -> float:
        return float(self.get("microphone", "pause_threshold", default=0.8))

    @property
    def mic_listen_timeout(self) -> int:
        return int(self.get("microphone", "listen_timeout", default=5))

    @property
    def mic_phrase_limit(self) -> int:
        return int(self.get("microphone", "phrase_limit", default=10))

    @property
    def obsidian_vault_path(self) -> str:
        return str(self.get("obsidian", "vault_path", default=""))

    @property
    def obsidian_daily_notes_folder(self) -> str:
        return str(self.get("obsidian", "daily_notes_folder", default="Diario"))

    @property
    def obsidian_memories_folder(self) -> str:
        return str(self.get("obsidian", "memories_folder", default="Darius/Memorias"))

    @property
    def obsidian_auto_inject_context(self) -> bool:
        return bool(self.get("obsidian", "auto_inject_context", default=True))

    @property
    def app_cache_hours(self) -> int:
        return int(self.get("app_cache_hours", default=6))

    @property
    def speaking_tail_secs(self) -> float:
        return float(self.get("speaking_tail_secs", default=0.4))

    @property
    def default_listen_mode(self) -> str:
        return str(self.get("listen_mode", default="NOMBRE"))

    @property
    def listen_key(self) -> str:
        return str(self.get("listen_key", default="right ctrl"))

    @property
    def name_similarity_cutoff(self) -> float:
        return float(self.get("name_similarity_cutoff", default=0.60))

    @property
    def min_words_without_name(self) -> int:
        return int(self.get("min_words_without_name", default=99))

    # ── Propiedades BYOK Multi-Proveedor ──────────────────────────────────────

    @property
    def active_provider(self) -> str:
        return str(self.get("llm", "active_provider", default="gemini")).lower().strip()

    @property
    def llm_gemini_api_key(self) -> str:
        return str(self.get("llm", "gemini_api_key", default=""))

    @property
    def llm_gemini_model(self) -> str:
        return str(self.get("llm", "gemini_model", default="gemini-2.5-flash"))

    @property
    def llm_openai_api_key(self) -> str:
        return str(self.get("llm", "openai_api_key", default=""))

    @property
    def llm_openai_model(self) -> str:
        return str(self.get("llm", "openai_model", default="gpt-4o-mini"))

    @property
    def llm_openrouter_api_key(self) -> str:
        return str(self.get("llm", "openrouter_api_key", default=""))

    @property
    def llm_openrouter_model(self) -> str:
        return str(self.get("llm", "openrouter_model", default="google/gemma-3-27b-it:free"))

    @property
    def llm_nvidia_api_key(self) -> str:
        return str(self.get("llm", "nvidia_api_key", default=""))

    @property
    def llm_nvidia_model(self) -> str:
        return str(self.get("llm", "nvidia_model", default="meta/llama-3.1-70b-instruct"))

    @property
    def llm_groq_api_key(self) -> str:
        return str(self.get("llm", "groq_api_key", default=""))

    @property
    def llm_groq_model(self) -> str:
        return str(self.get("llm", "groq_model", default="llama-3.3-70b-versatile"))

    @property
    def llm_ollama_base_url(self) -> str:
        return str(self.get("llm", "ollama_base_url", default="http://localhost:11434/v1"))

    @property
    def llm_ollama_model(self) -> str:
        return str(self.get("llm", "ollama_model", default="llama3.2"))

    @property
    def llm_custom_base_url(self) -> str:
        return str(self.get("llm", "custom_base_url", default="http://localhost:1234/v1"))

    @property
    def llm_custom_api_key(self) -> str:
        return str(self.get("llm", "custom_api_key", default=""))

    @property
    def llm_custom_model(self) -> str:
        return str(self.get("llm", "custom_model", default="local-model"))

    @property
    def llm_fallback_enabled(self) -> bool:
        return bool(self.get("llm", "fallback_enabled", default=True))


# ==============================================================================
#  Esquema de validación de tipos
# ==============================================================================

_SCHEMA: dict = {
    "assistant": {
        "name": str,
        "user_name": str,
    },
    "gemini": {
        "model": str,
        "max_tokens": int,
        "temperature": (int, float),
        "history_turns": int,
    },
    "llm": {
        "active_provider": str,
        "gemini_api_key": str,
        "gemini_model": str,
        "openai_api_key": str,
        "openai_model": str,
        "openrouter_api_key": str,
        "openrouter_model": str,
        "nvidia_api_key": str,
        "nvidia_model": str,
        "groq_api_key": str,
        "groq_model": str,
        "ollama_base_url": str,
        "ollama_model": str,
        "custom_base_url": str,
        "custom_api_key": str,
        "custom_model": str,
        "fallback_enabled": bool,
    },
    "tts": {
        "rate": (int, float),
        "volume": int,
    },
    "microphone": {
        "energy_threshold": int,
        "pause_threshold": (int, float),
        "listen_timeout": int,
        "phrase_limit": int,
    },
    "obsidian": {
        "vault_path": str,
        "daily_notes_folder": str,
        "memories_folder": str,
        "auto_inject_context": bool,
    },
    "app_cache_hours": int,
    "speaking_tail_secs": (int, float),
    "listen_mode": str,
    "listen_key": str,
    "name_similarity_cutoff": (int, float),
    "min_words_without_name": int,
}


def _get_default(path_parts: list[str]) -> object:
    """Navega _DEFAULTS siguiendo path_parts."""
    node = _DEFAULTS
    for p in path_parts:
        if isinstance(node, dict):
            node = node.get(p)
        else:
            return None
    return node


def _validate_types(data: dict, schema: dict, path: str = "") -> dict:
    """Valida tipos del merge contra el schema. Corrige a default si el tipo no coincide."""
    result = {}
    path_parts = path.split(".") if path else []
    for key, expected in schema.items():
        full_key = f"{path}.{key}" if path else key
        default = _get_default(path_parts + [key])
        if key not in data:
            if default is not None:
                result[key] = default
                log.warning(f"[Config] Falta '{full_key}', usando default: {default}")
            continue
        value = data[key]
        if isinstance(expected, dict):
            if isinstance(value, dict):
                result[key] = _validate_types(value, expected, full_key)
            else:
                if default is not None:
                    result[key] = default
                log.warning(f"[Config] '{full_key}' debería ser dict, usando default")
        else:
            expected_types = expected if isinstance(expected, tuple) else (expected,)
            if not isinstance(value, expected_types):
                fallback = default if default is not None else value
                result[key] = fallback
                log.warning(
                    f"[Config] '{full_key}' type={type(value).__name__} inválido "
                    f"(esperado {'|'.join(t.__name__ for t in expected_types)}), "
                    f"usando default: {fallback}"
                )
            else:
                result[key] = value
    return result


# ==============================================================================
#  Merge y carga
# ==============================================================================

def _deep_merge(base: dict, override: dict) -> dict:
    """
    Merge profundo: claves de `base` no presentes en `override` se conservan.
    Garantiza que nuevas claves añadidas en _DEFAULTS no se pierdan si
    el usuario tiene un config.json más antiguo.
    """
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load() -> _Config:
    data = _DEFAULTS.copy()

    if _CONFIG_FILE.exists():
        try:
            user_data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            # Quitar clave de comentario antes del merge
            user_data.pop("_comment", None)
            data = _deep_merge(_DEFAULTS, user_data)
            log.info(f"[Config] Cargado desde {_CONFIG_FILE.name}")
        except Exception as e:
            log.warning(f"[Config] Error leyendo config.json, usando defaults: {e}")
    else:
        # Primera ejecución: crear config.json para que el usuario pueda editarlo
        try:
            _CONFIG_FILE.write_text(
                json.dumps(_DEFAULTS, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("[Config] config.json creado con valores por defecto.")
        except Exception as e:
            log.warning(f"[Config] No se pudo crear config.json: {e}")

    # Validación de tipos contra el schema; datos inválidos se reemplazan con defaults
    data = _validate_types(data, _SCHEMA)

    return _Config(data)


# Instancia global — importar con: from config_loader import cfg
cfg = _load()
