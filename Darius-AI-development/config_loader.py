"""
config_loader.py — Cargador de configuración externa para DARIUS AI
====================================================================
Lee config.json del directorio del proyecto y expone un objeto `cfg`
con acceso tipado a todos los parámetros configurables.

Si config.json no existe lo crea con los valores por defecto, de forma
que el usuario siempre tenga un archivo editable listo.

Uso en main.py:
    from config_loader import cfg

    ASSISTANT_NAME = cfg.ASSISTANT_NAME   # "darius"
    USER_NAME      = cfg.USER_NAME        # "Oscar"
    ...

    # Cambio en tiempo de ejecución (se persiste en config.json):
    cfg.set("Miguel", "assistant", "user_name")
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("DARIUS.Config")

_BASE_DIR    = Path(__file__).parent
_CONFIG_FILE = _BASE_DIR / "config.json"

# Valores por defecto: garantizan arranque seguro aunque falte config.json
_DEFAULTS: dict = {
    "assistant": {
        "name":      "darius",
        "user_name": "Oscar",
    },
    "gemini": {
        "model":         "gemini-2.5-flash",
        "max_tokens":    300,
        "temperature":   0.7,
        "history_turns": 10,
    },
    "tts": {
        "rate":   1,
        "volume": 100,
    },
    "microphone": {
        "energy_threshold": 3000,
        "pause_threshold":  0.8,
        "listen_timeout":   5,
        "phrase_limit":     10,
    },
    "app_cache_hours":       6,
    "speaking_tail_secs":    0.4,
    "listen_mode":           "NOMBRE",
    "listen_key":            "right ctrl",
    "name_similarity_cutoff": 0.60,
    "min_words_without_name": 99,
}


# ══════════════════════════════════════════════════════════════════════════════
#  Clase de configuración
# ══════════════════════════════════════════════════════════════════════════════

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
            data_to_write = {k: v for k, v in self._data.items()
                             if not k.startswith("_comment")}
            _CONFIG_FILE.write_text(
                json.dumps(data_to_write, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("config.json actualizado.")
        except Exception as e:
            log.warning(f"No se pudo guardar config.json: {e}")

    # ── Propiedades con tipo estático ─────────────────────────────────────────

    @property
    def ASSISTANT_NAME(self) -> str:
        return str(self.get("assistant", "name", default="darius"))

    @property
    def USER_NAME(self) -> str:
        return str(self.get("assistant", "user_name", default="Oscar"))

    @property
    def GEMINI_MODEL(self) -> str:
        return str(self.get("gemini", "model", default="gemini-2.5-flash"))

    @property
    def GEMINI_MAX_TOKENS(self) -> int:
        return int(self.get("gemini", "max_tokens", default=300))

    @property
    def GEMINI_TEMPERATURE(self) -> float:
        return float(self.get("gemini", "temperature", default=0.7))

    @property
    def GEMINI_HISTORY_TURNS(self) -> int:
        return int(self.get("gemini", "history_turns", default=10))

    @property
    def TTS_RATE(self) -> int:
        return int(self.get("tts", "rate", default=1))

    @property
    def TTS_VOLUME(self) -> int:
        return int(self.get("tts", "volume", default=100))

    @property
    def MIC_ENERGY_THRESHOLD(self) -> int:
        return int(self.get("microphone", "energy_threshold", default=3000))

    @property
    def MIC_PAUSE_THRESHOLD(self) -> float:
        return float(self.get("microphone", "pause_threshold", default=0.8))

    @property
    def MIC_LISTEN_TIMEOUT(self) -> int:
        return int(self.get("microphone", "listen_timeout", default=5))

    @property
    def MIC_PHRASE_LIMIT(self) -> int:
        return int(self.get("microphone", "phrase_limit", default=10))

    @property
    def APP_CACHE_HOURS(self) -> int:
        return int(self.get("app_cache_hours", default=6))

    @property
    def SPEAKING_TAIL_SECS(self) -> float:
        return float(self.get("speaking_tail_secs", default=0.4))

    @property
    def DEFAULT_LISTEN_MODE(self) -> str:
        return str(self.get("listen_mode", default="NOMBRE"))

    @property
    def LISTEN_KEY(self) -> str:
        return str(self.get("listen_key", default="right ctrl"))

    @property
    def NAME_SIMILARITY_CUTOFF(self) -> float:
        return float(self.get("name_similarity_cutoff", default=0.60))

    @property
    def MIN_WORDS_WITHOUT_NAME(self) -> int:
        return int(self.get("min_words_without_name", default=99))


# ══════════════════════════════════════════════════════════════════════════════
#  Merge y carga
# ══════════════════════════════════════════════════════════════════════════════

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
            log.info(f"[Config] config.json creado con valores por defecto.")
        except Exception as e:
            log.warning(f"[Config] No se pudo crear config.json: {e}")

    return _Config(data)


# Instancia global — importar con: from config_loader import cfg
cfg = _load()
