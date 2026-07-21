"""
test_gemini_v6.py — Tests de Integración Gemini para DARIUS AI v6
==================================================================
Actualiza: test_gemini.py (diagnóstico básico sin manejo de errores)
Cambios:
  - Agrega pruebas de manejo diferenciado de errores (429, auth, red)
  - Verifica el límite de historial GEMINI_HISTORY_TURNS
  - Prueba la extracción de texto de la respuesta (response.text vs candidates)
  - Verifica que el system_instruction se aplica correctamente
  - Simula el formateo de respuesta (limpieza de markdown)

Ejecución:
  python test_gemini_v6.py              # todos los tests
  python test_gemini_v6.py --live       # incluye llamada real a la API
"""

import os
import re
import sys
import unittest
from unittest.mock import MagicMock

# ── Configuración ─────────────────────────────────────────────────────────────
GEMINI_MODEL         = "gemini-2.5-flash"
GEMINI_MAX_TOKENS    = 800
GEMINI_TEMPERATURE   = 0.7
GEMINI_HISTORY_TURNS = 10
ASSISTANT_NAME       = "darius"
USER_NAME            = "Oscar"


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS — réplicas de funciones de main.py
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text_from_response(response) -> str:
    """Réplica de la lógica de extracción de texto en ask_gemini()."""
    if hasattr(response, "text") and response.text:
        return response.text
    if hasattr(response, "candidates") and response.candidates:
        return response.candidates[0].content.parts[0].text
    return ""


def _clean_response_for_tts(text: str) -> str:
    """Réplica del post-proceso que elimina markdown para TTS."""
    return re.sub(r"[*_`#>]", "", text).strip()


def _classify_gemini_error(error: Exception) -> str:
    """Réplica de la lógica de clasificación de errores de ask_gemini()."""
    err = str(error)
    if any(k in err for k in ["429", "RESOURCE_EXHAUSTED", "quota"]):
        return "quota_exceeded"
    elif any(k in err for k in ["API_KEY", "authentication", "UNAUTHENTICATED"]):
        return "auth_error"
    elif any(k in err.lower() for k in ["network", "connection"]):
        return "network_error"
    else:
        return "unknown_error"


def _trim_history(history: list, max_turns: int) -> list:
    """Réplica del recorte de historial en ask_gemini()."""
    max_msgs = max_turns * 2
    if len(history) > max_msgs:
        return history[-max_msgs:]
    return history


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 1 — EXTRACCIÓN DE TEXTO DE RESPUESTA
# ─────────────────────────────────────────────────────────────────────────────

class TestResponseExtraction(unittest.TestCase):
    """
    Verifica la lógica de extracción de texto de distintos formatos
    de respuesta de la API Gemini (response.text vs candidates).
    """

    def test_extract_from_response_text_attribute(self):
        mock_response      = MagicMock()
        mock_response.text = "Hola, soy Darius."
        result = _extract_text_from_response(mock_response)
        self.assertEqual(result, "Hola, soy Darius.")

    def test_extract_from_candidates_fallback(self):
        """Cuando response.text es None/vacío, debe usar candidates."""
        mock_response      = MagicMock()
        mock_response.text = None
        mock_candidate     = MagicMock()
        mock_candidate.content.parts = [MagicMock(text="Respuesta desde candidates.")]
        mock_response.candidates = [mock_candidate]
        result = _extract_text_from_response(mock_response)
        self.assertEqual(result, "Respuesta desde candidates.")

    def test_extract_returns_empty_on_no_content(self):
        mock_response            = MagicMock()
        mock_response.text       = None
        mock_response.candidates = []
        result = _extract_text_from_response(mock_response)
        self.assertEqual(result, "")

    def test_response_text_has_priority_over_candidates(self):
        """response.text tiene prioridad — no debe acceder a candidates si text existe."""
        mock_response      = MagicMock()
        mock_response.text = "Texto directo."
        # Si accede a candidates, lanzaría excepción
        del mock_response.candidates
        try:
            result = _extract_text_from_response(mock_response)
            self.assertEqual(result, "Texto directo.")
        except AttributeError:
            self.fail("Accedió a candidates cuando response.text estaba disponible")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 2 — LIMPIEZA DE MARKDOWN PARA TTS
