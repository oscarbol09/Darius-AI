"""
debug_inspector_v6.py — Inspector de Diagnóstico para DARIUS AI v6
===================================================================
Reemplaza: debug_responses.py (v1/v2)
Motivo del reemplazo:
  - debug_responses.py simulaba os.system('nircmd.exe ...') cuando v6 usa pycaw.
  - No tenía conocimiento de windows_commands.py, modos de activación,
    fuzzy matching scores ni del worker TTS con queue.
  - Su función simulate_talk() era una copia desactualizada de _insert_message().

Este inspector provee:
  1. Resolución detallada con scores de fuzzy matching (Tipo A y Tipo B)
  2. Simulación del filtro de modos de activación (PTT/NOMBRE/AUTO)
  3. Reporte de la ruta de despacho de un comando (local → wincmd → Gemini)
  4. Diagnóstico de estado del entorno (API key, micrófono, pycaw, keyboard)
  5. Benchmark de resolución sobre el corpus completo de aliases

Uso:
  python debug_inspector_v6.py                      # menú interactivo
  python debug_inspector_v6.py "ver ip"             # inspeccionar un comando
  python debug_inspector_v6.py --env                # diagnóstico de entorno
  python debug_inspector_v6.py --bench              # benchmark de resolución
  python debug_inspector_v6.py --mode NOMBRE "darius abre chrome"
"""

import argparse
import datetime
import os
import re
import time
from difflib import SequenceMatcher

# ── Colores ANSI para terminal ────────────────────────────────────────────────
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA= "\033[95m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Constantes replicadas de main.py ─────────────────────────────────────────
ASSISTANT_NAME         = "darius"
NAME_SIMILARITY_CUTOFF = 0.60
MIN_WORDS_WITHOUT_NAME = 99

LISTEN_MODE_PTT   = "PTT"
LISTEN_MODE_NAME  = "NOMBRE"
LISTEN_MODE_AUTO  = "AUTO"

# ── Importar módulo de comandos ───────────────────────────────────────────────
try:
    from windows_commands import (
        _ACT_KEYS,
        _ACT_TABLE,
        _WIN_KEYS,
        _WIN_TABLE,
        SYSTEM_ACTIONS,
        WINDOWS_COMMANDS,
        _normalize,
        _resolve,
        resolve_action,
    )
    WINCMD_OK = True
