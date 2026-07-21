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

Sincronización con Supabase (tabla `config`, una fila por sección top-level):
    - Al cargar: si SUPABASE_URL/SUPABASE_KEY están configuradas, se lee la
      tabla `config` y esos valores tienen prioridad sobre config.json local
      (Supabase es la fuente de verdad compartida entre main.py y app.py).
      El resultado combinado se vuelve a escribir en config.json como caché
      offline, para que Darius arranque igual sin conexión.
    - Al hacer cfg.set(): se persiste en config.json Y se hace upsert de la
      sección correspondiente en Supabase. Si Supabase no está disponible,
      el cambio local igual se guarda (no bloquea el arranque ni el uso).
"""

import json
import logging
from pathlib import Path

from supabase_client import get_supabase

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
        "max_tokens":    800,
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
        Actualiza un valor en la config en runtime, lo persiste en config.json
        y lo sincroniza con Supabase (tabla `config`, fila = keys[0]).
        Ejemplo: cfg.set("Miguel", "assistant", "user_name")
        """
        if not keys:
            return
        node = self._data
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value
        self._save()
        self._push_section_to_supabase(keys[0])

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

    def _push_section_to_supabase(self, top_key: str):
        """Sube la sección top-level modificada a la tabla `config` de Supabase."""
        sb = get_supabase()
        if not sb:
            return
        try:
            sb.table("config").upsert({
                "key": top_key,
                "value": self._data.get(top_key),
            }).execute()
            log.info(f"[Config] Sección '{top_key}' sincronizada con Supabase.")
        except Exception as e:
            log.warning(f"[Config] No se pudo sincronizar '{top_key}' con Supabase: {e}")

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
        return int(self.get("gemini", "max_tokens", default=800))

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
#  Esquema de validación de tipos
# ══════════════════════════════════════════════════════════════════════════════

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


def _fetch_supabase_config() -> dict | None:
    """
    Lee todas las filas de la tabla `config` en Supabase y las arma como
    un dict {key: value} equivalente a la estructura top-level de config.json.
    Devuelve None si Supabase no está disponible o la consulta falla.
    """
    sb = get_supabase()
    if not sb:
        return None
    try:
        resp = sb.table("config").select("key, value").execute()
        rows = resp.data or []
        if not rows:
            return None
        remote = {row["key"]: row["value"] for row in rows}
        log.info(f"[Config] {len(remote)} secciones cargadas desde Supabase.")
        return remote
    except Exception as e:
        log.warning(f"[Config] No se pudo leer config desde Supabase: {e}")
        return None


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

    # Supabase, si está disponible, tiene prioridad sobre el config.json local
    # (es la fuente de verdad compartida entre main.py y app.py). El resultado
    # se vuelve a escribir en config.json como caché para arranques offline.
    remote = _fetch_supabase_config()
    if remote:
        data = _deep_merge(data, remote)
        try:
            _CONFIG_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("[Config] config.json actualizado como caché de Supabase.")
        except Exception as e:
            log.warning(f"[Config] No se pudo actualizar caché local: {e}")

    # Validación de tipos contra el schema; datos inválidos se reemplazan con defaults
    data = _validate_types(data, _SCHEMA)

    return _Config(data)


# Instancia global — importar con: from config_loader import cfg
cfg = _load()
