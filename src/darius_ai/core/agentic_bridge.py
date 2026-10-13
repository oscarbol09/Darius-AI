"""
agentic_bridge.py — Motor de Automatización Autónoma y CLI Bridge para DARIUS AI
===============================================================================
Permite a Darius interactuar directamente con herramientas del sistema operativo Windows
y utilidades de desarrollo (PowerShell, GitHub CLI 'gh', Git, diagnósticos de red).

Soporta:
  1. Ejecución hermética y segura de comandos con timeouts y limitación de salida.
  2. Detección y clasificación de acciones seguras (diagnósticos/lectura) vs. destructivas.
  3. Formateo y sintetización de salidas de consola para respuestas auditivas naturales.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from typing import Any

log = logging.getLogger("DARIUS.AgenticBridge")

# Límite máximo de salida de texto para evitar saturar el contexto de la IA o el TTS
MAX_OUTPUT_CHARS = 3000

# Palabras clave y comandos clasificados como destructivos o modificadores
DESTRUCTIVE_KEYWORDS = {
    "merge",
    "delete",
    "remove",
    "drop",
    "destroy",
    "format",
    "reboot",
    "shutdown",
    "kill",
    "stop-process",
    "clear-recyclebin",
    "push --force",
    "reset --hard",
    "clean -fdx",
    "branch -d",
    "branch -D",
    "pr merge",
    "pr close",
    "rmdir /s",
    "del /f",
    "del /s",
    "rm -rf",
}


def is_destructive(action_text: str) -> bool:
    """Evalúa si una acción o comando propuesto es potencialmente destructivo."""
    norm = action_text.lower().strip()
    return any(k in norm for k in DESTRUCTIVE_KEYWORDS)


class AgenticBridge:
    """Puente de ejecución para herramientas locales y CLIs activos."""

    def __init__(self):
        self._windir = os.environ.get("SYSTEMROOT", "C:\\Windows")
        self._powershell = os.path.join(self._windir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        self._cmd = os.path.join(self._windir, "System32", "cmd.exe")
        self._gh_path = shutil.which("gh") or shutil.which("gh.exe")
        self._git_path = shutil.which("git") or shutil.which("git.exe")

    def execute_powershell(self, command: str, timeout: int = 8) -> tuple[bool, str]:
        """
        Ejecuta un script o comando en PowerShell de forma no interactiva y segura.
        Retorna (éxito: bool, salida_o_error: str).
        """
        if not os.path.exists(self._powershell):
            return False, "PowerShell no está disponible en la ruta estándar del sistema."

        try:
            res = subprocess.run(  # noqa: S603
                [self._powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                output = stdout or "Comando ejecutado sin salida."
                return True, output[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Código de salida: {res.returncode}")[:MAX_OUTPUT_CHARS]
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s) al ejecutar comando PowerShell."
        except Exception as exc:
            log.error(f"Error al ejecutar PowerShell: {exc}")
            return False, str(exc)

    def execute_cmd(self, command: str, timeout: int = 8) -> tuple[bool, str]:
        """Ejecuta un comando en CMD de Windows."""
        try:
            res = subprocess.run(  # noqa: S603
                f"{self._cmd} /c {command}",
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                return True, (stdout or "Comando ejecutado con éxito.")[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Error {res.returncode}")[:MAX_OUTPUT_CHARS]
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s)."
        except Exception as exc:
            return False, str(exc)

    def execute_gh(self, args: str | list[str], timeout: int = 10) -> tuple[bool, str]:
        """
        Ejecuta GitHub CLI ('gh').
        Ejemplos de args:
          - 'pr list --repo oscarbol09/branchbase'
          - 'repo view oscarbol09/Darius-AI'
          - 'issue list'
        """
        gh_bin = self._gh_path or "gh"
        args_list = [a.strip() for a in args.split() if a.strip()] if isinstance(args, str) else list(args)

        # Prevenir ejecución vacía
        if not args_list:
            return False, "No se especificaron argumentos para GitHub CLI."

        try:
            res = subprocess.run(  # noqa: S603
                [gh_bin, *args_list],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                output = stdout or "Consulta de GitHub completada (sin resultados o vacía)."
                return True, output[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Error gh code {res.returncode}")[:MAX_OUTPUT_CHARS]
        except FileNotFoundError:
            return False, "GitHub CLI (gh) no está instalado o no se encuentra en el PATH."
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s) al consultar GitHub CLI."
        except Exception as exc:
            log.error(f"Error en gh cli: {exc}")
            return False, str(exc)

    def execute_git(self, command: str | list[str], repo_path: str = "", timeout: int = 8) -> tuple[bool, str]:
        """Ejecuta un comando de Git localmente."""
        git_bin = self._git_path or "git"
        if isinstance(command, str):
            cmd_list = [c.strip() for c in command.split() if c.strip()]
            if cmd_list and cmd_list[0] == "git":
                cmd_list = cmd_list[1:]
        else:
            cmd_list = list(command)

        cwd = repo_path if repo_path and os.path.isdir(repo_path) else os.getcwd()

        try:
            res = subprocess.run(  # noqa: S603
                [git_bin, *cmd_list],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            if res.returncode == 0:
                return True, (stdout or "Git ejecutado con éxito.")[:MAX_OUTPUT_CHARS]
            return False, (stderr or stdout or f"Error git code {res.returncode}")[:MAX_OUTPUT_CHARS]
        except FileNotFoundError:
            return False, "Git no está instalado o no se encuentra en el PATH."
        except subprocess.TimeoutExpired:
            return False, f"Tiempo de espera agotado ({timeout}s) al ejecutar Git."
        except Exception as exc:
            return False, str(exc)

    def flush_dns(self) -> tuple[bool, str]:
        """Limpia y vacía la caché de resolución DNS de Windows."""
        return self.execute_cmd("ipconfig /flushdns")

    def get_top_processes(self, count: int = 5) -> tuple[bool, str]:
        """Consulta los procesos que más memoria RAM están consumiendo en Windows."""
        ps_cmd = (
            f"Get-Process | Sort-Object WorkingSet64 -Descending | "
            f"Select-Object -First {count} ProcessName, @{{N='RAM_MB';E={{[math]::Round($_.WorkingSet64/1MB,1)}}}} | "
            f"Format-Table -AutoSize | Out-String"
        )
        return self.execute_powershell(ps_cmd)

    def get_system_summary(self) -> tuple[bool, str]:
        """Obtiene un diagnóstico rápido de CPU, RAM libre y espacio en disco."""
        ps_cmd = (
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$freeRam = [math]::Round($os.FreePhysicalMemory / 1024, 1); "
            "$totalRam = [math]::Round($os.TotalVisibleMemorySize / 1024, 1); "
            "$disk = Get-PSDrive C; "
            "$freeDisk = [math]::Round($disk.Free / 1GB, 1); "
            'Write-Output "RAM: $freeRam MB libres de $totalRam MB | Disco C: $freeDisk GB libres"'
        )
        return self.execute_powershell(ps_cmd)

    def human_mouse_move(self, x: int, y: int) -> tuple[bool, str]:
        """Mueve el ratón suavemente con física de curva de Bézier."""
        try:
            from src.darius_ai.gui.human_gui import gui

            gui.human_mouse_move(x, y)
            return True, f"Ratón movido a ({x}, {y})."
        except Exception as exc:
            return False, f"Error al mover ratón: {exc}"

    def human_click(
        self,
        x: int | None = None,
        y: int | None = None,
        button: str = "left",
        double: bool = False,
    ) -> tuple[bool, str]:
        """Ejecuta un clic o doble clic con duraciones humanas."""
        try:
            from src.darius_ai.gui.human_gui import gui

            gui.human_click(x=x, y=y, button=button, double=double)
            action_name = "Doble clic" if double else f"Clic {button}"
            coord_str = f" en ({x}, {y})" if x is not None and y is not None else ""
            return True, f"{action_name}{coord_str} completado."
        except Exception as exc:
            return False, f"Error al hacer clic: {exc}"

    def human_type(self, text: str, wpm: int = 70) -> tuple[bool, str]:
        """Escribe texto en pantalla con cadencia mecanográfica humana."""
        try:
            from src.darius_ai.gui.human_gui import gui

            gui.human_type(text, wpm=wpm)
            preview = text[:30] + ("..." if len(text) > 30 else "")
            return True, f"Texto escrito ({len(text)} caracteres): '{preview}'"
        except Exception as exc:
            return False, f"Error al escribir: {exc}"

    def human_hotkey(self, keys: str) -> tuple[bool, str]:
        """Presiona una combinación de teclas (ej: 'ctrl+c', 'win+r')."""
        try:
            from src.darius_ai.gui.human_gui import gui

            key_list = [k.strip() for k in re.split(r"[,+\s]+", keys) if k.strip()]
            gui.human_hotkey(*key_list)
            return True, f"Atajo ejecutado: {' + '.join(key_list)}"
        except Exception as exc:
            return False, f"Error al presionar atajo: {exc}"

    def scrape_web(self, url: str) -> tuple[bool, str]:
        """Descarga y extrae el texto limpio de una página web en segundo plano con validación SSRF."""
        try:
            from src.darius_ai.core.security_guard import AntiSSRFValidator

            safe, msg = AntiSSRFValidator.is_safe_url(url)
            if not safe:
                return False, f"URL bloqueada por seguridad perimetral SSRF: {msg}"

            from src.darius_ai.gui.human_gui import gui

            res = gui.scrape_web_content(url, max_chars=MAX_OUTPUT_CHARS)
            if res.get("success"):
                title = res.get("title", "")
                content = res.get("content", "")
                return True, f"Título: {title}\n\nContenido:\n{content}"
            return False, f"Error de scraping: {res.get('error', 'Fallo desconocido')}"
        except Exception as exc:
            return False, f"Error al scrapear {url}: {exc}"

    def parse_and_execute_tool(self, tool_name: str, args_str: str = "") -> dict[str, Any]:
        """
        Despachador central de llamadas a herramientas autónomas con protecciones de seguridad.
        Retorna:
          {
            "success": bool,
            "tool": str,
            "output": str,
            "is_destructive": bool
          }
        """
        tool_clean = tool_name.strip().lower()
        args_clean = args_str.strip()
        destructive = is_destructive(f"{tool_clean} {args_clean}")

        # Detección y bloqueo perimetral de inyección de prompt
        from src.darius_ai.core.security_guard import CredentialStripper, InjectionScanner, ThreatLevel

        scanner = InjectionScanner()
        findings = scanner.scan(args_clean)
        if any(f.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL) for f in findings):
            log.warning(f"[AgenticBridge] Inyección detectada en herramienta {tool_clean}: {args_clean[:60]}")
            return {
                "success": False,
                "tool": tool_name,
                "output": "Ejecución abortada: patrón de inyección de prompt detectado en argumentos.",
                "is_destructive": False,
            }

        if tool_clean in ("flush_dns", "limpiar_dns", "ipconfig_flushdns"):
            ok, out = self.flush_dns()
        elif tool_clean in ("top_processes", "procesos_ram", "ver_procesos"):
            ok, out = self.get_top_processes()
        elif tool_clean in ("system_summary", "diagnostico_sistema", "estado_recursos"):
            ok, out = self.get_system_summary()
        elif tool_clean in ("execute_gh", "gh", "github_cli"):
            ok, out = self.execute_gh(args_clean)
        elif tool_clean in ("execute_git", "git"):
            ok, out = self.execute_git(args_clean)
        elif tool_clean in ("execute_powershell", "powershell", "ps"):
            ok, out = self.execute_powershell(args_clean)
        elif tool_clean in ("execute_cmd", "cmd"):
            ok, out = self.execute_cmd(args_clean)
        elif tool_clean in ("human_type", "escribir", "teclear", "type_text"):
            ok, out = self.human_type(args_clean)
        elif tool_clean in ("human_click", "clic", "hacer_clic", "click"):
            # Extraer posibles coordenadas (x=100, y=200) o argumentos numéricos
            nums = [int(n) for n in re.findall(r"\b\d+\b", args_clean)]
            cx = nums[0] if len(nums) >= 1 else None
            cy = nums[1] if len(nums) >= 2 else None
            is_right = "right" in args_clean.lower() or "derecho" in args_clean.lower()
            is_double = "doble" in args_clean.lower() or "double" in args_clean.lower()
            btn = "right" if is_right else "left"
            ok, out = self.human_click(x=cx, y=cy, button=btn, double=is_double)
        elif tool_clean in ("human_mouse_move", "mover_mouse", "mouse_move"):
            nums = [int(n) for n in re.findall(r"\b\d+\b", args_clean)]
            if len(nums) >= 2:
                ok, out = self.human_mouse_move(nums[0], nums[1])
            else:
                ok, out = False, f"Se requieren coordenadas (x, y). Recibido: '{args_clean}'"
        elif tool_clean in ("human_hotkey", "hotkey", "combinacion_teclas", "presionar_teclas"):
            ok, out = self.human_hotkey(args_clean)
        elif tool_clean in ("scrape_web", "scrapear", "extraer_web", "leer_web"):
            ok, out = self.scrape_web(args_clean)
        elif tool_clean in ("python_exec", "safe_python", "python", "py"):
            from src.darius_ai.core.safe_code_interpreter import SafeCodeInterpreter

            interp = SafeCodeInterpreter()
            res = interp.run(args_clean)
            ok = res.success
            out = res.output if res.success else f"Error: {res.error}"
        elif tool_clean in ("web_search", "buscar_web", "google", "ddg"):
            from src.darius_ai.core.web_search_engine import WebSearchEngine

            engine = WebSearchEngine()
            results = engine.search(args_clean, max_results=3)
            ok = True
            out = "\n".join(f"- {r.title}: {r.snippet} ({r.url})" for r in results) or "Sin resultados."
        elif tool_clean in ("deep_research", "investigar_fondo"):
            from src.darius_ai.core.deep_research_agent import DeepResearchAgent
            from src.darius_ai.core.web_search_engine import WebSearchEngine

            agent = DeepResearchAgent(search_engine=WebSearchEngine())
            brief = agent.research(args_clean)
            ok = True
            out = brief.markdown_report
        elif tool_clean in ("media_action", "control_musica", "multimedia"):
            from src.darius_ai.system.media_controller import media_controller

            act = args_clean.lower().strip()
            if any(k in act for k in ("next", "siguiente")):
                ok, out = media_controller.next_track()
            elif any(k in act for k in ("prev", "anterior", "atras")):
                ok, out = media_controller.prev_track()
            elif any(k in act for k in ("stop", "detener", "parar")):
                ok, out = media_controller.stop()
            elif any(k in act for k in ("up", "subir", "aumentar")):
                ok, out = media_controller.volume_up()
            elif any(k in act for k in ("down", "bajar", "disminuir")):
                ok, out = media_controller.volume_down()
            elif any(k in act for k in ("mute", "silenciar", "mutear")):
                ok, out = media_controller.toggle_mute()
            elif "%" in act or any(char.isdigit() for char in act):
                match_digits = re.findall(r"\b\d+\b", act)
                pct = int(match_digits[0]) if match_digits else 50
                ok, out = media_controller.set_volume_percent(pct)
            else:
                ok, out = media_controller.play_pause()
        elif tool_clean in ("science_oracle", "oraculo_ciencia", "wikipedia_lookup", "constante_fisica"):
            from src.darius_ai.core.science_oracle import ScienceOracle

            oracle = ScienceOracle()
            ok, out = oracle.get_constant_or_conversion(args_clean)
            if not ok:
                ok, out = oracle.get_entity_summary(args_clean)
        elif tool_clean in (
            "darius_protocol",
            "protocolo_darius",
            "diagnostico_darius",
            "diagnostico_sistemas",
            "stark_protocol",
            "protocolo_stark",
            "diagnostico_armadura",
        ):
            from src.darius_ai.core.darius_protocol import get_darius_engine

            engine = get_darius_engine()
            diag = engine.run_diagnostic(with_sfx=True)
            out = engine.generate_vocal_briefing(diag)
            ok = True
        elif tool_clean in (
            "darius_persona",
            "jarvis_persona",
            "darius_wit",
            "humor_darius",
            "broma_darius",
            "consulta_humor",
        ):
            from src.darius_ai.core.darius_persona import DariusPersona

            out = DariusPersona.get_witty_retort(args_clean or "cuéntame un chiste")
            ok = True
        elif tool_clean in ("news_sentinel", "noticias", "titulares", "ultimas_noticias"):
            from src.darius_ai.core.news_sentinel import NewsSentinel

            sentinel = NewsSentinel()
            cat = args_clean.strip() or "technology"
            headlines = sentinel.get_top_headlines(category=cat, limit=4)
            out = sentinel.format_vocal_briefing(headlines, category=cat)
            ok = True
        elif tool_clean in ("lexicon_oracle", "definir_palabra", "diccionario", "lexico"):
            from src.darius_ai.core.lexicon_oracle import LexiconOracle

            oracle = LexiconOracle()
            target_word = args_clean.strip()
            found, entry, suggs = oracle.lookup(target_word)
            if found and entry:
                out = oracle.format_vocal_definition(entry)
                ok = True
            elif suggs:
                out = f"No encontré '{target_word}', señor. ¿Quizás quiso decir: {', '.join(suggs)}?"
                ok = False
            else:
                out = f"No encontré definición para '{target_word}' en el léxico, señor."
                ok = False
        elif tool_clean in ("youtube_search", "youtube", "reproducir_youtube", "video_youtube"):
            from src.darius_ai.system.media_controller import media_controller

            ok, out = media_controller.search_and_play_youtube(args_clean, auto_play=True)
        elif tool_clean in ("visual_ocr", "ocr_screen", "leer_pantalla", "extraer_texto_pantalla"):
            from src.darius_ai.core.visual_intel_ocr import VisualIntelOCR

            ocr = VisualIntelOCR()
            res = ocr.ocr_screen_region()
            ok = bool(res.text.strip())
            out = res.text if ok else "No se detectó texto en la pantalla, señor."
        elif tool_clean in ("face_biometrics", "biometric_auth", "reconocimiento_facial"):
            from src.darius_ai.core.face_biometrics import get_face_biometrics_engine

            engine = get_face_biometrics_engine()
            res = engine.verify_live_user(timeout_seconds=2.0)
            out = engine.get_biometric_greeting(res)
            ok = res.verified
        elif tool_clean in (
            "darius_timer",
            "stark_timer",
            "temporizador",
            "cuenta_regresiva",
            "alarma_temporizador",
        ):
            from src.darius_ai.core.darius_timer import get_darius_timer_manager

            mgr = get_darius_timer_manager()
            act = args_clean.lower().strip()
            if any(k in act for k in ("cancel", "cancelar", "detener", "parar")):
                for t in mgr.list_active_timers():
                    mgr.cancel_timer(t.id)
                out = "Temporizadores cancelados, señor."
                ok = True
            elif any(k in act for k in ("status", "estado", "cuanto", "queda")):
                active = mgr.list_active_timers()
                if not active:
                    out = "No hay temporizadores activos en este momento, señor."
                else:
                    out = mgr.format_timer_speech(active[0])
                ok = True
            else:
                match_digits = re.findall(r"\b\d+\b", act)
                secs = float(match_digits[0]) * 60.0 if match_digits else 300.0
                t = mgr.create_timer(label="recordatorio", seconds=secs)
                out = mgr.format_timer_speech(t)
                ok = True
        elif tool_clean in ("dialogue_stack", "dialogo_lifo", "pila_dialogo"):
            from src.darius_ai.core.dialogue_stack import get_dialogue_stack

            stack = get_dialogue_stack()
            top = stack.peek()
            if top:
                out = f"Diálogo activo: '{top.prompt}' (opciones: {list(top.expected_options.keys())})"
            else:
                out = "La pila de diálogo está vacía, señor."
            ok = True
        elif tool_clean in ("wake_on_lan", "wol", "despertar_pc", "encender_equipo"):
            from src.darius_ai.system.wol_dispatcher import get_wol_dispatcher

            dispatcher = get_wol_dispatcher()
            target = args_clean.strip() or "gaming_rig"
            ok, out = dispatcher.dispatch_wake(target, with_sfx=True)
        elif tool_clean in (
            "darius_lockdown",
            "tactical_lockdown",
            "lockdown",
            "codigo_rojo",
            "kill_switch",
            "silencio_tactico",
        ):
            from src.darius_ai.core.darius_lockdown import get_darius_lockdown_engine

            engine = get_darius_lockdown_engine()
            if any(k in args_clean.lower() for k in ("rojo", "lockdown", "bloqueo", "emergencia", "kill")):
                ok, out = engine.trigger_emergency_lockdown(lock_workstation=True)
            else:
                ok, out = engine.trigger_tactical_silence()
        elif tool_clean in ("track_orbital_iss", "orbital_radar", "iss", "estacion_espacial", "posicion_iss"):
            from src.darius_ai.core.orbital_radar import get_orbital_radar

            radar = get_orbital_radar()
            ok_radar, iss, alocution = radar.get_iss_position()
            ok = ok_radar
            out = radar.format_vocal_telemetry(iss) if ok_radar and iss else alocution
        elif tool_clean in ("scan_overhead_air_traffic", "air_traffic", "radar_aereo", "trafico_aereo", "vuelos"):
            from src.darius_ai.core.air_traffic_sentinel import get_air_traffic_sentinel

            sentinel = get_air_traffic_sentinel()
            ok_air, contacts, alocution = sentinel.scan_overhead()
            ok = ok_air
            out = sentinel.format_vocal_radar(contacts) if ok_air and contacts else alocution
        elif tool_clean in ("check_seismic_activity", "seismic_sensor", "sismos", "terremotos", "alerta_sismica"):
            from src.darius_ai.core.seismic_sensor import get_seismic_sensor

            sensor = get_seismic_sensor()
            ok_seis, events, alocution = sensor.get_recent_earthquakes(min_magnitude=4.5)
            ok = ok_seis
            out = sensor.format_vocal_alert(events, min_magnitude=4.5) if ok_seis and events else alocution
        elif tool_clean in ("query_space_weather", "space_weather", "clima_espacial", "tormenta_solar", "indice_kp"):
            from src.darius_ai.core.space_weather_oracle import get_space_weather_oracle

            oracle = get_space_weather_oracle()
            ok_sw, report, alocution = oracle.get_current_space_weather()
            ok = ok_sw
            out = oracle.format_vocal_briefing(report) if ok_sw and report else alocution
        elif tool_clean in ("gods_eye_protocol", "protocolo_ojo_de_dios", "ojo_de_dios", "radar_global"):
            from src.darius_ai.audio.sound_effects import get_sfx_engine
            from src.darius_ai.core.air_traffic_sentinel import get_air_traffic_sentinel
            from src.darius_ai.core.orbital_radar import get_orbital_radar
            from src.darius_ai.core.seismic_sensor import get_seismic_sensor
            from src.darius_ai.core.space_weather_oracle import get_space_weather_oracle

            get_sfx_engine().play_sonar_ping(blocking=False)
            radar = get_orbital_radar()
            air = get_air_traffic_sentinel()
            seismic = get_seismic_sensor()
            space = get_space_weather_oracle()

            _, iss, _ = radar.get_iss_position()
            _, flights, _ = air.scan_overhead()
            _, quakes, _ = seismic.get_recent_earthquakes(min_magnitude=4.5, limit=3)
            _, sw, _ = space.get_current_space_weather()

            sections = ["Protocolo Ojo de Dios activado, señor. Diagnóstico situacional global en línea:"]
            if iss:
                sections.append(
                    f"1. Órbita: ISS a {iss.altitude_km:.0f} km de altitud "
                    f"sobre [{iss.latitude:.1f}°, {iss.longitude:.1f}°]."
                )
            if flights:
                sections.append(f"2. Espacio aéreo: {len(flights)} aeronaves detectadas en radio táctico.")
            else:
                sections.append("2. Espacio aéreo: Corredor aéreo local despejado.")
            if quakes:
                sections.append(f"3. Sensores sísmicos: {len(quakes)} sismos >= M4.5 en las últimas 24h.")
            else:
                sections.append("3. Sensores sísmicos: Corteza terrestre estable sin anomalías mayores.")
            if sw:
                sections.append(f"4. Clima espacial: Índice Kp {sw.kp_index:.1f} ({sw.storm_level}).")

            ok = True
            out = "\n".join(sections)
        else:
            ok = False
            out = f"Herramienta desconocida: '{tool_name}'."

        # Sanitización de credenciales y tokens en la salida de cualquier herramienta
        out = CredentialStripper().strip(out)

        if destructive:
            try:
                from src.darius_ai.core.approval_store import ApprovalStore, RiskTier

                store = ApprovalStore()
                store.propose_action(
                    action_type=tool_clean,
                    description=f"Ejecución de {tool_clean} con argumentos: {args_clean}",
                    payload={"tool": tool_clean, "args": args_clean},
                    tier=RiskTier.HIGH,
                )
            except Exception as exc:
                log.warning(f"[AgenticBridge] No se pudo registrar en ApprovalStore: {exc}")

        return {
            "success": ok,
            "tool": tool_name,
            "output": out,
            "is_destructive": destructive,
        }

    # Alias idiomático para llamadas directas
    execute_tool = parse_and_execute_tool



# Instancia singleton accesible globalmente
bridge = AgenticBridge()
