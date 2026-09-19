"""
ai_client.py — Motor de IA Multi-Proveedor (BYOK) para DARIUS AI
=================================================================
Soporta:
  - Google Gemini (API nativa google-genai o REST)
  - OpenAI / ChatGPT (GPT-4o, GPT-4o-mini, o3-mini)
  - OpenRouter (Modelos gratuitos y premium con fallback)
  - NVIDIA NIM (Meta Llama 3.1, Nemotron vía API oficial)
  - Groq (Inferencia de ultra-baja latencia)
  - Ollama (Modelos locales: Llama 3.2, DeepSeek-R1, Mistral)
  - Custom / Local (Endpoints compatibles con OpenAI: LM Studio, vLLM)

Integra memoria de Obsidian de forma transparente en todos los proveedores.
"""

import datetime
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request as _req
from typing import Any

from config_loader import cfg

log = logging.getLogger("DARIUS.AI")

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES Y ENDPOINTS PÚBLICOS
# ─────────────────────────────────────────────────────────────────────────────

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

OPENROUTER_FREE_MODELS = [
    "google/gemma-3-27b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-3:free",
    "nvidia/nemotron-3-super:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "arcee-ai/arcee-trinity:free",
    "qwen/qwen3-8b:free",
]

PROVIDER_NAMES = {
    "gemini": "Google Gemini",
    "openai": "OpenAI (ChatGPT)",
    "openrouter": "OpenRouter",
    "nvidia": "NVIDIA NIM",
    "groq": "Groq",
    "ollama": "Ollama (Local)",
    "custom": "Personalizado (Custom)",
}


# ─────────────────────────────────────────────────────────────────────────────
#  RESOLUCIÓN DE CREDENCIALES (BYOK: Config > Entorno)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_provider_key(provider: str) -> str:
    """Resuelve la API Key para un proveedor: primero desde config.json, luego variables de entorno."""
    p = provider.lower().strip()
    if p == "gemini":
        return cfg.llm_gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    if p == "openai":
        return cfg.llm_openai_api_key or os.getenv("OPENAI_API_KEY", "")
    if p == "openrouter":
        return cfg.llm_openrouter_api_key or os.getenv("OPENROUTER_API_KEY", "")
    if p in ("nvidia", "nvidia_nim"):
        return cfg.llm_nvidia_api_key or os.getenv("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_NIM_API_KEY", "")
    if p == "groq":
        return cfg.llm_groq_api_key or os.getenv("GROQ_API_KEY", "")
    if p == "ollama":
        return ""  # Ollama local generalmente no requiere autenticación
    if p == "custom":
        return cfg.llm_custom_api_key or os.getenv("CUSTOM_API_KEY", "")
    return ""


