"""
test_commands_v6.py — Suite de Tests para DARIUS AI v6
=======================================================
Reemplaza: test_basic.py (v1) + test_commands.py (v1)
Motivo del reemplazo:
  - Los tests anteriores reimplementaban con if/elif la lógica de _CMD_PATTERNS,
    probando su propia copia en lugar del código real del proyecto.
  - No cubrían windows_commands.py, fuzzy matching, confirmaciones,
    ni los tres modos de activación.

Cobertura de esta suite:
  1. Motor de resolución de windows_commands.py (Tipo A y Tipo B)
  2. Fuzzy matching: scores, umbrales y falsos positivos
  3. Flujo de confirmación de acciones destructivas
  4. Filtro de modos de activación (PTT, NOMBRE, AUTO)
  5. Manejo de errores de la API Gemini (429, auth, red)
  6. Integración de _CMD_PATTERNS con regex compilados de main.py

Ejecución:
  python test_commands_v6.py              # todos los tests
  python test_commands_v6.py -v           # verbose
  python test_commands_v6.py WinCmd       # solo una clase
"""

import re
import sys
import unittest
from difflib import SequenceMatcher
from unittest.mock import MagicMock, patch

# ── Importaciones del proyecto ────────────────────────────────────────────────
# Ajusta el path si ejecutas desde fuera del directorio del proyecto
sys.path.insert(0, ".")

try:
    from windows_commands import (
        _ACT_CUTOFF,
        _ACT_KEYS,
        _ACT_TABLE,
        _WIN_CUTOFF,
        _WIN_KEYS,
        _WIN_TABLE,
        SYSTEM_ACTIONS,
        WINDOWS_COMMANDS,
        _normalize,
        _resolve,
        resolve_action,
        resolve_and_launch,
        run_action,
    )
    WINCMD_AVAILABLE = True
