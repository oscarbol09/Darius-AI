"""
app.py — Darius AI · Interfaz web con Streamlit
================================================
Punto de entrada para Railway (contenedor Linux).
Conecta con Gemini (google-genai) y hace fallback automático
a OpenRouter si Gemini falla o no está disponible.

Comparte datos con main.py (escritorio) vía Supabase: historial de chat
(tabla chat_history) y configuración (tabla config). Ver supabase_client.py.

Arranque local:
    streamlit run app.py

Arranque en Railway (start command):
    python -m streamlit run app.py --server.port $PORT --server.address 0.0.0.0
"""

from __future__ import annotations

import logging
import os

import requests
import streamlit as st
from dotenv import load_dotenv

from config_loader import cfg
from supabase_client import get_supabase

# ── Carga de variables de entorno ─────────────────────────────────────────────
load_dotenv()

GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_KEY   = os.getenv("OPENROUTER_API_KEY", "")

# ── Configuración base ─────────────────────────────────────────────────────────
# Importada desde config_loader.py, que comparte defaults con main.py.
# Prioridad: Supabase (tabla `config`) > config.json local > defaults.
ASSISTANT_NAME   = cfg.assistant_name
USER_NAME        = cfg.user_name
GEMINI_MODEL     = cfg.gemini_model
MAX_TOKENS       = cfg.gemini_max_tokens
TEMPERATURE      = cfg.gemini_temperature
HISTORY_TURNS    = cfg.gemini_history_turns

OPENROUTER_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
OPENROUTER_URL   = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = (
    f"Eres {ASSISTANT_NAME}, un asistente de inteligencia artificial "
    "amigable, conciso y preciso. Respondes siempre en el idioma del usuario. "
    "Evitas respuestas excesivamente largas a menos que el tema lo requiera."
)

log = logging.getLogger("DARIUS_WEB")

# ─────────────────────────────────────────────────────────────────────────────
#  CLIENTES DE IA
# ─────────────────────────────────────────────────────────────────────────────

def _build_gemini_history(messages: list[dict]) -> list[dict]:
    """Convierte el historial de st.session_state al formato que espera Gemini."""
    history = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        history.append({"role": role, "parts": [{"text": m["content"]}]})
    return history


def call_gemini(user_text: str, history: list[dict]) -> str:
    """Llama a Gemini usando la librería google-genai. Retorna el texto de respuesta."""
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types

        client = google_genai.Client(api_key=GEMINI_API_KEY)

        # Construimos el historial previo (sin el mensaje actual)
        chat_history = _build_gemini_history(history)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=chat_history + [{"role": "user", "parts": [{"text": user_text}]}],
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            ),
        )
        return response.text.strip()
    except Exception as exc:
        log.warning("Gemini falló: %s", exc)
        raise


