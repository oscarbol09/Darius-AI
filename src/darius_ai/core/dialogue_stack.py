"""
dialogue_stack.py — Pila LIFO de Sub-Diálogos y Confirmaciones para DARIUS AI
=============================================================================
Gestiona marcos interactivos de diálogo multi-turno en estructura de pila LIFO
(Pushdown Automaton) con control de expiración temporal, normalización fonético-textual
en español y fast-path para respuestas afirmativas y negativas.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("DARIUS.DIALOGUE_STACK")

# Conjuntos canónicos de fast-path en español
AFFIRMATIVE_KEYWORDS = {
    "si",
    "sí",
    "claro",
    "confirmo",
    "confirmar",
    "adelante",
    "procede",
    "proceder",
    "afirmativo",
    "correcto",
    "desde luego",
    "por supuesto",
    "autorizo",
    "de acuerdo",
    "ok",
    "yes",
}

NEGATIVE_KEYWORDS = {
    "no",
    "cancela",
    "cancelar",
    "espera",
    "esperar",
    "abortar",
    "aborta",
    "negativo",
    "rechazar",
    "rechazo",
    "detener",
    "detente",
    "parar",
}


def _strip_accents(text: str) -> str:
    """Elimina tildes y diacríticos preservando caracteres alfanuméricos."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def _normalize_text(text: str) -> str:
    """Limpia puntuación, espacios repetidos y convierte a minúsculas."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\sáéíóúüñ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class DialogueFrame:
    """Representa un marco conversacional interactivo en espera de resolución."""

    frame_id: str
    intent: str
    prompt: str
    expected_options: dict[str, str]
    context_data: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    created_at: float = field(default_factory=time.time)


class DariusDialogueStack:
    """
    Pila LIFO de sub-diálogos conversacionales para confirmaciones tácticas en Darius AI.
    Permite anidar preguntas contextuales y recuperar el flujo anterior al resolverlas.
    """

    def __init__(self) -> None:
        self._stack: list[DialogueFrame] = []
        self._lock = threading.Lock()

    def push(self, frame: DialogueFrame) -> None:
        """Apila un nuevo marco de diálogo en la cima."""
        with self._lock:
            self._stack.append(frame)
            log.info(
                "[DialogueStack] Marco apilado: id=%s intent=%s opciones=%s",
                frame.frame_id,
                frame.intent,
                list(frame.expected_options.keys()),
            )

    def pop(self) -> DialogueFrame | None:
        """Desapila y retorna el marco superior de la pila."""
        with self._lock:
            if not self._stack:
                return None
            frame = self._stack.pop()
            log.info("[DialogueStack] Marco desapilado: id=%s", frame.frame_id)
            return frame

    def peek(self) -> DialogueFrame | None:
        """Inspecciona el marco superior sin desapilarlo."""
        with self._lock:
            return self._stack[-1] if self._stack else None

    def is_empty(self) -> bool:
        """Verifica si la pila está vacía."""
        with self._lock:
            return len(self._stack) == 0

    def clear(self) -> None:
        """Vacía completamente la pila de diálogos."""
        with self._lock:
            self._stack.clear()
            log.info("[DialogueStack] Pila de diálogos limpiada por completo.")

    def clean_expired(self) -> list[DialogueFrame]:
        """Elimina todos los marcos cuyo timeout haya caducado."""
        now = time.time()
        expired: list[DialogueFrame] = []
        with self._lock:
            remaining: list[DialogueFrame] = []
            for frame in self._stack:
                if (now - frame.created_at) > frame.timeout_seconds:
                    expired.append(frame)
                else:
                    remaining.append(frame)
            self._stack = remaining

        if expired:
            log.info("[DialogueStack] %d marcos expirados purgados de la pila.", len(expired))
        return expired

    def process_response(self, user_text: str) -> tuple[bool, str, DialogueFrame | None]:
        """
        Procesa la respuesta del usuario contra el marco en la cima de la pila.

        Retorna:
          (éxito: bool, acción_o_mensaje: str, marco: DialogueFrame | None)
        """
        with self._lock:
            if not self._stack:
                return False, "No hay ningún diálogo activo en espera, señor.", None

            top = self._stack[-1]
            now = time.time()

            # 1. Verificar timeout del marco actual
            if (now - top.created_at) > top.timeout_seconds:
                self._stack.pop()
                log.info("[DialogueStack] Marco id=%s expiró por inactividad.", top.frame_id)
                return False, "El diálogo ha expirado por inactividad, señor.", top

            norm_input = _normalize_text(user_text)
            no_accent_input = _strip_accents(norm_input)

            # Diccionario normalizado de opciones esperadas
            norm_options: dict[str, str] = {}
            for opt_key, opt_action in top.expected_options.items():
                norm_key = _normalize_text(opt_key)
                norm_options[norm_key] = opt_action

            # 2. Coincidencia exacta directa
            if norm_input in norm_options:
                self._stack.pop()
                return True, norm_options[norm_input], top

            if no_accent_input in {_strip_accents(k) for k in norm_options}:
                for k, action in norm_options.items():
                    if _strip_accents(k) == no_accent_input:
                        self._stack.pop()
                        return True, action, top

            # 3. Fast-path afirmativo
            is_affirmative = (norm_input in AFFIRMATIVE_KEYWORDS) or (no_accent_input in AFFIRMATIVE_KEYWORDS)
            if is_affirmative:
                aff_action = self._resolve_affirmative_action(norm_options)
                if aff_action is not None:
                    self._stack.pop()
                    return True, aff_action, top

            # 4. Fast-path negativo
            is_negative = (norm_input in NEGATIVE_KEYWORDS) or (no_accent_input in NEGATIVE_KEYWORDS)
            if is_negative:
                neg_action = self._resolve_negative_action(norm_options)
                if neg_action is not None:
                    self._stack.pop()
                    return True, neg_action, top

            # 5. Coincidencia parcial por subcadenas si la clave es distintiva
            for k, action in norm_options.items():
                if len(k) >= 3 and (k in norm_input or norm_input in k):
                    self._stack.pop()
                    return True, action, top

            # 6. Respuesta no concluyente: marco permanece en la cima
            options_hint = ", ".join(f"'{k}'" for k in top.expected_options)
            message = f"Respuesta no concluyente. Por favor confirme una de las opciones ({options_hint}), señor."
            return False, message, top

    def _is_affirmative_key(self, key: str) -> bool:
        """Determina si una clave representa una intención afirmativa."""
        k = _strip_accents(key)
        if k in AFFIRMATIVE_KEYWORDS:
            return True
        return any(term in k for term in ["confirm", "adelant", "proced", "autoriz", "si", "acept"])

    def _is_negative_key(self, key: str) -> bool:
        """Determina si una clave representa una intención negativa."""
        k = _strip_accents(key)
        if k in NEGATIVE_KEYWORDS:
            return True
        return any(term in k for term in ["cancel", "abort", "rechaz", "deten", "no", "deneg"])

    def _resolve_affirmative_action(self, norm_options: dict[str, str]) -> str | None:
        """Encuentra la acción afirmativa en el mapa de opciones normalizadas."""
        for k, action in norm_options.items():
            if self._is_affirmative_key(k):
                return action

        # Si sólo hay dos opciones y una es negativa, deducir la otra
        if len(norm_options) == 2:
            for k, action in norm_options.items():
                if not self._is_negative_key(k):
                    return action

        return None

    def _resolve_negative_action(self, norm_options: dict[str, str]) -> str | None:
        """Encuentra la acción negativa en el mapa de opciones normalizadas."""
        for k, action in norm_options.items():
            if self._is_negative_key(k):
                return action

        # Si sólo hay dos opciones y una es afirmativa, deducir la otra
        if len(norm_options) == 2:
            for k, action in norm_options.items():
                if not self._is_affirmative_key(k):
                    return action

        return None


_GLOBAL_DIALOGUE_STACK: DariusDialogueStack | None = None
_GLOBAL_DIALOGUE_STACK_LOCK = threading.Lock()


def get_darius_dialogue_stack() -> DariusDialogueStack:
    """Retorna la instancia global única de la pila de diálogos de Darius AI."""
    global _GLOBAL_DIALOGUE_STACK
    if _GLOBAL_DIALOGUE_STACK is None:
        with _GLOBAL_DIALOGUE_STACK_LOCK:
            if _GLOBAL_DIALOGUE_STACK is None:
                _GLOBAL_DIALOGUE_STACK = DariusDialogueStack()
    return _GLOBAL_DIALOGUE_STACK


# Aliases para compatibilidad hacia atrás
get_dialogue_stack = get_darius_dialogue_stack
get_stark_dialogue_stack = get_darius_dialogue_stack
StarkDialogueStack = DariusDialogueStack

__all__ = [
    "AFFIRMATIVE_KEYWORDS",
    "NEGATIVE_KEYWORDS",
    "DariusDialogueStack",
    "DialogueFrame",
    "StarkDialogueStack",
    "get_darius_dialogue_stack",
    "get_dialogue_stack",
    "get_stark_dialogue_stack",
]

