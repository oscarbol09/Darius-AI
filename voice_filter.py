"""
voice_filter.py — Filtros de activación por voz para DARIUS AI
================================================================
Contiene las funciones de reconocimiento de nombre y modos de escucha.
Extraídas de main.py para ser testeables de forma aislada (sin GUI,
sin Windows, sin CustomTkinter). Ver test_voice_v6.py.

Uso:
    from voice_filter import check_name_in_text, process_recognized_text
"""

import logging
from difflib import SequenceMatcher

log = logging.getLogger("DARIUS.VoiceFilter")

LISTEN_MODE_PTT = "PTT"
LISTEN_MODE_NAME = "NOMBRE"
LISTEN_MODE_AUTO = "AUTO"


def _strip_name(text: str, assistant_name: str) -> str:
    """Quita el nombre del asistente del texto."""
    return text.replace(assistant_name, "").strip()


def check_name_in_text(
    text: str,
    assistant_name: str,
    cutoff: float,
) -> tuple[bool, str]:
    """
    Verifica si el texto contiene el nombre del asistente.
    Retorna (encontrado: bool, texto_limpio_sin_nombre: str).
    """
    words = text.split()
    if assistant_name in text:
        return True, _strip_name(text, assistant_name)
    if words:
        similarity = SequenceMatcher(None, assistant_name, words[0]).ratio()
        if similarity >= cutoff:
            log.debug(
                "[NOMBRE] Variante aceptada: '%s' (%.2f)",
                words[0], similarity,
            )
            return True, " ".join(words[1:]).strip()
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
    words = text.split()

    if mode == LISTEN_MODE_AUTO:
        if assistant_name in text:
            return True, _strip_name(text, assistant_name)
        if words:
            sim = SequenceMatcher(None, assistant_name, words[0]).ratio()
            if sim > cutoff:
                return True, " ".join(words[1:]).strip()
        return True, text

    if mode == LISTEN_MODE_NAME:
        found, clean = check_name_in_text(text, assistant_name, cutoff)
        if not found:
            return False, ""
        return True, clean

    if mode == LISTEN_MODE_PTT:
        clean = _strip_name(text, assistant_name) if assistant_name in text else text
        return True, clean

    return False, ""