# ─────────────────────────────────────────────────────────────────────────────

class TestMarkdownCleanup(unittest.TestCase):
    """
    El TTS de DARIUS usa SAPI que no interpreta markdown.
    Verifica que la limpieza elimine todos los caracteres problemáticos.
    """

    def test_removes_bold_asterisks(self):
        result = _clean_response_for_tts("**Importante:** esto es **bold**")
        self.assertNotIn("*", result)
        self.assertIn("Importante", result)

    def test_removes_italic_underscores(self):
        result = _clean_response_for_tts("texto _italic_ aquí")
        self.assertNotIn("_", result)

    def test_removes_code_backticks(self):
        result = _clean_response_for_tts("usa `os.startfile()` para abrir")
        self.assertNotIn("`", result)

    def test_removes_headers(self):
        result = _clean_response_for_tts("# Título principal\n## Subtítulo")
        self.assertNotIn("#", result)

    def test_removes_blockquote(self):
        result = _clean_response_for_tts("> Esto es una cita")
        self.assertNotIn(">", result)

    def test_preserves_plain_text(self):
        text   = "Son las tres de la tarde."
        result = _clean_response_for_tts(text)
        self.assertEqual(result, text)

    def test_preserves_numbers_and_punctuation(self):
        text   = "La temperatura es 25°C. Batería: 80%."
        result = _clean_response_for_tts(text)
        self.assertIn("25", result)
        self.assertIn("80%", result)

    def test_strips_leading_trailing_whitespace(self):
        result = _clean_response_for_tts("   respuesta con espacios   ")
        self.assertEqual(result, "respuesta con espacios")


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 3 — MANEJO DE ERRORES DE API
# ─────────────────────────────────────────────────────────────────────────────

class TestGeminiErrorHandling(unittest.TestCase):
    """
    Prueba el clasificador de errores de ask_gemini().
    Cada tipo de error debe mapear a una respuesta TTS diferente.
    """

    def test_quota_error_429(self):
        e = Exception("Error 429 Too Many Requests")
        self.assertEqual(_classify_gemini_error(e), "quota_exceeded")

    def test_quota_error_resource_exhausted(self):
        e = Exception("RESOURCE_EXHAUSTED: quota exceeded for model")
        self.assertEqual(_classify_gemini_error(e), "quota_exceeded")

    def test_quota_error_lowercase_quota(self):
        e = Exception("quota limit reached for daily requests")
        self.assertEqual(_classify_gemini_error(e), "quota_exceeded")

    def test_auth_error_api_key(self):
        e = Exception("Invalid API_KEY provided")
        self.assertEqual(_classify_gemini_error(e), "auth_error")

    def test_auth_error_unauthenticated(self):
        e = Exception("UNAUTHENTICATED: Request had invalid authentication credentials")
        self.assertEqual(_classify_gemini_error(e), "auth_error")

    def test_network_error_connection(self):
        e = Exception("network connection refused: unable to reach api.google.com")
        self.assertEqual(_classify_gemini_error(e), "network_error")

    def test_network_error_timeout(self):
        e = Exception("Connection timeout while connecting to endpoint")
        self.assertEqual(_classify_gemini_error(e), "network_error")

    def test_unknown_error(self):
        e = Exception("Internal server error 500 — unexpected model state")
        self.assertEqual(_classify_gemini_error(e), "unknown_error")

    def test_all_classified_errors_return_string(self):
        """Ningún tipo de error debe propagar excepción — siempre retorna str."""
        errors = [
            Exception("429"),
            Exception("UNAUTHENTICATED"),
            Exception("network"),
            Exception("unknown xyz"),
            ValueError("model not found"),
            RuntimeError("unexpected"),
        ]
        for e in errors:
            with self.subTest(error=str(e)):
                result = _classify_gemini_error(e)
                self.assertIsInstance(result, str)
                self.assertGreater(len(result), 0)


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 4 — GESTIÓN DE HISTORIAL DE CONVERSACIÓN
# ─────────────────────────────────────────────────────────────────────────────