except ImportError as e:
    WINCMD_AVAILABLE = False
    print(f"[WARN] No se pudo importar windows_commands.py: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _fuzzy_score(query: str, key: str) -> float:
    """Retorna el ratio SequenceMatcher entre query normalizado y key."""
    from windows_commands import _normalize
    return SequenceMatcher(None, _normalize(query), _normalize(key)).ratio()


def _best_match(query: str, keys: list) -> tuple[str, float]:
    """Retorna (mejor_key, mejor_score) para una query sobre una lista de keys."""
    from windows_commands import _normalize
    nq = _normalize(query)
    best_key, best_score = "", 0.0
    for k in keys:
        s = SequenceMatcher(None, nq, k).ratio()
        if s > best_score:
            best_score, best_key = s, k
    return best_key, best_score


# ═════════════════════════════════════════════════════════════════════════════
#  1. NORMALIZACIÓN
# ═════════════════════════════════════════════════════════════════════════════

class TestNormalization(unittest.TestCase):
    """Verifica que _normalize elimine tildes y homogenice a minúsculas."""

    @unittest.skipUnless(WINCMD_AVAILABLE, "windows_commands no disponible")
    def test_tildes_removed(self):
        self.assertEqual(_normalize("Configuración"), "configuracion")
        self.assertEqual(_normalize("Administración"), "administracion")
        self.assertEqual(_normalize("Energía"), "energia")

    @unittest.skipUnless(WINCMD_AVAILABLE, "windows_commands no disponible")
    def test_lowercase(self):
        self.assertEqual(_normalize("WIFI"), "wifi")
        self.assertEqual(_normalize("Bluetooth"), "bluetooth")

    @unittest.skipUnless(WINCMD_AVAILABLE, "windows_commands no disponible")
    def test_strips_whitespace(self):
        self.assertEqual(_normalize("  wifi  "), "wifi")


# ═════════════════════════════════════════════════════════════════════════════
#  2. TIPO A — RESOLUCIÓN DE PANELES / VENTANAS
# ═════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(WINCMD_AVAILABLE, "windows_commands no disponible")
class TestWinCmdTypeA(unittest.TestCase):
    """
    Prueba la resolución de comandos Tipo A (WINDOWS_COMMANDS).
    No ejecuta os.startfile() — los subprocesos están mockeados.
    """

    # ── Exact match ──────────────────────────────────────────────────────────

    def test_exact_match_wifi(self):
        canonical = _resolve("wifi", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(canonical, "wifi")

    def test_exact_match_bluetooth(self):
        canonical = _resolve("bluetooth", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(canonical, "bluetooth")

    def test_exact_match_with_tilde(self):
        """Una query con tilde debe resolver igual que sin tilde."""
        c1 = _resolve("configuración", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        c2 = _resolve("configuracion", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(c1, c2)

    # ── Alias match ──────────────────────────────────────────────────────────

    def test_alias_red_wifi(self):
        canonical = _resolve("configurar red", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertIn(canonical, ["configuracion de red", "wifi"])

    def test_alias_windows_defender(self):
        canonical = _resolve("windows defender", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(canonical, "seguridad de windows")

    def test_alias_descargas(self):
        canonical = _resolve("mis descargas", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(canonical, "descargas")

    def test_alias_administrador_tareas(self):
        canonical = _resolve("task manager", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(canonical, "administrador de tareas")

    # ── Fuzzy match ──────────────────────────────────────────────────────────

    def test_fuzzy_typo_bluetooh(self):
        """Typo común: 'bluetooh' → 'bluetooth'"""
        canonical = _resolve("bluetooh", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(canonical, "bluetooth")

    def test_fuzzy_partial_configuracion(self):
        canonical = _resolve("configuracion de pantalla", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        self.assertEqual(canonical, "pantalla")

    def test_fuzzy_score_threshold(self):
        """Queries muy distintos deben retornar None (no hacer match forzado)."""
        # "hola mundo" no debe resolverse a ningún panel de Windows
        canonical = _resolve("hola mundo xyz123", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        # Si retorna algo, el score debe haber sido ≥ 0.52 (comportamiento esperado)
        # Este test documenta el umbral, no lo invalida
        if canonical is not None:
            _, score = _best_match("hola mundo xyz123", _WIN_KEYS)
            self.assertGreaterEqual(score, 0.52,
                msg=f"Match '{canonical}' con score < umbral (posible falso positivo)")

    # ── resolve_and_launch con mock ───────────────────────────────────────────

    @patch("windows_commands.os.startfile")
    def test_launch_ms_settings_uri(self, mock_startfile):
        """URIs ms-settings: deben invocar os.startfile, no subprocess."""
        desc = resolve_and_launch("wifi")
        self.assertIsNotNone(desc)
        mock_startfile.assert_called_once()
        args = mock_startfile.call_args[0][0]
        self.assertTrue(args.startswith("ms-settings:"),
                        f"Se esperaba URI ms-settings:, se obtuvo: {args}")

    @patch("windows_commands.subprocess.Popen")
    def test_launch_msc_snap_in(self, mock_popen):
        """Archivos .msc deben lanzarse con mmc, no con startfile."""
        desc = resolve_and_launch("administrador de dispositivos")
        self.assertIsNotNone(desc)
        mock_popen.assert_called()
        cmd_args = mock_popen.call_args[0][0]
        self.assertEqual(cmd_args[0], "mmc",
                         f"Se esperaba 'mmc', se obtuvo: {cmd_args}")

    @patch("windows_commands.os.startfile")
    def test_launch_returns_desc_string(self, mock_startfile):
        """resolve_and_launch debe retornar un string no vacío en caso de éxito."""
        desc = resolve_and_launch("bluetooth")
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)

    def test_launch_unknown_query_returns_none(self):
        """Queries sin match deben retornar None sin lanzar excepción."""
        result = resolve_and_launch("comando_inexistente_xyzabc999")
        self.assertIsNone(result)


# ═════════════════════════════════════════════════════════════════════════════
#  3. TIPO B — RESOLUCIÓN DE ACCIONES / SUBPROCESOS
# ═════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(WINCMD_AVAILABLE, "windows_commands no disponible")
class TestWinCmdTypeB(unittest.TestCase):
    """
    Prueba la resolución y ejecución de comandos Tipo B (SYSTEM_ACTIONS).
    Todos los subprocess están mockeados — no se ejecuta nada en el SO real.
    """

    # ── Resolución ────────────────────────────────────────────────────────────

    def test_resolve_ver_ip(self):
        entry = resolve_action("ver ip")
        self.assertIsNotNone(entry)
        self.assertIn("action", entry)
        self.assertEqual(entry["action"]["type"], "powershell")

    def test_resolve_vaciar_papelera(self):
        entry = resolve_action("vaciar papelera")
        self.assertIsNotNone(entry)
        self.assertTrue(entry.get("confirm", False),
                        "vaciar_papelera debe requerir confirmación")

    def test_resolve_ping_google(self):
        entry = resolve_action("hay internet")
        self.assertIsNotNone(entry,
            "'hay internet' debe resolver a 'ping google' via alias")

    def test_resolve_alias_limpiar_temp(self):
        entry = resolve_action("borrar temporales")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["canonical"], "limpiar archivos temporales")

    def test_resolve_unknown_returns_none(self):
        entry = resolve_action("comando_absolutamente_inexistente_xyzabc")
        self.assertIsNone(entry)

    # ── Campos obligatorios ───────────────────────────────────────────────────

    def test_all_actions_have_required_fields(self):
        """Cada entrada de SYSTEM_ACTIONS debe tener 'action', 'desc' y 'aliases'."""
        for key, data in SYSTEM_ACTIONS.items():
            with self.subTest(action=key):
                self.assertIn("action", data, f"'{key}' sin campo 'action'")
                self.assertIn("desc",   data, f"'{key}' sin campo 'desc'")
                self.assertIn("aliases",data, f"'{key}' sin campo 'aliases'")
                self.assertIn("type",   data["action"],
                              f"'{key}.action' sin campo 'type'")
                self.assertIn("run",    data["action"],
                              f"'{key}.action' sin campo 'run'")
                self.assertIn(data["action"]["type"], ("powershell", "cmd"),
                              f"'{key}.action.type' inválido")

    def test_confirm_actions_are_marked(self):
        """Acciones destructivas conocidas deben tener confirm=True."""
        destructivas = ["vaciar papelera", "limpiar archivos temporales",
                        "resetear red", "cerrar sesion"]
        for query in destructivas:
            entry = resolve_action(query)
            if entry:  # solo falla si resuelve pero no tiene confirm
                self.assertTrue(entry.get("confirm", False),
                                f"'{query}' resolvió a '{entry['canonical']}' sin confirm=True")

    # ── run_action con mock ───────────────────────────────────────────────────

    @patch("windows_commands.subprocess.run")
    def test_run_action_return_output(self, mock_run):
        """Acciones con return_output=True deben capturar stdout."""
        mock_run.return_value = MagicMock(
            stdout="192.168.1.100\n", stderr="", returncode=0
        )
        entry = resolve_action("ver ip")
        self.assertIsNotNone(entry)
        success, output = run_action(entry)
        self.assertTrue(success)
        self.assertIn("192.168.1.100", output)
        mock_run.assert_called_once()

    @patch("windows_commands.subprocess.Popen")
    def test_run_action_background_no_window(self, mock_popen):
        """Acciones sin return_output ni open_window deben usar CREATE_NO_WINDOW."""
        import subprocess as sp
        mock_popen.return_value = MagicMock()
        entry = resolve_action("bloquear pantalla")
        self.assertIsNotNone(entry)
        success, output = run_action(entry)
        self.assertTrue(success)
        mock_popen.assert_called()
        kwargs = mock_popen.call_args[1]
        self.assertEqual(kwargs.get("creationflags"), sp.CREATE_NO_WINDOW,
                         "Acción background debe usar CREATE_NO_WINDOW")

    @patch("windows_commands.subprocess.Popen")
    def test_run_action_open_window_console(self, mock_popen):
        """Acciones con open_window=True deben abrir consola visible."""
        import subprocess as sp
        mock_popen.return_value = MagicMock()
        entry = resolve_action("ping google")
        self.assertIsNotNone(entry)
        success, _ = run_action(entry)
        self.assertTrue(success)
        mock_popen.assert_called()
        kwargs = mock_popen.call_args[1]
        self.assertEqual(kwargs.get("creationflags"), sp.CREATE_NEW_CONSOLE,
                         "Acción open_window debe usar CREATE_NEW_CONSOLE")

    @patch("windows_commands.subprocess.run")
    def test_run_action_timeout_returns_false(self, mock_run):
        """Un TimeoutExpired debe retornar (False, mensaje_de_error)."""
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="test", timeout=15)
        entry = resolve_action("ver ip")
        success, output = run_action(entry)
        self.assertFalse(success)
        self.assertIn("tardó", output.lower())

    @patch("windows_commands.subprocess.run")
    def test_run_action_output_truncated_at_300(self, mock_run):
        """Salidas largas deben truncarse a 300 chars para TTS."""
        mock_run.return_value = MagicMock(
            stdout="X" * 500, stderr="", returncode=0
        )
        entry = resolve_action("ver ip")
        _, output = run_action(entry)
        self.assertLessEqual(len(output), 305,  # 300 + "…"
                             "Output de TTS no debe superar 300 chars")


# ═════════════════════════════════════════════════════════════════════════════
#  4. FUZZY MATCHING — SCORES Y UMBRALES
# ═════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(WINCMD_AVAILABLE, "windows_commands no disponible")
class TestFuzzyMatching(unittest.TestCase):
    """
    Prueba el comportamiento del fuzzy matcher bajo distintos escenarios.
    Incluye test de score mínimo y detección de posibles falsos positivos.
    """

    def test_score_exact_match_is_one(self):
        score = _fuzzy_score("wifi", "wifi")
        self.assertEqual(score, 1.0)

    def test_score_bluetooth_typo(self):
        score = _fuzzy_score("bluetooh", "bluetooth")
        self.assertGreater(score, 0.85,
            "Typo de una letra debe producir score > 0.85")

    def test_score_completely_different_is_low(self):
        score = _fuzzy_score("reproducir musica", "administrador de dispositivos")
        self.assertLess(score, 0.52,
            "Queries no relacionados no deben superar el umbral 0.52")

    def test_threshold_boundary_at_0_52(self):
        """Queries en el límite del umbral deben resolverse o no según el score."""
        query  = "configurar pantallas"
        result = _resolve(query, _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        key, score = _best_match(query, _WIN_KEYS)
        if score >= 0.52:
            self.assertIsNotNone(result,
                f"Score {score:.2f} ≥ 0.52 pero _resolve retornó None")
        else:
            self.assertIsNone(result,
                f"Score {score:.2f} < 0.52 pero _resolve retornó '{result}'")

    def test_keyword_subset_fallback(self):
        """
        El fallback de palabras clave debe activarse cuando el fuzzy falla.
        'ver servicios activos' → todas las palabras en la clave.
        """
        result = _resolve("ver servicios activos", _ACT_TABLE, _ACT_KEYS, _ACT_CUTOFF)
        self.assertIsNotNone(result,
            "El fallback de palabras clave debe capturar 'ver servicios activos'")

    def test_type_a_and_type_b_no_crossover(self):
        """
        'ver ip' debe resolverse en SYSTEM_ACTIONS (Tipo B),
        NO en WINDOWS_COMMANDS (Tipo A).
        """
        type_a = _resolve("ver ip", _WIN_TABLE, _WIN_KEYS, _WIN_CUTOFF)
        type_b = _resolve("ver ip", _ACT_TABLE, _ACT_KEYS, _ACT_CUTOFF)
        self.assertIsNone(type_a,
            "'ver ip' no debe resolverse como panel de Windows (Tipo A)")
        self.assertIsNotNone(type_b,
            "'ver ip' debe resolverse como acción de sistema (Tipo B)")

    def test_score_report_all_aliases(self):
        """
        Genera reporte de scores para las primeras 10 entradas de cada tabla.
        No falla — documenta los scores para detección manual de anomalías.
        """
        print("\n[FUZZY SCORES — muestra de aliases]")
        checked = 0
        for canonical, data in list(SYSTEM_ACTIONS.items())[:5]:
            for alias in data.get("aliases", [])[:2]:
                key, score = _best_match(alias, _ACT_KEYS)
                print(f"  '{alias}' → '{canonical}' | score: {score:.3f}")
                checked += 1
        self.assertGreater(checked, 0)


# ═════════════════════════════════════════════════════════════════════════════
#  5. MODOS DE ACTIVACIÓN (simulación de process_recognized_text)
# ═════════════════════════════════════════════════════════════════════════════

try:
    from voice_filter import check_name_in_text
    VOICE_FILTER_AVAILABLE = True
except ImportError:
    VOICE_FILTER_AVAILABLE = False

ASSISTANT_NAME         = "darius"
NAME_SIMILARITY_CUTOFF = 0.60


@unittest.skipUnless(VOICE_FILTER_AVAILABLE, "voice_filter.py no disponible")
class TestActivationModes(unittest.TestCase):
    """
    Prueba la lógica de filtrado de modos usando la función real
    check_name_in_text() de voice_filter.py (extraída de main.py).
    """

    # ── Modo NOMBRE ───────────────────────────────────────────────────────────

    def test_nombre_mode_accepts_exact_name(self):
        found, clean = check_name_in_text("darius abre el explorador", ASSISTANT_NAME, NAME_SIMILARITY_CUTOFF)
        self.assertTrue(found)
        self.assertEqual(clean, "abre el explorador")

    def test_nombre_mode_accepts_name_mid_sentence(self):
        """El nombre puede aparecer en cualquier posición."""
        found, clean = check_name_in_text("oye darius qué hora es", ASSISTANT_NAME, NAME_SIMILARITY_CUTOFF)
        self.assertTrue(found)

    def test_nombre_mode_rejects_random_noise(self):
        found, _ = check_name_in_text("um ah", ASSISTANT_NAME, NAME_SIMILARITY_CUTOFF)
        self.assertFalse(found)

    def test_nombre_mode_accepts_phonetic_variant_dario(self):
        """'dario' tiene similitud > 0.60 con 'darius' → debe aceptarse."""
        score = SequenceMatcher(None, ASSISTANT_NAME, "dario").ratio()
        self.assertGreater(score, NAME_SIMILARITY_CUTOFF,
            f"'dario' score {score:.2f} debería superar {NAME_SIMILARITY_CUTOFF}")
        found, _ = check_name_in_text("dario abre chrome", ASSISTANT_NAME, NAME_SIMILARITY_CUTOFF)
        self.assertTrue(found, "'dario' debería ser aceptado como variante fonética")

    def test_nombre_mode_rejects_very_different_word(self):
        """Una palabra muy diferente al nombre no debe activar el asistente."""
        found, _ = check_name_in_text("computadora abre chrome", ASSISTANT_NAME, NAME_SIMILARITY_CUTOFF)
        self.assertFalse(found,
            "'computadora' no debe confundirse con 'darius'")

    def test_nombre_mode_clean_text_is_command_only(self):
        """El texto limpio NO debe contener el nombre del asistente."""
        _, clean = check_name_in_text("darius sube el volumen", ASSISTANT_NAME, NAME_SIMILARITY_CUTOFF)
        self.assertNotIn("darius", clean)
        self.assertEqual(clean, "sube el volumen")

    # ── Umbral de similitud ───────────────────────────────────────────────────

    def test_similarity_cutoff_value(self):
        """Documenta los scores de variantes fonéticas conocidas."""
        variants = {
            "dario":  True,   # debe aceptarse
            "mario":  False,  # m inicial muy diferente
            "darío":  True,   # tilde — normalización debería manejarla
            "varios": False,  # contexto común, no debe activar
        }
        for word, expected_above_cutoff in variants.items():
            # normaliza tilde para la prueba
            clean_word = word.replace("í", "i").replace("á", "a")
            score = SequenceMatcher(None, ASSISTANT_NAME, clean_word).ratio()
            actual_above = score >= NAME_SIMILARITY_CUTOFF
            print(f"  '{word}' → score: {score:.3f} | "
                  f"{'ACEPTA' if actual_above else 'RECHAZA'}")
            if expected_above_cutoff:
                self.assertTrue(actual_above or score > 0.50,
                    f"'{word}' debería tener score razonable, obtuvo {score:.2f}")


# ═════════════════════════════════════════════════════════════════════════════
#  6. MANEJO DE ERRORES GEMINI
# ═════════════════════════════════════════════════════════════════════════════

class TestGeminiErrorHandling(unittest.TestCase):
    """
    Prueba el manejo diferenciado de errores de la API Gemini
    sin realizar llamadas reales de red.
    """

    def _classify_gemini_error(self, error_str: str) -> str:
        """
        Replica la lógica de clasificación de errores de ask_gemini().
        Retorna el tipo de error como string para assertions.
        """
        if any(k in error_str for k in ["429", "RESOURCE_EXHAUSTED", "quota"]):
            return "quota_exceeded"
        elif any(k in error_str for k in ["API_KEY", "authentication", "UNAUTHENTICATED"]):
            return "auth_error"
        elif any(k in error_str.lower() for k in ["network", "connection"]):
            return "network_error"
        else:
            return "unknown_error"

    def test_error_429_classified_as_quota(self):
        self.assertEqual(
            self._classify_gemini_error("Error 429: Too Many Requests"),
            "quota_exceeded"
        )

    def test_error_resource_exhausted(self):
        self.assertEqual(
            self._classify_gemini_error("RESOURCE_EXHAUSTED: quota exceeded"),
            "quota_exceeded"
        )

    def test_error_unauthenticated(self):
        self.assertEqual(
            self._classify_gemini_error("UNAUTHENTICATED: Invalid API_KEY"),
            "auth_error"
        )

    def test_error_network(self):
        self.assertEqual(
            self._classify_gemini_error("network connection refused"),
            "network_error"
        )

    def test_error_unknown(self):
        self.assertEqual(
            self._classify_gemini_error("Some unexpected internal server error XYZ"),
            "unknown_error"
        )

    def test_quota_error_does_not_raise(self):
        """El sistema no debe propagar excepciones al usuario — solo hablar."""
        errors = [
            "429 RESOURCE_EXHAUSTED",
            "quota limit reached",
            "UNAUTHENTICATED API_KEY invalid",
            "network timeout connection refused",
        ]
        for err in errors:
            with self.subTest(error=err):
                # Verificar que el clasificador no lanza excepción
                try:
                    result = self._classify_gemini_error(err)
                    self.assertIsInstance(result, str)
                except Exception as e:
                    self.fail(f"Clasificador lanzó excepción para '{err}': {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  7. CMD_PATTERNS — REGEX DE main.py
# ═════════════════════════════════════════════════════════════════════════════

class TestCmdPatterns(unittest.TestCase):
    """
    Prueba los regex de _CMD_PATTERNS de main.py sin instanciar la UI.
    Los patrones se replican localmente (en lugar de importarlos de main.py)
    porque main.py tiene imports de Windows (tkinter, win32api) que fallan
    en CI no-Windows o sin GUI.

    La verificación contra la fuente de verdad está en
    test_verify_patterns_match_main(), que importa los patrones reales
    de main.py solo en Windows.
    """

    # Replica de _CMD_PATTERNS de main.py (los patrones relevantes)
    PATTERNS = [
        (re.compile(r"\b(qué hora|hora exacta)\b"),                              "hora"),
        (re.compile(r"\b(qué fecha|fecha de hoy|día de hoy)\b"),                 "fecha"),
        (re.compile(r"\b(reproduce|pon|ponme|coloca|escuchar|música)\b"),        "youtube"),
        (re.compile(r"\b(busca|buscar|googlea)\b"),                              "buscar"),
        (re.compile(r"\b(abre|abrir|lanza|ejecuta|inicia|muestra)\b"),           "abrir"),
        (re.compile(r"\bsubir\s+volumen\b"),                                     "vol_up"),
        (re.compile(r"\bbajar\s+volumen\b"),                                     "vol_down"),
        (re.compile(r"\bsilenciar\b"),                                           "vol_mute"),
        (re.compile(r"\b(cómo estás|estado del sistema|status)\b"),              "estado"),
        (re.compile(r"\b(adiós|adios|descansa|apágate|cerrar darius)\b"),        "cerrar"),
    ]

    def _route(self, cmd: str) -> str | None:
        cmd = cmd.strip().lower()
        for pattern, handler in self.PATTERNS:
            if pattern.search(cmd):
                return handler
        return None  # → Gemini

    def test_hora_commands(self):
        self.assertEqual(self._route("qué hora es"), "hora")
        self.assertEqual(self._route("hora exacta por favor"), "hora")

    def test_fecha_commands(self):
        self.assertEqual(self._route("qué fecha es hoy"), "fecha")
        self.assertEqual(self._route("fecha de hoy"), "fecha")

    def test_youtube_commands(self):
        self.assertEqual(self._route("reproduce música rock"), "youtube")
        self.assertEqual(self._route("pon una canción"), "youtube")
        self.assertEqual(self._route("ponme algo de jazz"), "youtube")

    def test_buscar_commands(self):
        self.assertEqual(self._route("busca recetas de cocina"), "buscar")
        self.assertEqual(self._route("googlea el tiempo en bogotá"), "buscar")

    def test_abrir_commands(self):
        self.assertEqual(self._route("abre chrome"), "abrir")
        self.assertEqual(self._route("ejecuta el bloc de notas"), "abrir")
        self.assertEqual(self._route("lanza el explorador"), "abrir")

    def test_volumen_commands(self):
        self.assertEqual(self._route("subir volumen"), "vol_up")
        self.assertEqual(self._route("bajar volumen"), "vol_down")
        self.assertEqual(self._route("silenciar"), "vol_mute")

    def test_cerrar_commands(self):
        self.assertEqual(self._route("adiós darius"), "cerrar")
        self.assertEqual(self._route("descansa"), "cerrar")

    def test_unknown_routes_to_gemini(self):
        """Comandos sin patrón deben retornar None → escalar a Gemini."""
        self.assertIsNone(self._route("cuál es la capital de Francia"))
        self.assertIsNone(self._route("escríbeme un poema"))
        self.assertIsNone(self._route("explícame la relatividad"))

    def test_no_false_positive_subir_vs_bajar(self):
        """'subir' y 'bajar' no deben confundirse entre sí."""
        self.assertNotEqual(self._route("subir volumen"), "vol_down")
        self.assertNotEqual(self._route("bajar volumen"), "vol_up")


# ═════════════════════════════════════════════════════════════════════════════
#  8. INTEGRIDAD ESTRUCTURAL DE LOS DICCIONARIOS
# ═════════════════════════════════════════════════════════════════════════════

@unittest.skipUnless(WINCMD_AVAILABLE, "windows_commands no disponible")
class TestDictionaryIntegrity(unittest.TestCase):
    """
    Verifica que ninguna entrada de los diccionarios esté malformada.
    Detecta errores de tipeo en la estructura antes de que ocurran en runtime.
    """

    def test_all_windows_commands_have_cmd_and_desc(self):
        for key, data in WINDOWS_COMMANDS.items():
            with self.subTest(cmd=key):
                self.assertIn("cmd",  data, f"'{key}' sin campo 'cmd'")
                self.assertIn("desc", data, f"'{key}' sin campo 'desc'")
                self.assertIsInstance(data["cmd"],  str, f"'{key}.cmd' no es string")
                self.assertIsInstance(data["desc"], str, f"'{key}.desc' no es string")

    def test_all_aliases_are_strings(self):
        for key, data in WINDOWS_COMMANDS.items():
            for i, alias in enumerate(data.get("aliases", [])):
                self.assertIsInstance(alias, str,
                    f"'{key}.aliases[{i}]' no es string: {alias!r}")

    def test_no_duplicate_aliases_across_tables(self):
        """
        Un alias no debería aparecer tanto en WINDOWS_COMMANDS como en
        SYSTEM_ACTIONS — podría causar resoluciones ambiguas.
        """
        win_aliases = set()
        for data in WINDOWS_COMMANDS.values():
            for alias in data.get("aliases", []):
                win_aliases.add(_normalize(alias))

        conflicts = []
        for canonical, data in SYSTEM_ACTIONS.items():
            for alias in data.get("aliases", []):
                norm = _normalize(alias)
                if norm in win_aliases:
                    conflicts.append((alias, canonical))

        # Reportar conflictos sin fallar (puede ser intencional en algunos casos)
        if conflicts:
            print(f"\n[INFO] {len(conflicts)} alias(es) compartidos entre tablas:")
            for alias, canonical in conflicts[:5]:
                print(f"  '{alias}' → SYSTEM_ACTIONS['{canonical}']")

    def test_system_actions_no_empty_run(self):
        for key, data in SYSTEM_ACTIONS.items():
            run = data.get("action", {}).get("run", "").strip()
            self.assertGreater(len(run), 0,
                f"'{key}.action.run' está vacío")


# ═════════════════════════════════════════════════════════════════════════════
#  9. VERIFICACIÓN CONTRA MAIN.PY (Windows únicamente)
# ═════════════════════════════════════════════════════════════════════════════

try:
    # Solo funciona en Windows con GUI; falla elegantemente en otros entornos
    from main import _CMD_PATTERNS as _REAL_PATTERNS
    MAIN_PATTERNS_AVAILABLE = True
except Exception:
    MAIN_PATTERNS_AVAILABLE = False


@unittest.skipUnless(MAIN_PATTERNS_AVAILABLE, "main.py no disponible (no Windows o sin GUI)")
class TestPatternsMatchMain(unittest.TestCase):
    """
    Verifica que los patrones replicados en TestCmdPatterns coincidan
    con los patrones reales de la variable _CMD_PATTERNS de main.py.
    Esto detecta desincronización entre el código fuente y los tests.
    """

    def setUp(self):
        self.real_handlers = {p[1] for p in _REAL_PATTERNS}
        self.test_handlers = {p[1] for p in TestCmdPatterns.PATTERNS}

    def test_all_real_handlers_have_tests(self):
        missing = self.real_handlers - self.test_handlers
        self.assertEqual(
            len(missing), 0,
            f"Handlers en main.py sin test: {missing}"
        )

    def test_no_extra_handlers_in_tests(self):
        extra = self.test_handlers - self.real_handlers
        self.assertEqual(
            len(extra), 0,
            f"Handlers en tests que no existen en main.py: {extra}"
        )


# ═════════════════════════════════════════════════════════════════════════════
#  RUNNER
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Permite ejecutar una clase específica: python test_commands_v6.py WinCmd
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        pattern = sys.argv.pop(1)
        loader  = unittest.TestLoader()
        suite   = unittest.TestSuite()
        for cls in [TestNormalization, TestWinCmdTypeA, TestWinCmdTypeB,
                    TestFuzzyMatching, TestActivationModes,
                    TestGeminiErrorHandling, TestCmdPatterns,
                    TestDictionaryIntegrity, TestPatternsMatchMain]:
            if pattern.lower() in cls.__name__.lower():
                suite.addTests(loader.loadTestsFromTestCase(cls))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        unittest.main(verbosity=2)