except ImportError as e:
    WINCMD_OK = False
    print(f"{RED}[ERROR] No se pudo importar windows_commands.py: {e}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
#  SECCIÓN 1 — RESOLUCIÓN CON SCORE DETALLADO
# ─────────────────────────────────────────────────────────────────────────────

def _compute_all_scores(query: str, table: dict, keys: list) -> list[tuple[str, float]]:
    """
    Calcula el score SequenceMatcher de `query` contra todos los keys.
    Retorna lista de (key, score) ordenada de mayor a menor.
    """
    nq = _normalize(query)
    scores = [(k, SequenceMatcher(None, nq, k).ratio()) for k in keys]
    return sorted(scores, key=lambda x: x[1], reverse=True)


def inspect_command(query: str, top_n: int = 5) -> dict:
    """
    Inspecciona cómo se resolvería `query` en el sistema v6.

    Retorna un dict con:
      - route:       "type_a" | "type_b" | "gemini" | "local_pattern"
      - canonical:   clave canónica en la tabla (si aplica)
      - score:       float (0.0–1.0) del mejor match en fuzzy
      - match_type:  "exact" | "fuzzy" | "keyword" | "none"
      - top_matches: lista de (key, score) con los mejores candidatos
      - action_type: "powershell" | "cmd" | None
      - requires_confirm: bool
      - desc:        str descripción amigable
    """
    result = {
        "query":            query,
        "route":            "gemini",
        "canonical":        None,
        "score":            0.0,
        "match_type":       "none",
        "top_matches_a":    [],
        "top_matches_b":    [],
        "action_type":      None,
        "requires_confirm": False,
        "desc":             "",
        "cmd":              None,
    }

    if not WINCMD_OK:
        return result

    # ── Top scores de ambas tablas ────────────────────────────────────────────
    result["top_matches_a"] = _compute_all_scores(query, _WIN_TABLE, _WIN_KEYS)[:top_n]
    result["top_matches_b"] = _compute_all_scores(query, _ACT_TABLE, _ACT_KEYS)[:top_n]

    # ── Determinar el mejor score global ─────────────────────────────────────
    best_a = result["top_matches_a"][0][1] if result["top_matches_a"] else 0.0
    best_b = result["top_matches_b"][0][1] if result["top_matches_b"] else 0.0
    result["score"] = max(best_a, best_b)

    # ── Intentar resolver en Tipo B primero (acciones tienen prioridad en _cmd_accion)
    entry_b = resolve_action(query)
    if entry_b:
        result["route"]            = "type_b"
        result["canonical"]        = entry_b["canonical"]
        result["action_type"]      = entry_b["action"]["type"]
        result["requires_confirm"] = entry_b.get("confirm", False)
        result["desc"]             = entry_b["desc"]
        result["match_type"]       = _detect_match_type(query, entry_b["canonical"], _ACT_TABLE, _ACT_KEYS)
        return result

    # ── Intentar resolver en Tipo A
    res_a = _resolve(query, _WIN_TABLE, _WIN_KEYS)
    if res_a:
        data = WINDOWS_COMMANDS[res_a]
        result["route"]      = "type_a"
        result["canonical"]  = res_a
        result["cmd"]        = data["cmd"]
        result["desc"]       = data["desc"]
        result["match_type"] = _detect_match_type(query, res_a, _WIN_TABLE, _WIN_KEYS)
        return result

    # ── Fallback: Gemini
    result["route"] = "gemini"
    return result


def _detect_match_type(query: str, canonical: str, table: dict, keys: list) -> str:
    """Determina si el match fue exacto, fuzzy o por palabras clave."""
    nq = _normalize(query)
    if nq in table and table[nq] == canonical:
        return "exact"
    words = set(nq.split())
    canonical_norm = _normalize(canonical)
    if len(words) >= 2 and all(w in canonical_norm for w in words):
        return "keyword"
    return "fuzzy"


# ─────────────────────────────────────────────────────────────────────────────
#  SECCIÓN 2 — SIMULACIÓN DE MODOS DE ACTIVACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def simulate_activation_filter(text: str, mode: str) -> dict:
    """
    Simula process_recognized_text() de main.py para los tres modos.

    Retorna:
      - accepted:    bool — ¿el texto pasaría el filtro?
      - clean_text:  str  — texto resultante tras extraer el nombre
      - name_found:  bool
      - similarity:  float — score de la primera palabra vs ASSISTANT_NAME
      - reason:      str   — explicación del resultado
    """
    words = text.split()
    result = {
        "input_text":  text,
        "mode":        mode,
        "accepted":    False,
        "clean_text":  text,
        "name_found":  False,
        "similarity":  0.0,
        "reason":      "",
    }

    if mode == LISTEN_MODE_AUTO:
        result["accepted"] = True
        if ASSISTANT_NAME in text:
            result["name_found"] = True
            result["clean_text"] = text.replace(ASSISTANT_NAME, "").strip()
            result["reason"]     = "AUTO: acepta todo; nombre eliminado del texto"
        elif words:
            sim = SequenceMatcher(None, ASSISTANT_NAME, words[0]).ratio()
            result["similarity"] = sim
            if sim > NAME_SIMILARITY_CUTOFF:
                result["name_found"] = True
                result["clean_text"] = " ".join(words[1:]).strip()
                result["reason"]     = f"AUTO: variante fonética '{words[0]}' (score {sim:.2f})"
            else:
                result["reason"] = "AUTO: texto procesado sin nombre"
        return result

    elif mode == LISTEN_MODE_NAME:
        if ASSISTANT_NAME in text:
            result["accepted"]   = True
            result["name_found"] = True
            result["clean_text"] = text.replace(ASSISTANT_NAME, "").strip()
            result["reason"]     = "NOMBRE: nombre exacto encontrado"
            return result
        if words:
            sim = SequenceMatcher(None, ASSISTANT_NAME, words[0]).ratio()
            result["similarity"] = sim
            if sim >= NAME_SIMILARITY_CUTOFF:
                result["accepted"]   = True
                result["name_found"] = True
                result["clean_text"] = " ".join(words[1:]).strip()
                result["reason"]     = (f"NOMBRE: variante '{words[0]}' "
                                        f"aceptada (score {sim:.2f} ≥ {NAME_SIMILARITY_CUTOFF})")
            else:
                result["accepted"] = False
                result["reason"]   = (f"NOMBRE: descartado — '{words[0] if words else text}' "
                                      f"score {sim:.2f} < {NAME_SIMILARITY_CUTOFF}")
        else:
            result["reason"] = "NOMBRE: texto vacío descartado"
        return result

    elif mode == LISTEN_MODE_PTT:
        # En PTT el nombre no se exige — siempre acepta
        result["accepted"] = True
        if ASSISTANT_NAME in text:
            result["name_found"] = True
            result["clean_text"] = text.replace(ASSISTANT_NAME, "").strip()
        result["reason"] = "PTT: siempre acepta (usuario decidió presionar la tecla)"
        return result

    result["reason"] = f"Modo desconocido: {mode}"
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  SECCIÓN 3 — DIAGNÓSTICO DE ENTORNO
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_environment() -> dict:
    """
    Verifica el estado de todas las dependencias críticas de DARIUS AI v6.
    No arranca la UI — solo comprueba importabilidad y variables de entorno.
    """
    checks = {}

    # Variables de entorno
    checks["GEMINI_API_KEY"] = {
        "ok":    bool(os.getenv("GEMINI_API_KEY")),
        "value": "✓ presente" if os.getenv("GEMINI_API_KEY") else "✗ AUSENTE — sys.exit(1) al arrancar",
        "critical": True,
    }
    checks["PORCUPINE_ACCESS_KEY"] = {
        "ok":    bool(os.getenv("PORCUPINE_ACCESS_KEY")),
        "value": "✓ presente" if os.getenv("PORCUPINE_ACCESS_KEY") else "— no configurada (opcional)",
        "critical": False,
    }

    # Dependencias Python
    deps = [
        ("speech_recognition", True,  "STT — Google Speech API"),
        ("win32com.client",     True,  "SAPI TTS + COM"),
        ("win32event",          True,  "Mutex instancia única"),
        ("customtkinter",       True,  "UI framework"),
        ("numpy",               True,  "Animación de ondas"),
        ("google.genai",        True,  "SDK Gemini"),
        ("keyboard",            False, "Modo PTT (requiere admin)"),
        ("pycaw",               False, "Control de volumen nativo"),
        ("pvporcupine",         False, "Wake-word hardware (opcional)"),
        ("pyaudio",             True,  "Captura de audio"),
        ("pyttsx3",             False, "OBSOLETO — no usar en v6"),
    ]

    for mod, critical, description in deps:
        try:
            __import__(mod)
            ok    = True
            value = "✓ instalado"
            # Advertencia especial para pyttsx3
            if mod == "pyttsx3":
                value = "⚠ instalado pero OBSOLETO en v6 — eliminar de requirements.txt"
                ok    = False
        except ImportError:
            ok    = False
            value = "✗ no instalado" + (" — requerido" if critical else " (opcional)")

        checks[mod] = {"ok": ok, "value": value, "critical": critical,
                       "description": description}

    # Micrófono disponible
    try:
        import speech_recognition as sr
        mics = sr.Microphone.list_microphone_names()
        checks["microphone"] = {
            "ok":    len(mics) > 0,
            "value": f"✓ {len(mics)} dispositivo(s) detectado(s)" if mics else "✗ Sin micrófono",
            "critical": True,
            "description": "Dispositivos de entrada de audio",
        }
    except Exception as e:
        checks["microphone"] = {
            "ok": False, "value": f"✗ Error: {e}",
            "critical": True, "description": "Dispositivos de entrada de audio",
        }

    return checks


# ─────────────────────────────────────────────────────────────────────────────
#  SECCIÓN 4 — BENCHMARK DE RESOLUCIÓN
# ─────────────────────────────────────────────────────────────────────────────

def run_benchmark() -> dict:
    """
    Ejecuta el motor de resolución sobre todos los aliases del corpus.
    Mide tiempo de resolución y detecta aliases que fallen el round-trip.
    """
    if not WINCMD_OK:
        return {"error": "windows_commands no disponible"}

    results = {
        "total_aliases_a":    0,
        "total_aliases_b":    0,
        "failed_roundtrip_a": [],
        "failed_roundtrip_b": [],
        "avg_time_ms_a":      0.0,
        "avg_time_ms_b":      0.0,
    }

    # Tipo A
    times_a = []
    for canonical, data in WINDOWS_COMMANDS.items():
        for alias in data.get("aliases", []):
            results["total_aliases_a"] += 1
            t0  = time.perf_counter()
            res = _resolve(alias, _WIN_TABLE, _WIN_KEYS)
            elapsed = (time.perf_counter() - t0) * 1000
            times_a.append(elapsed)
            if res != canonical:
                results["failed_roundtrip_a"].append({
                    "alias":    alias,
                    "expected": canonical,
                    "got":      res,
                })

    results["avg_time_ms_a"] = sum(times_a) / len(times_a) if times_a else 0

    # Tipo B
    times_b = []
    for canonical, data in SYSTEM_ACTIONS.items():
        for alias in data.get("aliases", []):
            results["total_aliases_b"] += 1
            t0  = time.perf_counter()
            res = _resolve(alias, _ACT_TABLE, _ACT_KEYS)
            elapsed = (time.perf_counter() - t0) * 1000
            times_b.append(elapsed)
            if res != canonical:
                results["failed_roundtrip_b"].append({
                    "alias":    alias,
                    "expected": canonical,
                    "got":      res,
                })

    results["avg_time_ms_b"] = sum(times_b) / len(times_b) if times_b else 0
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  SECCIÓN 5 — DESPACHO COMPLETO (replica main.py sin UI)
# ─────────────────────────────────────────────────────────────────────────────

# Replica de _CMD_PATTERNS de main.py
_CMD_PATTERNS_LOCAL = [
    (re.compile(r"\b(qué hora|hora exacta)\b"),                              "hora"),
    (re.compile(r"\b(qué fecha|fecha de hoy|día de hoy)\b"),                 "fecha"),
    (re.compile(r"\b(nueva conversación|olvida todo|resetea la memoria)\b"), "reset"),
    (re.compile(r"\b(reproduce|pon|ponme|coloca|escuchar|música)\b"),        "youtube"),
    (re.compile(r"\b(busca|buscar|googlea)\b"),                              "buscar"),
    (re.compile(r"\b(abre|abrir|lanza|ejecuta|inicia|muestra)\b"),           "abrir"),
    (re.compile(r"\bsubir\s+volumen\b"),                                     "vol_up"),
    (re.compile(r"\bbajar\s+volumen\b"),                                     "vol_down"),
    (re.compile(r"\bsilenciar\b"),                                           "vol_mute"),
    (re.compile(r"\b(cómo estás|estado del sistema|status)\b"),              "estado"),
    (re.compile(r"\b(adiós|adios|descansa|apágate|cerrar darius)\b"),        "cerrar"),
    (re.compile(r"\bapagar\s+el\s+equipo\b"),                                "apagar_pc"),
    (re.compile(
        r"\b(ver|muéstrame|consulta|corre|haz|limpia|vacía|vaciar|limpiar|"
        r"diagnostica|diagnosticar|renueva|renovar|resetea|resetear|"
        r"desconecta|desconectar|activa|desactiva|bloquea|suspende|hiberna|"
        r"cierra\s+sesion|resumen|cuanto|cuanta|cual es|hay internet|"
        r"cuánto|cuánta|cuál es)\b"
    ), "accion"),
]


def trace_dispatch(cmd: str) -> dict:
    """
    Traza el camino completo de despacho de un comando en main.py.
    Retorna el handler activado y el contexto de resolución.
    """
    cmd_clean = cmd.strip().lower()
    trace     = {"input": cmd, "local_handler": None, "wincmd_result": None,
                 "final_route": "gemini", "pattern_matched": None}

    for pattern, handler in _CMD_PATTERNS_LOCAL:
        if pattern.search(cmd_clean):
            trace["local_handler"]  = handler
            trace["pattern_matched"] = pattern.pattern
            if handler == "accion" and WINCMD_OK:
                trace["wincmd_result"] = inspect_command(cmd)
                if trace["wincmd_result"]["route"] != "gemini":
                    trace["final_route"] = trace["wincmd_result"]["route"]
                else:
                    trace["final_route"] = "gemini"
            elif handler == "abrir" and WINCMD_OK:
                trace["wincmd_result"] = inspect_command(cmd)
                trace["final_route"]   = trace["wincmd_result"]["route"]
            else:
                trace["final_route"] = f"local:{handler}"
            return trace

    # Sin patrón → inspección directa en wincmd por si acaso
    if WINCMD_OK:
        trace["wincmd_result"] = inspect_command(cmd)
        if trace["wincmd_result"]["route"] != "gemini":
            trace["final_route"] = trace["wincmd_result"]["route"]

    return trace


# ─────────────────────────────────────────────────────────────────────────────
#  IMPRESIÓN FORMATEADA
# ─────────────────────────────────────────────────────────────────────────────

def print_inspection_report(query: str, mode: str = LISTEN_MODE_AUTO):
    """Imprime un reporte completo de inspección para una query."""
    print(f"\n{'═'*65}")
    print(f"{BOLD}{CYAN}  DARIUS AI v6 — Inspector de Diagnóstico{RESET}")
    print(f"{'═'*65}")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{DIM}  {ts}{RESET}")

    # ── Filtro de modo ────────────────────────────────────────────────────────
    filter_result = simulate_activation_filter(query, mode)
    mode_color    = {
        LISTEN_MODE_PTT:  YELLOW,
        LISTEN_MODE_NAME: CYAN,
        LISTEN_MODE_AUTO: DIM,
    }.get(mode, RESET)

    print(f"\n  {BOLD}MODO DE ACTIVACIÓN:{RESET} {mode_color}{mode}{RESET}")
    status_icon = f"{GREEN}✓ ACEPTADO{RESET}" if filter_result["accepted"] else f"{RED}✗ DESCARTADO{RESET}"
    print(f"  Input:      {BOLD}'{query}'{RESET}")
    print(f"  Estado:     {status_icon}")
    print(f"  Razón:      {DIM}{filter_result['reason']}{RESET}")
    if filter_result["similarity"] > 0:
        sim = filter_result["similarity"]
        sim_color = GREEN if sim >= NAME_SIMILARITY_CUTOFF else RED
        print(f"  Similitud:  {sim_color}{sim:.4f}{RESET} (umbral: {NAME_SIMILARITY_CUTOFF})")
    if filter_result["name_found"]:
        print(f"  Texto limpio: {BOLD}'{filter_result['clean_text']}'{RESET}")

    if not filter_result["accepted"]:
        print(f"\n  {YELLOW}⚑ El comando fue descartado por el filtro de modo.{RESET}")
        print("  No se realiza resolución de comandos.")
        print(f"{'─'*65}\n")
        return

    # ── Traza de despacho ─────────────────────────────────────────────────────
    effective_query = filter_result["clean_text"] or query
    trace           = trace_dispatch(effective_query)

    print(f"\n  {BOLD}DESPACHO DE COMANDO{RESET}")
    print(f"  Query efectiva:  {BOLD}'{effective_query}'{RESET}")
    if trace["pattern_matched"]:
        print(f"  Regex activado:  {DIM}{trace['pattern_matched'][:60]}...{RESET}"
              if len(trace["pattern_matched"]) > 60
              else f"  Regex activado:  {DIM}{trace['pattern_matched']}{RESET}")
        print(f"  Handler local:   {MAGENTA}{trace['local_handler']}{RESET}")

    route_colors = {
        "type_a": GREEN,
        "type_b": CYAN,
        "gemini": YELLOW,
    }
    final_color = route_colors.get(
        trace["final_route"].split(":")[0] if ":" in trace["final_route"]
        else trace["final_route"],
        RESET
    )
    print(f"  Ruta final:      {final_color}{BOLD}{trace['final_route'].upper()}{RESET}")

    # ── Detalle de resolución wincmd ──────────────────────────────────────────
    wincmd = trace.get("wincmd_result") or (inspect_command(effective_query) if WINCMD_OK else None)
    if wincmd and wincmd["route"] != "gemini":
        print(f"\n  {BOLD}RESOLUCIÓN windows_commands.py{RESET}")
        print(f"  Tipo:       {GREEN if wincmd['route']=='type_a' else CYAN}"
              f"{'TIPO A (Panel/URI)' if wincmd['route']=='type_a' else 'TIPO B (Subproceso)'}{RESET}")
        print(f"  Canónico:   {BOLD}'{wincmd['canonical']}'{RESET}")
        print(f"  Descripción:{wincmd['desc']}")
        print(f"  Match:      {wincmd['match_type'].upper()}")

        score_color = GREEN if wincmd["score"] >= 0.80 else \
                      YELLOW if wincmd["score"] >= 0.52 else RED
        print(f"  Score:      {score_color}{BOLD}{wincmd['score']:.4f}{RESET} "
              f"{DIM}(umbral mínimo: 0.52){RESET}")

        if wincmd["route"] == "type_a" and wincmd["cmd"]:
            print(f"  Comando:    {DIM}{wincmd['cmd']}{RESET}")
        if wincmd["route"] == "type_b":
            at = wincmd.get("action_type", "?")
            print(f"  Exec type:  {MAGENTA}{at}{RESET}")
            if wincmd.get("requires_confirm"):
                print(f"  {YELLOW}⚠ REQUIERE CONFIRMACIÓN VERBAL{RESET}")

    elif WINCMD_OK:
        print(f"\n  {YELLOW}→ Sin match en windows_commands — escalando a Gemini{RESET}")

    # ── Top matches ───────────────────────────────────────────────────────────
    if WINCMD_OK and wincmd:
        print(f"\n  {BOLD}TOP 5 CANDIDATOS — Tipo A (WINDOWS_COMMANDS){RESET}")
        for key, score in wincmd.get("top_matches_a", [])[:5]:
            bar   = "█" * int(score * 20)
            color = GREEN if score >= 0.80 else YELLOW if score >= 0.52 else RED
            print(f"    {color}{score:.3f}{RESET} {bar:<20} {DIM}{key}{RESET}")

        print(f"\n  {BOLD}TOP 5 CANDIDATOS — Tipo B (SYSTEM_ACTIONS){RESET}")
        for key, score in wincmd.get("top_matches_b", [])[:5]:
            bar   = "█" * int(score * 20)
            color = GREEN if score >= 0.80 else YELLOW if score >= 0.52 else RED
            print(f"    {color}{score:.3f}{RESET} {bar:<20} {DIM}{key}{RESET}")

    print(f"{'─'*65}\n")


def print_environment_report():
    """Imprime el reporte de estado del entorno."""
    checks = diagnose_environment()
    print(f"\n{'═'*65}")
    print(f"{BOLD}{CYAN}  DARIUS AI v6 — Diagnóstico de Entorno{RESET}")
    print(f"{'═'*65}\n")

    print(f"  {BOLD}Variables de Entorno:{RESET}")
    for name in ["GEMINI_API_KEY", "PORCUPINE_ACCESS_KEY"]:
        c = checks[name]
        icon = GREEN + "✓" if c["ok"] else RED + "✗"
        print(f"    {icon}{RESET} {name:<30} {c['value']}")

    print(f"\n  {BOLD}Dependencias Python:{RESET}")
    for name, c in checks.items():
        if name in ("GEMINI_API_KEY", "PORCUPINE_ACCESS_KEY", "microphone"):
            continue
        icon  = GREEN + "✓" if c["ok"] else (RED + "✗" if c.get("critical") else YELLOW + "—")
        desc  = c.get("description", "")
        print(f"    {icon}{RESET} {name:<25} {c['value']:<35} {DIM}{desc}{RESET}")

    print(f"\n  {BOLD}Hardware:{RESET}")
    mic = checks.get("microphone", {})
    icon = GREEN + "✓" if mic.get("ok") else RED + "✗"
    print(f"    {icon}{RESET} {'Micrófono':<25} {mic.get('value', '—')}")

    critical_fails = [k for k, v in checks.items()
                      if not v["ok"] and v.get("critical")]
    if critical_fails:
        print(f"\n  {RED}{BOLD}⛔ Dependencias críticas faltantes: {', '.join(critical_fails)}{RESET}")
        print(f"  {RED}   DARIUS AI no puede iniciar correctamente.{RESET}")
    else:
        print(f"\n  {GREEN}{BOLD}✓ Entorno apto para ejecutar DARIUS AI v6{RESET}")

    print(f"{'─'*65}\n")


def print_benchmark_report():
    """Imprime el reporte de benchmark del motor de resolución."""
    print(f"\n{'═'*65}")
    print(f"{BOLD}{CYAN}  DARIUS AI v6 — Benchmark del Motor de Resolución{RESET}")
    print(f"{'═'*65}\n")

    if not WINCMD_OK:
        print(f"  {RED}windows_commands.py no disponible{RESET}")
        return

    print("  Ejecutando round-trip sobre todos los aliases...\n")
    t0     = time.perf_counter()
    report = run_benchmark()
    total  = time.perf_counter() - t0

    print(f"  {BOLD}TIPO A — WINDOWS_COMMANDS{RESET}")
    passed_a = report["total_aliases_a"] - len(report["failed_roundtrip_a"])
    print(f"    Total aliases:   {report['total_aliases_a']}")
    print(f"    ✓ Pasaron:       {GREEN}{passed_a}{RESET}")
    print(f"    ✗ Fallaron:      {RED if report['failed_roundtrip_a'] else GREEN}{len(report['failed_roundtrip_a'])}{RESET}")  # noqa: E501
    print(f"    Tiempo promedio: {report['avg_time_ms_a']:.4f} ms/alias")

    if report["failed_roundtrip_a"]:
        print(f"\n    {YELLOW}Aliases con round-trip fallido:{RESET}")
        for f in report["failed_roundtrip_a"][:10]:
            print(f"      '{f['alias']}' → esperado '{f['expected']}', obtuvo '{f['got']}'")

    print(f"\n  {BOLD}TIPO B — SYSTEM_ACTIONS{RESET}")
    passed_b = report["total_aliases_b"] - len(report["failed_roundtrip_b"])
    print(f"    Total aliases:   {report['total_aliases_b']}")
    print(f"    ✓ Pasaron:       {GREEN}{passed_b}{RESET}")
    print(f"    ✗ Fallaron:      {RED if report['failed_roundtrip_b'] else GREEN}{len(report['failed_roundtrip_b'])}{RESET}")  # noqa: E501
    print(f"    Tiempo promedio: {report['avg_time_ms_b']:.4f} ms/alias")

    if report["failed_roundtrip_b"]:
        print(f"\n    {YELLOW}Aliases con round-trip fallido:{RESET}")
        for f in report["failed_roundtrip_b"][:10]:
            print(f"      '{f['alias']}' → esperado '{f['expected']}', obtuvo '{f['got']}'")

    total_pass = passed_a + passed_b
    total_all  = report["total_aliases_a"] + report["total_aliases_b"]
    pct        = (total_pass / total_all * 100) if total_all > 0 else 0
    color      = GREEN if pct >= 95 else YELLOW if pct >= 85 else RED

    print(f"\n  {BOLD}RESULTADO GLOBAL{RESET}")
    print(f"    {color}{total_pass}/{total_all} ({pct:.1f}%) aliases resuelven correctamente{RESET}")
    print(f"    Tiempo total del benchmark: {total*1000:.1f} ms")
    print(f"{'─'*65}\n")


def interactive_menu():
    """Menú interactivo para explorar el inspector sin argumentos CLI."""
    print(f"\n{BOLD}{CYAN}  ╔══════════════════════════════════════╗")
    print("  ║   DARIUS AI v6 — Debug Inspector    ║")
    print(f"  ╚══════════════════════════════════════╝{RESET}\n")
    print("  Comandos disponibles:")
    print(f"    {GREEN}[1]{RESET} Inspeccionar un comando")
    print(f"    {GREEN}[2]{RESET} Diagnóstico de entorno")
    print(f"    {GREEN}[3]{RESET} Benchmark de resolución")
    print(f"    {GREEN}[q]{RESET} Salir\n")

    while True:
        try:
            choice = input(f"  {CYAN}>{RESET} ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cerrando inspector.")
            break

        if choice == "1":
            query = input("  Comando a inspeccionar: ").strip()
            if not query:
                continue
            print("  Modo de activación [PTT/NOMBRE/AUTO] (Enter = AUTO): ", end="")
            mode_input = input().strip().upper()
            mode = mode_input if mode_input in (LISTEN_MODE_PTT, LISTEN_MODE_NAME, LISTEN_MODE_AUTO) \
                   else LISTEN_MODE_AUTO
            print_inspection_report(query, mode)

        elif choice == "2":
            print_environment_report()

        elif choice == "3":
            print_benchmark_report()

        elif choice in ("q", "quit", "salir", "exit"):
            print(f"  {DIM}Inspector cerrado.{RESET}\n")
            break
        else:
            print(f"  {YELLOW}Opción no reconocida.{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DARIUS AI v6 — Debug Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python debug_inspector_v6.py "ver ip"
  python debug_inspector_v6.py --mode NOMBRE "darius abre chrome"
  python debug_inspector_v6.py --mode PTT "sube el volumen"
  python debug_inspector_v6.py --env
  python debug_inspector_v6.py --bench
        """
    )
    parser.add_argument("query",   nargs="?", help="Comando a inspeccionar")
    parser.add_argument("--mode",  default="AUTO",
                        choices=["PTT", "NOMBRE", "AUTO"],
                        help="Modo de activación a simular (default: AUTO)")
    parser.add_argument("--env",   action="store_true", help="Diagnóstico de entorno")
    parser.add_argument("--bench", action="store_true", help="Benchmark de resolución")

    args = parser.parse_args()

    if args.env:
        print_environment_report()
    elif args.bench:
        print_benchmark_report()
    elif args.query:
        print_inspection_report(args.query, args.mode)
    else:
        interactive_menu()