class TestConversationHistory(unittest.TestCase):
    """
    Verifica el manejo de la ventana de contexto conversacional.
    La lógica de recorte debe preservar los mensajes más recientes.
    """

    def _make_history(self, n_turns: int) -> list:
        """Genera n_turns turnos de conversación mock."""
        history = []
        for i in range(n_turns):
            history.append({"role": "user",  "parts": [{"text": f"Pregunta {i}"}]})
            history.append({"role": "model", "parts": [{"text": f"Respuesta {i}"}]})
        return history

    def test_history_not_trimmed_below_limit(self):
        history = self._make_history(5)  # 10 mensajes < 20 (límite)
        result  = _trim_history(history, GEMINI_HISTORY_TURNS)
        self.assertEqual(len(result), 10)

    def test_history_trimmed_at_limit(self):
        history = self._make_history(15)  # 30 mensajes > 20 (límite)
        result  = _trim_history(history, GEMINI_HISTORY_TURNS)
        self.assertEqual(len(result), GEMINI_HISTORY_TURNS * 2)

    def test_history_trim_preserves_most_recent(self):
        """El recorte debe conservar los mensajes MÁS RECIENTES."""
        history = self._make_history(15)
        result  = _trim_history(history, GEMINI_HISTORY_TURNS)
        last_original = history[-1]
        last_trimmed  = result[-1]
        self.assertEqual(last_original["parts"][0]["text"],
                         last_trimmed["parts"][0]["text"])

    def test_history_trim_discards_oldest(self):
        """El recorte debe DESCARTAR los mensajes más antiguos."""
        history = self._make_history(15)
        result  = _trim_history(history, GEMINI_HISTORY_TURNS)
        first_original = history[0]["parts"][0]["text"]
        texts_in_result = [m["parts"][0]["text"] for m in result]
        self.assertNotIn(first_original, texts_in_result,
                         "El mensaje más antiguo no debería estar en el historial recortado")

    def test_empty_history_not_trimmed(self):
        result = _trim_history([], GEMINI_HISTORY_TURNS)
        self.assertEqual(result, [])

    def test_history_entry_structure(self):
        """Cada entrada debe tener 'role' y 'parts' con estructura correcta."""
        history = self._make_history(1)
        for entry in history:
            self.assertIn("role",  entry)
            self.assertIn("parts", entry)
            self.assertIn(entry["role"], ("user", "model"))
            self.assertIsInstance(entry["parts"], list)
            self.assertIn("text", entry["parts"][0])


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 5 — SYSTEM INSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

