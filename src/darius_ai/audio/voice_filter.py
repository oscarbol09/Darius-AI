"""
voice_filter.py — Filtros de activación por voz para DARIUS AI
================================================================
Contiene las funciones de reconocimiento de nombre y modos de escucha.
Extraídas de main.py para ser testeables de forma aislada (sin GUI,
sin Windows, sin CustomTkinter). Ver test_voice_v6.py.

Uso:
    from src.darius_ai.audio.voice_filter import check_name_in_text, process_recognized_text
"""

import logging
import re
from difflib import SequenceMatcher

log = logging.getLogger("DARIUS.VoiceFilter")

LISTEN_MODE_PTT = "PTT"
LISTEN_MODE_NAME = "NOMBRE"
LISTEN_MODE_AUTO = "AUTO"


def _normalize_token(token: str) -> str:
    """Normaliza un token retirando signos de puntuación y tildes en español."""
    t = token.lower().strip(",.:;!?¿¡'\"")
    accents = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}
    for acc, plain in accents.items():
        t = t.replace(acc, plain)
    return t


def _get_name_aliases(assistant_name: str) -> set[str]:
    """Genera el conjunto de variantes fonéticas y ortográficas aceptadas para el asistente."""
    base = assistant_name.lower().strip()
    aliases = {base, _normalize_token(base)}
    if "darius" in base:
        aliases.update({"dario", "darío", "darios", "daríos", "daryus", "daris"})
    return aliases


def _strip_name(text: str, assistant_name: str) -> str:
    """Quita el nombre del asistente o sus variantes del texto, preservando el resto de la frase."""
    aliases = _get_name_aliases(assistant_name)
    result = text
    # Ordenar por longitud descendente para evitar reemplazos parciales
    for alias in sorted(aliases, key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(alias)}\b[,\s]*", re.IGNORECASE)
        result = pattern.sub("", result)
    return re.sub(r"\s+", " ", result).strip()


def check_name_in_text(
    text: str,
    assistant_name: str,
    cutoff: float,
) -> tuple[bool, str]:
    """
    Verifica si el texto contiene el nombre del asistente o alguna de sus variantes fonéticas.
    Busca tanto por coincidencia de subcadena/regex como por similitud fonética en cualquier posición.
    Retorna (encontrado: bool, texto_limpio_sin_nombre: str).
    """
    if not text or not text.strip():
        return False, ""

    aliases = _get_name_aliases(assistant_name)
    words = text.split()

    # 1. Búsqueda directa por límites de palabra para cada alias registrado
    for alias in aliases:
        if re.search(rf"\b{re.escape(alias)}\b", text, re.IGNORECASE):
            clean = _strip_name(text, assistant_name)
            log.debug("[NOMBRE] Detectado por alias exacto '%s' -> '%s'", alias, clean)
            return True, clean

    # 2. Búsqueda difusa (fuzzy) token a token con normalización contra los alias
    cleaned_words = []
    found = False

    for word in words:
        norm_w = _normalize_token(word)
        word_is_name = False
        for alias in aliases:
            norm_a = _normalize_token(alias)
            if norm_w == norm_a or SequenceMatcher(None, norm_a, norm_w).ratio() >= cutoff:
                word_is_name = True
                break

        if word_is_name:
            found = True
        else:
            cleaned_words.append(word)

    if found:
        clean = " ".join(cleaned_words).strip()
        log.debug("[NOMBRE] Detectado por similitud difusa -> '%s'", clean)
        return True, clean

    return False, text



def process_recognized_text(
    text: str,
    mode: str,
    assistant_name: str,
    cutoff: float,
) -> tuple[bool, str]:
    """
    Filtra texto reconocido según el modo de escucha.
    Retorna (debe_procesar: bool, comando_efectivo: str).

    Modos:
        - NOMBRE: solo procesa si el nombre está presente
        - AUTO: procesa siempre; si hay nombre lo remueve
        - PTT: procesa siempre; remueve nombre si aparece
    """
    if mode == LISTEN_MODE_AUTO:
        found, clean = check_name_in_text(text, assistant_name, cutoff)
        if found:
            return True, clean
        return True, text

    if mode == LISTEN_MODE_NAME:
        found, clean = check_name_in_text(text, assistant_name, cutoff)
        if not found:
            return False, ""
        return True, clean

    if mode == LISTEN_MODE_PTT:
        found, clean = check_name_in_text(text, assistant_name, cutoff)
        if found:
            return True, clean
        return True, text

    return False, ""


# Alias para interoperabilidad y claridad semántica
should_process_command = process_recognized_text

