"""
supabase_client.py — Cliente Supabase compartido para DARIUS AI
==================================================================
Usado por main.py (escritorio, Windows) y app.py (web, Railway) para que
ambos lean/escriban los mismos datos: chat_history, apps_cache y config.

Diseño defensivo: si SUPABASE_URL / SUPABASE_KEY no están configuradas,
o si la librería `supabase` no está instalada, get_supabase() devuelve
None y cada módulo debe seguir funcionando en modo local (igual que
antes de esta migración), solo que sin persistencia compartida.

Uso:
    from supabase_client import get_supabase

    sb = get_supabase()
    if sb:
        sb.table("chat_history").insert({...}).execute()
"""

import logging
import os

log = logging.getLogger("DARIUS.Supabase")

_client = None
_init_attempted = False


def get_supabase():
    """
    Devuelve un cliente Supabase singleton, o None si no está configurado
    o disponible. Nunca lanza excepción — los llamadores deben tratar
    None como "modo local sin Supabase".
    """
    global _client, _init_attempted

    if _client is not None:
        return _client
    if _init_attempted:
        return None
    _init_attempted = True

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        log.warning(
            "SUPABASE_URL / SUPABASE_KEY no configuradas — "
            "Darius funcionará en modo local (sin datos compartidos)."
        )
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        log.info("Cliente Supabase inicializado correctamente.")
        return _client
    except ImportError:
        log.warning(
            "Librería 'supabase' no instalada (pip install supabase) — "
            "Darius funcionará en modo local."
        )
        return None
    except Exception as e:
        log.error(f"No se pudo inicializar el cliente Supabase: {e}")
        return None