class TestSystemInstruction(unittest.TestCase):
    """
    Verifica que el system_instruction cumpla los requisitos de comportamiento
    de DARIUS v6 antes de enviarlo a la API.
    """

    SYSTEM_INSTRUCTION = (
        f"Eres Darius, asistente de IA con personalidad futurista y directa. "
        f"El usuario se llama {USER_NAME}. "
        "Responde en español, conciso (máximo 3 oraciones), "
        "sin markdown, sin asteriscos, sin bullets. Solo texto plano."
    )

    def test_instruction_mentions_assistant_name(self):
        self.assertIn("Darius", self.SYSTEM_INSTRUCTION)

    def test_instruction_mentions_user_name(self):
        self.assertIn(USER_NAME, self.SYSTEM_INSTRUCTION)

    def test_instruction_requests_spanish(self):
        self.assertIn("español", self.SYSTEM_INSTRUCTION.lower())

    def test_instruction_prohibits_markdown(self):
        instr_lower = self.SYSTEM_INSTRUCTION.lower()
        self.assertTrue(
            "markdown" in instr_lower or "asteriscos" in instr_lower,
            "El system_instruction debe prohibir explícitamente markdown"
        )

    def test_instruction_requests_concise_response(self):
        self.assertTrue(
            "conciso" in self.SYSTEM_INSTRUCTION.lower()
            or "3 oración" in self.SYSTEM_INSTRUCTION.lower()
            or "máximo" in self.SYSTEM_INSTRUCTION.lower(),
            "El system_instruction debe solicitar respuestas concisas"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  TEST 6 — INTEGRACIÓN REAL CON LA API (opcional, requiere API key)
# ─────────────────────────────────────────────────────────────────────────────

class TestGeminiLiveIntegration(unittest.TestCase):
    """
    Tests de integración real con la API de Gemini.
    Solo se ejecutan si se pasa --live como argumento o si
    la variable de entorno DARIUS_RUN_LIVE_TESTS=1 está definida.

    ADVERTENCIA: Estos tests consumen cuota de la API.
    """

    @classmethod
    def setUpClass(cls):
        cls.run_live = (
            os.getenv("DARIUS_RUN_LIVE_TESTS", "0") == "1"
            or "--live" in sys.argv
        )
        cls.api_key  = os.getenv("GEMINI_API_KEY")

    def _skip_if_not_live(self):
        if not self.run_live:
            self.skipTest("Test live omitido (usa --live o DARIUS_RUN_LIVE_TESTS=1)")
        if not self.api_key:
            self.skipTest("GEMINI_API_KEY no configurada")

    def test_live_basic_response(self):
        self._skip_if_not_live()
        from google import genai
        from google.genai import types

        client   = genai.Client(api_key=self.api_key)
        config   = types.GenerateContentConfig(
            system_instruction="Eres Darius. Responde en español. Solo texto plano.",
            temperature=0.1,
            max_output_tokens=50,
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role": "user", "parts": [{"text": "Di hola brevemente."}]}],
            config=config,
        )
        text = _extract_text_from_response(response)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)
        print(f"\n[LIVE] Respuesta: '{text}'")

    def test_live_response_has_no_markdown(self):
        """La respuesta real no debería contener markdown dado el system_instruction."""
        self._skip_if_not_live()
        from google import genai
        from google.genai import types

        client   = genai.Client(api_key=self.api_key)
        config   = types.GenerateContentConfig(
            system_instruction=(
                "Responde SOLO en texto plano. Sin asteriscos, "
                "sin bullets, sin markdown de ningún tipo."
            ),
            temperature=0.1,
            max_output_tokens=100,
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role": "user", "parts": [{"text": "¿Qué es Python?"}]}],
            config=config,
        )
        text = _extract_text_from_response(response)
        # Advertencia (no falla) si aparece markdown — depende del modelo
        if any(c in text for c in ["*", "#", "`", "_"]):
            print(f"\n[WARN] Respuesta contiene markdown a pesar del system_instruction: '{text[:100]}'")

    def test_live_error_handling_bad_key(self):
        """Una API key inválida debe clasificarse como auth_error."""
        self._skip_if_not_live()
        from google import genai

        client = genai.Client(api_key="INVALID_KEY_FOR_TESTING")
        try:
            client.models.generate_content(
                model=GEMINI_MODEL,
                contents="test",
            )
            self.fail("Se esperaba excepción con API key inválida")
        except Exception as e:
            error_type = _classify_gemini_error(e)
            self.assertEqual(error_type, "auth_error",
                f"API key inválida debería clasificar como 'auth_error', obtuvo: '{error_type}' ({e})")


# ─────────────────────────────────────────────────────────────────────────────
#  RUNNER
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Filtrar --live de sys.argv antes de pasarlo a unittest
    if "--live" in sys.argv:
        sys.argv.remove("--live")
        os.environ["DARIUS_RUN_LIVE_TESTS"] = "1"
        print("[INFO] Modo --live activado: se ejecutarán tests de integración real.")
        print(f"[INFO] API Key presente: {bool(os.getenv('GEMINI_API_KEY'))}\n")

    unittest.main(verbosity=2)