def call_openrouter(user_text: str, history: list[dict]) -> str:
    """Llama a OpenRouter como fallback. Retorna el texto de respuesta."""
    if not OPENROUTER_KEY:
        raise ValueError("OPENROUTER_API_KEY no está configurada.")

    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history[-HISTORY_TURNS * 2:]:
        messages_payload.append({"role": m["role"], "content": m["content"]})
    messages_payload.append({"role": "user", "content": user_text})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://darius-ai.local",
        "X-Title": "Darius AI",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages_payload,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def get_ai_response(user_text: str, history: list[dict]) -> tuple[str, str]:
    """
    Intenta Gemini primero; si falla, usa OpenRouter.
    Retorna (respuesta, proveedor_usado).
    """
    if GEMINI_API_KEY:
        try:
            return call_gemini(user_text, history), "Gemini"
        except Exception:
            log.warning("Gemini falló, usando OpenRouter como fallback")

    if OPENROUTER_KEY:
        try:
            return call_openrouter(user_text, history), "OpenRouter"
        except Exception as exc:
            return f"⚠️ Error al conectar con la IA: {exc}", "error"

    return (
        "⚠️ No hay claves de API configuradas. "
        "Configura GEMINI_API_KEY o OPENROUTER_API_KEY en las variables de entorno.",
        "error",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  INTERFAZ STREAMLIT
# ─────────────────────────────────────────────────────────────────────────────

def setup_page():
    st.set_page_config(
        page_title="Darius AI",
        page_icon="🤖",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    # CSS personalizado para un look más limpio
    st.markdown(
        """
        <style>
        /* Fondo principal */
        .stApp { background-color: #0f1117; }

        /* Título centrado */
        .darius-title {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 700;
            background: linear-gradient(90deg, #6c63ff, #48c9b0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
        }
        .darius-subtitle {
            text-align: center;
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 1.5rem;
        }

        /* Burbujas de chat */
        .chat-bubble-user {
            background: #1e3a5f;
            border-radius: 18px 18px 4px 18px;
            padding: 10px 16px;
            margin: 6px 0;
            max-width: 80%;
            margin-left: auto;
            color: #e8f0fe;
            font-size: 0.95rem;
        }
        .chat-bubble-ai {
            background: #1a1d2e;
            border: 1px solid #2d2f45;
            border-radius: 18px 18px 18px 4px;
            padding: 10px 16px;
            margin: 6px 0;
            max-width: 80%;
            color: #e0e0e0;
            font-size: 0.95rem;
        }
        .chat-meta {
            font-size: 0.72rem;
            color: #555;
            margin-top: 2px;
        }
        .provider-badge {
            font-size: 0.68rem;
            color: #48c9b0;
            margin-left: 6px;
        }

        /* Ocultar header por defecto de Streamlit */
        header[data-testid="stHeader"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _row_to_role(speaker: str) -> str:
    """Mapea el campo `speaker` de chat_history (texto libre) a role user/assistant."""
    return "assistant" if speaker.strip().lower() in (
        ASSISTANT_NAME.lower(), "assistant", "darius", "sistema"
    ) else "user"


def _load_shared_history(limit: int = 100) -> list[dict]:
    """
    Carga el historial compartido (desktop + web) desde Supabase, más reciente
    al final, para que la web muestre la misma conversación que main.py.
    Devuelve [] si Supabase no está disponible (modo local, como antes).
    """
    sb = get_supabase()
    if not sb:
        return []
    try:
        resp = (
            sb.table("chat_history")
            .select("speaker, message, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = list(reversed(resp.data or []))
        return [
            {"role": _row_to_role(r["speaker"]), "content": r["message"]}
            for r in rows
        ]
    except Exception as exc:
        log.warning("No se pudo cargar historial compartido desde Supabase: %s", exc)
        return []


def _push_message_to_supabase(role: str, content: str):
    """Inserta un mensaje en chat_history (source='web'). Best-effort."""
    sb = get_supabase()
    if not sb:
        return
    speaker = ASSISTANT_NAME if role == "assistant" else USER_NAME
    try:
        sb.table("chat_history").insert({
            "source":  "web",
            "speaker": speaker,
            "message": content,
        }).execute()
    except Exception as exc:
        log.warning("No se pudo sincronizar mensaje web con Supabase: %s", exc)


def init_session():
    """Inicializa el estado de la sesión. Si es la primera carga y Supabase
    está disponible, precarga el historial compartido con main.py."""
    if "messages" not in st.session_state:
        st.session_state.messages = _load_shared_history()
    if "thinking" not in st.session_state:
        st.session_state.thinking = False


def render_header():
    st.markdown('<div class="darius-title">🤖 Darius AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="darius-subtitle">Asistente de inteligencia artificial · Gemini + OpenRouter</div>',
        unsafe_allow_html=True,
    )


def render_chat_history():
    """Renderiza el historial de mensajes como burbujas."""
    if not st.session_state.messages:
        st.markdown(
            "<p style='text-align:center; color:#444; margin-top:3rem;'>"
            "👋 Hola, soy <strong>Darius</strong>. ¿En qué puedo ayudarte hoy?</p>",
            unsafe_allow_html=True,
        )
        return

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="chat-bubble-user">{msg["content"]}</div>'
                f'<div class="chat-meta" style="text-align:right;">Tú</div>',
                unsafe_allow_html=True,
            )
        else:
            provider_badge = ""
            if "provider" in msg:
                provider_badge = f'<span class="provider-badge">via {msg["provider"]}</span>'
            st.markdown(
                f'<div class="chat-bubble-ai">{msg["content"]}</div>'
                f'<div class="chat-meta">Darius {provider_badge}</div>',
                unsafe_allow_html=True,
            )


def render_input_area():
    """Renderiza el formulario de entrada del usuario."""
    st.markdown("---")

    col1, col2 = st.columns([5, 1])

    with col1:
        user_input = st.text_input(
            label="Mensaje",
            placeholder="Escribe tu mensaje aquí…",
            label_visibility="collapsed",
            key="user_input_field",
        )
    with col2:
        send_btn = st.button("Enviar", use_container_width=True, type="primary")

    # Botón para limpiar el historial
    if st.session_state.messages and st.button("🗑️ Limpiar conversación", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    return user_input, send_btn


def handle_send(user_input: str):
    """Procesa el mensaje del usuario y obtiene la respuesta de la IA."""
    if not user_input.strip():
        return

    # Guardamos el mensaje del usuario (local + Supabase, source='web')
    st.session_state.messages.append({"role": "user", "content": user_input.strip()})
    _push_message_to_supabase("user", user_input.strip())

    # Historial previo (sin el último mensaje que acabamos de agregar)
    previous_history = st.session_state.messages[:-1]

    with st.spinner("Darius está pensando…"):
        response_text, provider = get_ai_response(user_input.strip(), previous_history)

    # Guardamos la respuesta del asistente (local + Supabase, source='web')
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text, "provider": provider}
    )
    _push_message_to_supabase("assistant", response_text)

    # Forzamos re-render para mostrar el nuevo mensaje
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def main():
    setup_page()
    init_session()
    render_header()

    # Área de historial
    chat_container = st.container()
    with chat_container:
        render_chat_history()

    # Área de input
    user_input, send_btn = render_input_area()

    # Disparador: botón o Enter (el text_input devuelve valor al presionar Enter)
    if send_btn or (user_input and user_input != st.session_state.get("_last_input", "")):
        st.session_state["_last_input"] = user_input
        handle_send(user_input)


if __name__ == "__main__":
    main()