def get_gemini_client() -> Any | None:
    """Instancia cliente Google GenAI si la API key está disponible."""
    api_key = resolve_provider_key("gemini")
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        log.debug(f"No se pudo inicializar genai.Client: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  INYECCIÓN DE SISTEMA Y MEMORIA OBSIDIAN
# ─────────────────────────────────────────────────────────────────────────────

def _get_system_time_context() -> str:
    """Obtiene la fecha, hora y zona horaria locales del equipo para inyectar en los prompts."""
    now = datetime.datetime.now().astimezone()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    dia_semana = dias[now.weekday()]
    dia = now.day
    mes = meses[now.month - 1]
    anio = now.year
    hora_12 = now.strftime("%I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")
    hora_24 = now.strftime("%H:%M")
    tz_name = now.tzname() or "Local"
    offset = now.strftime("%z")
    formatted_offset = f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"

    return (
        f"[HORA Y FECHA LOCAL DEL EQUIPO]\n"
        f"- Fecha del sistema: {dia_semana}, {dia} de {mes} de {anio}\n"
        f"- Hora del sistema: {hora_12} ({hora_24} formato 24h)\n"
        f"- Zona horaria del sistema: {tz_name} ({formatted_offset})\n"
        "Debes basar cualquier referencia temporal, fecha u hora exclusivamente en estos datos locales del equipo."
    )


def _build_system_instruction(prompt: str = "") -> str:
    """Construye las directrices de personalidad de Darius con tiempo local y memoria de Obsidian."""
    time_context = _get_system_time_context()
    base = (
        f"Eres {cfg.assistant_name}, un asistente de inteligencia artificial "
        f"amigable, conciso y preciso para Windows. Tu usuario es {cfg.user_name}. "
        "Respondes siempre en español de forma natural, fluida y directa. "
        "Evitas respuestas excesivamente largas a menos que el tema lo requiera. "
        "Si no sabes algo, dilo honestamente.\n\n"
        f"{time_context}"
    )
    try:
        from obsidian_brain import brain
        context = brain.get_memory_context(prompt)
        if context:
            base += f"\n\n[CONTEXTO DE MEMORIA EN OBSIDIAN]\n{context}"
    except Exception as e:
        log.debug(f"No se pudo cargar contexto de Obsidian: {e}")
    return base


def _classify_error_message(exc: Exception, provider: str = "IA") -> str:
    """Clasifica errores de red y HTTP en mensajes amigables en español."""
    msg = str(exc)
    if "401" in msg or "API_KEY" in msg or "authentication" in msg.lower() or "UNAUTHENTICATED" in msg:
        return f"La clave de API de {provider} es inválida o no está autorizada."
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower() or "rate limit" in msg.lower():
        return f"Límite de cuota o solicitudes alcanzado en {provider}."
    if "404" in msg or "not found" in msg.lower():
        return f"El modelo configurado en {provider} no fue encontrado o no está disponible."
    if "SAFETY" in msg or "safety" in msg.lower():
        return f"La respuesta fue bloqueada por filtros de seguridad de {provider}."
    if "WinError 10061" in msg or "Connection refused" in msg or "failed to connect" in msg.lower():
        return f"No se pudo conectar con el servidor local de {provider}. Verifica que esté en ejecución."
    if "timed out" in msg.lower() or "timeout" in msg.lower():
        return f"Tiempo de espera agotado al conectar con {provider}."
    return f"Error en {provider}: {msg[:140]}"


# ─────────────────────────────────────────────────────────────────────────────
#  CLIENTE OPENAI-COMPATIBLE UNIFICADO (REST)
# ─────────────────────────────────────────────────────────────────────────────

def _call_openai_compatible(
    endpoint: str,
    api_key: str | None,
    model: str,
    prompt: str,
    history: list[dict] | None = None,
    extra_headers: dict | None = None,
    timeout: int = 25,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """
    Ejecuta una petición estándar a cualquier API compatible con OpenAI /chat/completions.
    """
    system_instruction = _build_system_instruction(prompt)
    messages: list[dict[str, str]] = [{"role": "system", "content": system_instruction}]

    if history:
        turns = cfg.gemini_history_turns * 2
        for m in history[-turns:]:
            role = "assistant" if m.get("role") in ("model", "assistant") else "user"
            content = m.get("content", "")
            if content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": prompt})

    headers: dict[str, str] = {
        "Content-Type": "application/json",
    }
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    if extra_headers:
        headers.update(extra_headers)

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or cfg.gemini_max_tokens,
        "temperature": temperature if temperature is not None else cfg.gemini_temperature,
    }

    data = json.dumps(payload).encode("utf-8")
    request = _req.Request(endpoint, data=data, headers=headers, method="POST")  # noqa: S310

    try:
        with _req.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            body = json.loads(raw)
            choices = body.get("choices", [])
            if not choices:
                raise ValueError(f"El endpoint '{endpoint}' devolvió 'choices' vacío.")
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if not content or not content.strip():
                finish = choices[0].get("finish_reason", "unknown")
                raise ValueError(f"Respuesta vacía del modelo '{model}' (finish_reason={finish})")
            return content.strip()
    except urllib.error.HTTPError as he:
        try:
            err_body = he.read().decode("utf-8")
            err_json = json.loads(err_body)
            err_msg = err_json.get("error", {}).get("message", err_body[:200])
        except Exception:
            err_msg = str(he)
        raise RuntimeError(f"HTTP {he.code}: {err_msg}") from he
    except urllib.error.URLError as ue:
        raise RuntimeError(f"Fallo de conexión: {ue.reason}") from ue


# ─────────────────────────────────────────────────────────────────────────────
#  IMPLEMENTACIONES DE PROVEEDORES
# ─────────────────────────────────────────────────────────────────────────────

def ask_gemini(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Consulta a Google Gemini usando la clave configurada o entorno."""
    api_key = resolve_provider_key("gemini")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no está configurada")

    client = get_gemini_client()
    if client is not None:
        from google.genai import types
        system_instruction = _build_system_instruction(prompt)
        contents = []
        if history:
            for m in history:
                role = "user" if m["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        model = cfg.llm_gemini_model or cfg.gemini_model
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=cfg.gemini_max_tokens,
                    temperature=cfg.gemini_temperature,
                ),
            )
            text = response.text.strip()
            log.info(f"[Gemini] Respuesta obtenida ({len(text)} chars)")
            return text, f"Gemini ({model})"
        except Exception as exc:
            error_msg = _classify_error_message(exc, "Gemini")
            log.warning(f"[Gemini] Error: {exc}")
            raise RuntimeError(error_msg) from exc

    raise RuntimeError("No se pudo inicializar el cliente de Gemini.")


def ask_openai(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Consulta a OpenAI (ChatGPT)."""
    api_key = resolve_provider_key("openai")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no está configurada")
    model = cfg.llm_openai_model or "gpt-4o-mini"
    text = _call_openai_compatible(
        endpoint=OPENAI_ENDPOINT,
        api_key=api_key,
        model=model,
        prompt=prompt,
        history=history,
    )
    return text, f"OpenAI ({model})"


def ask_openrouter(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Consulta a OpenRouter con rotación defensiva de modelos."""
    api_key = resolve_provider_key("openrouter")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY no está configurada")

    configured_model = cfg.llm_openrouter_model
    models_to_try = [configured_model] if configured_model else []
    for m in OPENROUTER_FREE_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    extra_headers = {
        "HTTP-Referer": "https://darius-ai.local",
        "X-Title": "Darius AI Assistant",
    }

    last_err: Exception | None = None
    for model in models_to_try:
        try:
            text = _call_openai_compatible(
                endpoint=OPENROUTER_ENDPOINT,
                api_key=api_key,
                model=model,
                prompt=prompt,
                history=history,
                extra_headers=extra_headers,
                timeout=20,
            )
            return text, f"OpenRouter ({model})"
        except Exception as exc:
            log.warning(f"[OpenRouter] Modelo '{model}' falló: {exc}")
            last_err = exc
            continue

    raise RuntimeError(f"Todos los modelos de OpenRouter fallaron: {last_err}")


def ask_nvidia(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Consulta a NVIDIA NIM."""
    api_key = resolve_provider_key("nvidia")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY no está configurada")
    model = cfg.llm_nvidia_model or "meta/llama-3.1-70b-instruct"
    text = _call_openai_compatible(
        endpoint=NVIDIA_ENDPOINT,
        api_key=api_key,
        model=model,
        prompt=prompt,
        history=history,
    )
    return text, f"NVIDIA NIM ({model})"


def ask_groq(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Consulta a Groq Cloud."""
    api_key = resolve_provider_key("groq")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY no está configurada")
    model = cfg.llm_groq_model or "llama-3.3-70b-versatile"
    text = _call_openai_compatible(
        endpoint=GROQ_ENDPOINT,
        api_key=api_key,
        model=model,
        prompt=prompt,
        history=history,
    )
    return text, f"Groq ({model})"


def ask_ollama(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Consulta a Ollama local."""
    base_url = (cfg.llm_ollama_base_url or "http://localhost:11434/v1").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    model = cfg.llm_ollama_model or "llama3.2"
    text = _call_openai_compatible(
        endpoint=endpoint,
        api_key="ollama",
        model=model,
        prompt=prompt,
        history=history,
        timeout=45,
    )
    return text, f"Ollama ({model})"


def ask_custom(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """Consulta a un endpoint personalizado compatible con OpenAI."""
    base_url = (cfg.llm_custom_base_url or "http://localhost:1234/v1").rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    api_key = resolve_provider_key("custom")
    model = cfg.llm_custom_model or "local-model"
    text = _call_openai_compatible(
        endpoint=endpoint,
        api_key=api_key,
        model=model,
        prompt=prompt,
        history=history,
        timeout=45,
    )
    return text, f"Custom ({model})"


# ─────────────────────────────────────────────────────────────────────────────
#  DISPATCHER PRINCIPAL CON FALLBACK DEFENSIVO
# ─────────────────────────────────────────────────────────────────────────────

def get_ai_response(prompt: str, history: list[dict] | None = None) -> tuple[str, str]:
    """
    Ejecuta la consulta con el proveedor activo en BYOK.
    Si el proveedor principal falla y el fallback está activado, escala ordenadamente.
    """
    active = cfg.active_provider or "gemini"
    provider_callers = {
        "gemini": ask_gemini,
        "openai": ask_openai,
        "openrouter": ask_openrouter,
        "nvidia": ask_nvidia,
        "groq": ask_groq,
        "ollama": ask_ollama,
        "custom": ask_custom,
    }
    primary_fn = provider_callers.get(active, ask_gemini)

    try:
        return primary_fn(prompt, history)
    except Exception as primary_exc:
        log.warning(f"Proveedor principal '{active}' falló: {primary_exc}")

        if not cfg.llm_fallback_enabled:
            return _classify_error_message(primary_exc, active.upper()), "error"

        # Cadena de Fallback: intenta OpenRouter si hay clave configurada
        openrouter_key = resolve_provider_key("openrouter")
        if active != "openrouter" and openrouter_key:
            try:
                log.info("Intentando fallback con OpenRouter...")
                return ask_openrouter(prompt, history)
            except Exception as fb_exc:
                log.warning(f"Fallback OpenRouter falló: {fb_exc}")

        # Si aún falla, intenta Gemini si no era el activo
        gemini_key = resolve_provider_key("gemini")
        if active != "gemini" and gemini_key:
            try:
                log.info("Intentando fallback con Gemini...")
                return ask_gemini(prompt, history)
            except Exception as gemini_exc:
                log.warning(f"Fallback Gemini falló: {gemini_exc}")

        return _classify_error_message(primary_exc, active.upper()), "error"


# ─────────────────────────────────────────────────────────────────────────────
#  VERIFICACIÓN DE CONEXIÓN EN TIEMPO REAL (GUI TEST)
# ─────────────────────────────────────────────────────────────────────────────

def test_provider_connection(
    provider: str,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
) -> tuple[bool, str, float]:
    """
    Prueba en tiempo real la conectividad y autenticación con un proveedor.
    Retorna: (éxito: bool, mensaje_detalle: str, latencia_ms: float)
    """
    p = provider.lower().strip()
    effective_key = api_key.strip() or resolve_provider_key(p)
    test_prompt = "Responde únicamente: OK"
    start_t = time.perf_counter()

    try:
        if p == "gemini":
            if not effective_key:
                return False, "Falta la API Key de Gemini.", 0.0
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=effective_key)
            effective_model = model.strip() or cfg.llm_gemini_model or "gemini-3.6-flash"
            resp = client.models.generate_content(
                model=effective_model,
                contents=[{"role": "user", "parts": [{"text": test_prompt}]}],
                config=types.GenerateContentConfig(max_output_tokens=10, temperature=0.0),
            )
            _ = resp.text
        elif p == "openai":
            if not effective_key:
                return False, "Falta la API Key de OpenAI.", 0.0
            effective_model = model.strip() or "gpt-4o-mini"
            _call_openai_compatible(OPENAI_ENDPOINT, effective_key, effective_model, test_prompt, max_tokens=10)
        elif p == "openrouter":
            if not effective_key:
                return False, "Falta la API Key de OpenRouter.", 0.0
            effective_model = model.strip() or "google/gemma-3-27b-it:free"
            _call_openai_compatible(
                OPENROUTER_ENDPOINT,
                effective_key,
                effective_model,
                test_prompt,
                extra_headers={"HTTP-Referer": "https://darius-ai.local", "X-Title": "Darius Test"},
                max_tokens=10,
            )
        elif p == "nvidia":
            if not effective_key:
                return False, "Falta la API Key de NVIDIA NIM.", 0.0
            effective_model = model.strip() or "meta/llama-3.1-70b-instruct"
            _call_openai_compatible(NVIDIA_ENDPOINT, effective_key, effective_model, test_prompt, max_tokens=10)
        elif p == "groq":
            if not effective_key:
                return False, "Falta la API Key de Groq.", 0.0
            effective_model = model.strip() or "llama-3.3-70b-versatile"
            _call_openai_compatible(GROQ_ENDPOINT, effective_key, effective_model, test_prompt, max_tokens=10)
        elif p == "ollama":
            url = (base_url.strip() or "http://localhost:11434/v1").rstrip("/") + "/chat/completions"
            effective_model = model.strip() or "llama3.2"
            _call_openai_compatible(url, "ollama", effective_model, test_prompt, max_tokens=10, timeout=10)
        elif p == "custom":
            url = (base_url.strip() or "http://localhost:1234/v1").rstrip("/") + "/chat/completions"
            effective_model = model.strip() or "local-model"
            _call_openai_compatible(url, effective_key, effective_model, test_prompt, max_tokens=10, timeout=10)
        else:
            return False, f"Proveedor desconocido: '{provider}'", 0.0

        latency = (time.perf_counter() - start_t) * 1000.0
        return True, f"Conexión exitosa ({latency:.0f} ms)", latency

    except Exception as exc:
        latency = (time.perf_counter() - start_t) * 1000.0
        error_detail = _classify_error_message(exc, p.upper())
        return False, error_detail, latency
