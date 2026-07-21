"""
ai_client.py — Clientes de IA (Gemini + OpenRouter fallback)
============================================================
Extraído de main.py para separar responsabilidades.
"""

import os
import json
import random
import logging
import urllib.request as _req

from google import genai
from google.genai import types

from config_loader import cfg

log = logging.getLogger("DARIUS.AI")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

_gemini_client: genai.Client | None = None
if GEMINI_API_KEY:
    _gemini_client = genai.Client(api_key=GEMINI_API_KEY)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

_OPENROUTER_MODELS = [
    "nvidia/nemotron-3-super:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "arcee-ai/arcee-trinity:free",
    "google/gemma-3-4b-it:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "qwen/qwen3-8b:free",
]

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _build_system_instruction() -> str:
    return (
        f"Eres {cfg.ASSISTANT_NAME}, un asistente de inteligencia artificial "
        "amigable, conciso y preciso. Tu creador es Dario. "
        "Respondes siempre en el idioma del usuario. "
        "Evitas respuestas excesivamente largas a menos que el tema lo requiera. "
        "Si no sabes algo, dilo honestamente."
    )


def _classify_gemini_error(exc: Exception) -> str:
    """Clasifica el error de Gemini en un mensaje legible para el usuario."""
    msg = str(exc)
    if "429" in msg:
        return "Gemini está sobrecargado en este momento."
    if "API_KEY" in msg or "API key" in msg:
        return "La API key de Gemini no es válida."
    if "SAFETY" in msg or "safety" in msg:
        return "La respuesta fue bloqueada por las políticas de seguridad de Gemini."
    if "not found" in msg.lower() or "404" in msg:
        return "El modelo de Gemini especificado no está disponible."
    if "quota" in msg.lower():
        return "Se excedió la cuota de la API de Gemini."
    return f"Gemini falló: {msg[:120]}"


def ask_gemini(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    if not _gemini_client:
        raise RuntimeError("GEMINI_API_KEY no está configurada")

    system_instruction = _build_system_instruction()
    contents = []
    if history:
        for m in history:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    try:
        response = _gemini_client.models.generate_content(
            model=cfg.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=cfg.GEMINI_MAX_TOKENS,
                temperature=cfg.GEMINI_TEMPERATURE,
            ),
        )
        text = response.text.strip()
        log.info(f"[Gemini] Respuesta obtenida ({len(text)} chars)")
        return text, "Gemini"
    except Exception as exc:
        error_msg = _classify_gemini_error(exc)
        log.warning(f"[Gemini] Error: {exc}")
        raise RuntimeError(error_msg) from exc


def ask_openrouter(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY no configurada")

    system_instruction = _build_system_instruction()

    messages = [{"role": "system", "content": system_instruction}]
    if history:
        for m in history[-cfg.GEMINI_HISTORY_TURNS * 2:]:
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://darius-ai.local",
        "X-Title": "Darius AI Assistant",
    }

    models = _OPENROUTER_MODELS.copy()
    random.shuffle(models)

    last_error: Exception | None = None
    for model in models:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": cfg.GEMINI_MAX_TOKENS,
            "temperature": cfg.GEMINI_TEMPERATURE,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            request = _req.Request(_OPENROUTER_URL, data=data, headers=headers, method="POST")
            with _req.urlopen(request, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if not choices:
                    raise ValueError(f"OpenRouter devolvió choices vacío para '{model}'")
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if not content or not content.strip():
                    finish = choices[0].get("finish_reason", "unknown")
                    raise ValueError(f"Respuesta vacía de '{model}' (finish_reason={finish})")
                log.info(f"[OpenRouter] Respuesta de '{model}' obtenida.")
                return content.strip(), f"OpenRouter ({model})"
        except Exception as exc:
            log.warning(f"[OpenRouter] Modelo '{model}' falló: {exc}")
            last_error = exc
            continue

    raise RuntimeError(
        f"Todos los modelos de OpenRouter fallaron. Último error: {last_error}"
    )


def get_ai_response(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Intenta Gemini primero; si falla, OpenRouter. Retorna (texto, proveedor)."""
    if _gemini_client:
        try:
            return ask_gemini(prompt, history)
        except Exception as exc:
            log.warning(f"Gemini falló, intentando OpenRouter: {exc}")

    if OPENROUTER_API_KEY:
        try:
            return ask_openrouter(prompt, history)
        except Exception as exc:
            return f"Error al conectar con la IA: {exc}", "error"

    return "No hay API keys configuradas (GEMINI_API_KEY o OPENROUTER_API_KEY).", "error"
