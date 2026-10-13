"""
agent_planner.py — Planificador Agéntico Multi-Paso y Orquestador para DARIUS AI
===============================================================================
Permite a Darius AI descomponer y ejecutar metas complejas que requieren múltiples
pasos secuenciales (ej. "Toma una captura de la pantalla, investiga el error y anótalo en mi diario"):
  1. Descomposición de metas en secuencias JSON ordenadas (1 a 4 pasos atómicos).
  2. Catálogo de herramientas locales integradas (Visión, Deep Research, Obsidian, Win32, Human GUI).
  3. Canalización de contexto (el resultado del paso anterior fluye al siguiente).
  4. Recuperación y tolerancia a fallos con degradación elegante.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from src.darius_ai.core.ai_client import get_ai_response

log = logging.getLogger("DARIUS.Planner")

PLANNER_SYSTEM_PROMPT = """Eres el módulo planificador agéntico de DARIUS AI.
Tu tarea es descomponer la meta u orden del usuario en una secuencia estricta y mínima de pasos (1 a 4 pasos).
Usa EXCLUSIVAMENTE las herramientas disponibles en la lista a continuación.

HERRAMIENTAS DISPONIBLES:
1. screen_vision
   - action: "analyze" | "error" | "ocr"
   - prompt: string (opcional)

2. deep_research
   - topic: string (requerido)
   - depth: "quick" | "standard" | "deep" (opcional, default standard)

3. web_search
   - query: string (requerido)

4. save_obsidian_memory
   - title: string (requerido)
   - content: string (opcional, si está vacío se inyectará el resultado del paso anterior)

5. append_daily_note
   - entry: string (opcional, si está vacío se inyectará el resultado del paso anterior)

6. open_app
   - app_name: string (requerido)

7. human_gui
   - action: "type" | "click" | "hotkey"
   - text: string (para type)
   - keys: string (para hotkey, ej. "ctrl+c")

8. windows_action
   - command: string (ej. "limpiar cache dns", "ver prs de github", "procesos que mas consumen")

9. speak
   - text: string (mensaje de confirmación o síntesis verbal)

10. target_dossier
   - target_name: string (nombre del objetivo o persona)
   - category: "person" | "company" | "repository" | "topic" (opcional)

11. daily_digest
   - save: boolean (opcional, default true)

12. schedule_task
   - prompt: string (requerido)
   - type: "interval" | "once" (opcional, default interval)
   - value: string (segundos o ISO datetime)

13. check_complexity
   - query: string (requerido)

14. execute_skill
   - skill_name: string (requerido)

15. approval_status
   - action: "pending" | "resolve" (opcional, default pending)
   - id: string (para resolve)
   - decision: "approve" | "deny" (para resolve)

16. safe_python_exec
   - code: string (requerido, código Python verificado por AST para cálculos o transformaciones)

17. user_profile
   - action: "read" | "add" | "update" | "remove" (opcional, default read)
   - category: "Identidad y Rol" | "Preferencias y Estilo" | "Proyectos Activos"
     | "Stack Tecnológico" | "Restricciones y Hábitos"
   - fact: string

18. workflow_run
   - dag: object (con 'nodes' y 'edges' para ejecución en grafo)

19. media_control
   - action: "play_pause" | "next" | "prev" | "stop" | "volume_up" | "volume_down" | "mute" | "set_volume"
   - percent: integer (opcional para set_volume)

20. science_oracle
   - query: string (requerido, constante física, conversión de unidades o entidad enciclopédica)

21. darius_protocol
   - with_sfx: boolean (opcional, default true)

22. darius_persona
   - query: string (opcional, réplica ingeniosa, humor inteligente o personalidad)

23. news_sentinel
   - category: "technology" | "science" | "business" | "world" (opcional)
   - limit: integer (opcional, default 4)

24. lexicon_oracle
   - word: string (requerido, palabra para buscar definición, fonética y sinónimos)

25. youtube_search
   - query: string (requerido, video o música para reproducir)

26. visual_ocr
   - action: "screen" | "clipboard" (opcional, default screen)

27. darius_timer
   - action: "create" | "cancel" | "status" (opcional, default status)
   - label: string (opcional)
   - seconds: integer (opcional para create)

28. dialogue_stack
   - action: "push" | "pop" | "peek" | "clear" (opcional, default peek)
   - prompt: string (para push)
   - expected_options: object (para push)

29. wake_on_lan
   - target: string (requerido, ej. "gaming_rig", "nas", "homelab" o dirección MAC)

30. darius_lockdown (o tactical_lockdown)
   - level: "silence" | "lockdown" (opcional, default silence)

31. track_orbital_iss
   - action: "position" (opcional)

32. scan_overhead_air_traffic
   - radius_km: float (opcional, default 100.0)
   - max_contacts: integer (opcional, default 5)

33. check_seismic_activity
   - min_magnitude: float (opcional, default 4.5)
   - limit: integer (opcional, default 5)

34. query_space_weather
   - action: "status" (opcional)

REGLAS OBLIGATORIAS:
- Devuelve ÚNICAMENTE un objeto JSON válido con la clave 'steps' (lista de objetos).
- Cada paso debe contener: 'tool' (nombre de la herramienta) y 'params' (objeto con sus parámetros).
- No inventes herramientas que no estén en la lista.
- Para pasar el resultado de un paso previo al siguiente, deja el parámetro de contenido vacío o usa '{{PREV}}'.
- Ejemplo de salida JSON:
{
  "goal": "analizar error en pantalla y guardar en notas",
  "steps": [
    {"tool": "screen_vision", "params": {"action": "error"}},
    {"tool": "append_daily_note", "params": {"entry": "{{PREV}}"}}
  ]
}
"""



class AgentPlannerEngine:
    """
    Motor de planificación y orquestación multi-paso.
    """

    def create_plan(self, goal: str) -> list[dict[str, Any]]:
        """Solicita al LLM la descomposición de la meta en pasos estructurados."""
        from src.darius_ai.core.security_guard import InjectionScanner, ThreatLevel
        from src.darius_ai.core.user_profile_engine import UserProfileEngine

        # Protección perimetral contra inyecciones de prompt maliciosas
        scanner = InjectionScanner()
        findings = scanner.scan(goal)
        if any(f.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL) for f in findings):
            log.warning(f"[Planner] Bloqueado por inyección de prompt: {goal[:60]}")
            return []

        # Enriquecimiento dinámico con el perfil del usuario si existe
        try:
            profile_ctx = UserProfileEngine().get_profile_prompt_injection()
        except Exception:
            profile_ctx = ""

        prompt_prefix = f"{PLANNER_SYSTEM_PROMPT}\n\n{profile_ctx}" if profile_ctx else PLANNER_SYSTEM_PROMPT
        prompt = f'{prompt_prefix}\n\nMeta del usuario: "{goal.strip()}"\n\nJSON:'
        try:
            raw_response, _ = get_ai_response(prompt)
            match = re.search(r"\{[\s\S]*\}", raw_response)
            if match:
                data = json.loads(match.group(0))
                steps = data.get("steps", [])
                if isinstance(steps, list) and steps:
                    log.info(f"[Planner] Plan generado con {len(steps)} pasos para meta: '{goal}'")
                    return steps[:4]
        except Exception as e:
            log.warning(f"[Planner] Error generando plan con IA: {e}")

        # Fallback heurístico: un solo paso directo
        return [{"tool": "speak", "params": {"text": f"Ejecutando solicitud: {goal}"}}]

    def execute_step(self, tool: str, params: dict[str, Any], prev_result: str = "") -> tuple[bool, str]:
        """Ejecuta una herramienta individual del plan agéntico y sanitiza credenciales."""
        from src.darius_ai.core.security_guard import CredentialStripper

        ok, raw_out = self._execute_step_raw(tool, params, prev_result)
        return ok, CredentialStripper().strip(raw_out)

    def _execute_step_raw(self, tool: str, params: dict[str, Any], prev_result: str = "") -> tuple[bool, str]:
        """Ejecución interna directa de la herramienta."""
        p = dict(params or {})

        # Inyectar resultado previo si el campo está vacío o contiene marcador
        for k, v in list(p.items()):
            if isinstance(v, str) and ("{{PREV}}" in v or not v.strip()) and prev_result:
                p[k] = v.replace("{{PREV}}", prev_result) if "{{PREV}}" in v else prev_result

        t = tool.lower().strip()
        log.info(f"[Planner] Ejecutando paso: {t} con params: {p}")

        try:
            if t == "screen_vision":
                from src.darius_ai.core.screen_vision import vision_engine

                action = p.get("action", "analyze")
                prompt = p.get("prompt", "")
                if action == "error":
                    out = vision_engine.analyze_screen_error()
                elif action == "ocr":
                    out = vision_engine.read_screen_text()
                else:
                    out = vision_engine.analyze_screen(prompt=prompt or "¿Qué hay en mi pantalla?")
                return True, out

            elif t == "deep_research":
                topic = p.get("topic", "") or prev_result or "tema general"
                try:
                    from src.darius_ai.core.deep_research_agent import DeepResearchAgent
                    from src.darius_ai.core.web_search_engine import WebSearchEngine

                    agent = DeepResearchAgent(search_engine=WebSearchEngine())
                    brief = agent.research(topic)
                    return True, brief.markdown_report
                except Exception as ex:
                    log.warning(f"[Planner] Fallback en deep_research: {ex}")
                    from src.darius_ai.core.deep_research import research_pipeline

                    depth = p.get("depth", "standard")
                    res = research_pipeline.run_research(topic=topic, depth=depth, save_to_obsidian=True)
                    return True, res["summary"]

            elif t == "web_search":
                query = p.get("query", "") or prev_result
                try:
                    from src.darius_ai.core.web_search_engine import WebSearchEngine

                    search_engine = WebSearchEngine()
                    max_r = int(p.get("max_results", 3))
                    search_hits = search_engine.search(query, max_results=max_r)
                    out = "\n".join(f"- {hit.title}: {hit.snippet} ({hit.url})" for hit in search_hits)
                    return True, out or "No se encontraron resultados en la web."
                except Exception as ex:
                    log.warning(f"[Planner] Fallback en búsqueda web: {ex}")
                    from src.darius_ai.core.deep_research import _search_duckduckgo

                    fallback_hits = _search_duckduckgo(query, max_results=3)
                    out = "\n".join(f"- {r['title']}: {r['snippet']} ({r['url']})" for r in fallback_hits)
                    return True, out or "No se encontraron resultados en la web."

            elif t == "safe_python_exec":
                from src.darius_ai.core.safe_code_interpreter import SafeCodeInterpreter, UnsafeCodeError

                code_txt = p.get("code", "") or prev_result
                try:
                    interp = SafeCodeInterpreter()
                    exec_res = interp.run(code_txt)
                    if exec_res.success:
                        return True, exec_res.output or f"Código ejecutado en {exec_res.duration_ms:.1f}ms."
                    return False, f"Error en ejecución: {exec_res.error}"
                except UnsafeCodeError as ue:
                    return False, f"Infracción de seguridad AST: {ue}"

            elif t == "user_profile":
                from src.darius_ai.core.user_profile_engine import UserProfileEngine

                u_engine = UserProfileEngine()
                action = p.get("action", "read")
                cat = p.get("category", "Preferencias y Estilo")
                fact = p.get("fact", "") or prev_result
                if action == "read":
                    prof = u_engine.read_profile()
                    out = "\n".join(
                        f"### {k}\n" + "\n".join(f"- {item}" for item in v)
                        for k, v in prof.items()
                        if v
                    )
                    return True, out or "Perfil de usuario vacío."
                elif action == "add":
                    ok = u_engine.add_fact(cat, fact)
                    return ok, f"Hecho añadido a '{cat}': {fact}"
                elif action == "update":
                    old_f = p.get("old_fact", "")
                    ok = u_engine.update_fact(cat, old_f, fact)
                    return ok, f"Hecho actualizado en '{cat}'."
                elif action == "remove":
                    ok = u_engine.remove_fact(cat, fact)
                    return ok, f"Hecho eliminado de '{cat}'."

            elif t == "workflow_run":
                from src.darius_ai.core.workflow_dag import WorkflowDAG, WorkflowEdge, WorkflowNode

                dag_dict = p.get("dag", {})
                dag = WorkflowDAG(name=p.get("name", "Workflow Plan"))
                for n in dag_dict.get("nodes", []):
                    dag.add_node(
                        WorkflowNode(
                            id=n["id"],
                            action=n.get("action", ""),
                            params=n.get("params", {}),
                            description=n.get("description", ""),
                        )
                    )
                for e in dag_dict.get("edges", []):
                    dag.add_edge(
                        WorkflowEdge(
                            source=e["source"],
                            target=e["target"],
                            condition=e.get("condition"),
                        )
                    )
                valid, v_msg = dag.validate()
                if not valid:
                    return False, f"DAG inválido: {v_msg}"

                def _exec_node(node: WorkflowNode, ctx: dict[str, Any]) -> Any:
                    return f"Paso {node.id} ({node.action}) ejecutado."

                dag_results = dag.execute(_exec_node)
                return True, f"Workflow completado ({len(dag_results)} pasos): {dag_results}"

            elif t == "save_obsidian_memory":
                from src.darius_ai.core.obsidian_brain import brain

                title = p.get("title", "Nota de Darius")
                content = p.get("content", "") or prev_result
                path = brain.save_memory(title=title, content=content)
                return True, f"Memoria guardada en Obsidian: {path.name}"

            elif t == "append_daily_note":
                from src.darius_ai.core.obsidian_brain import brain

                entry = p.get("entry", "") or prev_result
                path = brain.append_daily_note(entry=entry)
                return True, f"Entrada añadida a la nota diaria: {path.name}"

            elif t == "open_app":
                from src.darius_ai.system.windows_commands import resolve_and_launch

                app_name = p.get("app_name", "")
                desc = resolve_and_launch(app_name)
                return True, f"Lanzando aplicación: {desc or app_name}"

            elif t == "human_gui":
                from src.darius_ai.gui.human_gui import gui

                action = p.get("action", "type")
                if action == "type":
                    txt = p.get("text", "") or prev_result
                    gui.human_type(txt)
                    return True, f"Texto escrito: {txt[:30]}..."
                elif action == "hotkey":
                    keys = p.get("keys", "enter")
                    gui.human_hotkey(keys)
                    return True, f"Atajo ejecutado: {keys}"
                elif action == "click":
                    gui.human_click()
                    return True, "Clic ejecutado."

            elif t == "windows_action":
                from src.darius_ai.system.windows_commands import resolve_action, run_action

                cmd = p.get("command", "")
                entry = resolve_action(cmd)
                if entry:
                    ok, out = run_action(entry)
                    return ok, out or f"Acción '{cmd}' completada."
                return False, f"Comando de sistema no reconocido: {cmd}"

            elif t == "speak":
                txt = p.get("text", "") or prev_result
                return True, txt

            elif t == "target_dossier":
                from src.darius_ai.core.target_dossier import get_dossier_engine

                target = p.get("target_name", "") or prev_result or "objetivo"
                cat = p.get("category", "person")
                dossier_engine = get_dossier_engine()
                dossier = dossier_engine.synthesize_dossier(target, category=cat, raw_research_text=prev_result)
                saved_path = dossier_engine.save_to_obsidian(dossier)
                summary_txt = dossier.to_speech_summary()
                return True, f"Dossier de {dossier.target_name} generado en Obsidian ({saved_path}): {summary_txt}"

            elif t == "daily_digest":
                from src.darius_ai.core.daily_digest import DailyDigestEngine

                engine_digest = DailyDigestEngine()
                metrics = engine_digest.collect_metrics()
                narrative = engine_digest.generate_spoken_narrative(metrics)
                if p.get("save", True):
                    engine_digest.save_briefing(metrics, narrative)
                return True, narrative

            elif t == "schedule_task":
                from src.darius_ai.core.task_scheduler import TaskScheduler

                prompt_txt = p.get("prompt", "") or prev_result or "Tarea periódica"
                stype = p.get("type", "interval")
                sval = str(p.get("value", "60"))
                sched = TaskScheduler()
                task = sched.schedule_task(prompt_txt, schedule_type=stype, schedule_value=sval)
                return True, f"Tarea '{task.id}' programada: {prompt_txt} (próxima: {task.next_run})"

            elif t == "check_complexity":
                from src.darius_ai.core.complexity_router import ComplexityRouter

                query_txt = p.get("query", "") or prev_result
                router = ComplexityRouter()
                score, tier, budget, target_mod = router.analyze(query_txt)
                return (
                    True,
                    f"Complejidad: {score} ({tier.value}), presupuesto: {budget} tokens, modelo: {target_mod.value}",
                )

            elif t == "execute_skill":
                from src.darius_ai.core.skill_registry import SkillRegistry

                skill_name = p.get("skill_name", "")
                reg = SkillRegistry()
                manifest = reg.get_skill(skill_name) or reg.discover_skills().get(skill_name)
                if manifest:
                    return True, f"Procedimiento '{skill_name}':\n{manifest.playbook}"
                return False, f"Habilidad '{skill_name}' no encontrada."

            elif t == "approval_status":
                from src.darius_ai.core.approval_store import ApprovalStore, Decision

                store = ApprovalStore()
                act = p.get("action", "pending")
                if act == "pending":
                    pending = store.get_pending_actions()
                    if not pending:
                        return True, "No hay acciones pendientes de aprobación."
                    items = [f"[{a.id}] {a.action_type}: {a.description}" for a in pending]
                    return True, "Acciones pendientes:\n" + "\n".join(items)
                elif act == "resolve":
                    aid = p.get("id", "")
                    dec = p.get("decision", "approve")
                    store.resolve_action(aid, Decision.APPROVE if dec == "approve" else Decision.DENY)
                    return True, f"Acción '{aid}' resuelta como {dec}."

            elif t == "media_control":
                from src.darius_ai.system.media_controller import media_controller

                action_val = p.get("action", "play_pause").lower()
                if "next" in action_val:
                    return media_controller.next_track()
                elif "prev" in action_val:
                    return media_controller.prev_track()
                elif "stop" in action_val:
                    return media_controller.stop()
                elif "up" in action_val:
                    return media_controller.volume_up()
                elif "down" in action_val:
                    return media_controller.volume_down()
                elif "mute" in action_val:
                    return media_controller.toggle_mute()
                elif "set" in action_val or "percent" in p:
                    pct = int(p.get("percent", 50))
                    return media_controller.set_volume_percent(pct)
                return media_controller.play_pause()

            elif t == "science_oracle":
                from src.darius_ai.core.science_oracle import ScienceOracle

                oracle = ScienceOracle()
                q = p.get("query", "") or prev_result
                ok, out = oracle.get_constant_or_conversion(q)
                if not ok:
                    ok, out = oracle.get_entity_summary(q)
                return ok, out

            elif t in ("darius_protocol", "stark_protocol"):
                from src.darius_ai.core.darius_protocol import get_darius_engine

                engine = get_darius_engine()
                sfx_flag = p.get("with_sfx", True)
                diag = engine.run_diagnostic(with_sfx=sfx_flag)
                return True, engine.generate_vocal_briefing(diag)

            elif t in ("darius_persona", "jarvis_persona", "darius_wit"):
                from src.darius_ai.core.darius_persona import DariusPersona

                query = p.get("query", "cuéntame un chiste")
                return True, DariusPersona.get_witty_retort(query)

            elif t in ("darius_timer", "stark_timer"):
                from src.darius_ai.core.darius_timer import get_darius_timer_manager

                mgr = get_darius_timer_manager()
                action = p.get("action", "status")
                if action == "create":
                    secs = float(p.get("seconds", 300))
                    label = p.get("label", "recordatorio")
                    timer = mgr.create_timer(label=label, seconds=secs)
                    return True, mgr.format_timer_speech(timer)
                elif action == "cancel":
                    for timer in mgr.list_active_timers():
                        mgr.cancel_timer(timer.id)
                    return True, "Temporizadores cancelados, señor."
                else:
                    active = mgr.list_active_timers()
                    if not active:
                        return True, "No hay temporizadores activos en este momento, señor."
                    return True, mgr.format_timer_speech(active[0])

            elif t in ("darius_lockdown", "tactical_lockdown"):
                from src.darius_ai.core.darius_lockdown import get_darius_lockdown_engine

                engine = get_darius_lockdown_engine()
                level = p.get("level", "silence")
                if level == "lockdown":
                    return engine.trigger_emergency_lockdown(lock_workstation=True)
                return engine.trigger_tactical_silence()

            elif t == "track_orbital_iss":
                from src.darius_ai.core.orbital_radar import get_orbital_radar

                radar = get_orbital_radar()
                ok, iss, alocution = radar.get_iss_position()
                if ok and iss:
                    return True, radar.format_vocal_telemetry(iss)
                return True, alocution

            elif t == "scan_overhead_air_traffic":
                from src.darius_ai.core.air_traffic_sentinel import get_air_traffic_sentinel

                sentinel = get_air_traffic_sentinel()
                rad = float(p.get("radius_km", 100.0))
                max_c = int(p.get("max_contacts", 5))
                ok, contacts, alocution = sentinel.scan_overhead(radius_km=rad, max_contacts=max_c)
                if ok and contacts:
                    return True, sentinel.format_vocal_radar(contacts)
                return True, alocution

            elif t == "check_seismic_activity":
                from src.darius_ai.core.seismic_sensor import get_seismic_sensor

                sensor = get_seismic_sensor()
                mag = float(p.get("min_magnitude", 4.5))
                lim = int(p.get("limit", 5))
                ok, events, alocution = sensor.get_recent_earthquakes(min_magnitude=mag, limit=lim)
                if ok and events:
                    return True, sensor.format_vocal_alert(events, min_magnitude=mag)
                return True, alocution

            elif t == "query_space_weather":
                from src.darius_ai.core.space_weather_oracle import get_space_weather_oracle

                oracle = get_space_weather_oracle()
                ok, report, alocution = oracle.get_current_space_weather()
                if ok and report:
                    return True, oracle.format_vocal_briefing(report)
                return True, alocution

            # Fallback a AgenticBridge si no se resolvió arriba
            from src.darius_ai.core.agentic_bridge import bridge

            args_str = p.get("query") or p.get("word") or p.get("text") or p.get("target") or json.dumps(p)
            res = bridge.parse_and_execute_tool(t, str(args_str))
            if res.get("success"):
                return True, res.get("output", "")

            return False, res.get("output") or f"Herramienta desconocida: {t}"

        except Exception as e:
            log.error(f"[Planner] Error ejecutando paso '{t}': {e}")
            return False, f"Error en {t}: {e}"

    def plan_and_execute(
        self,
        goal: str,
        speak_fn: Callable[[str], None] | None = None,
        status_fn: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        """
        Orquesta el ciclo completo: genera el plan, ejecuta cada paso en secuencia y reporta resultados.
        """
        from src.darius_ai.audio.sound_effects import get_sfx_engine
        from src.darius_ai.core.loop_guard import LoopGuard, LoopStatus
        from src.darius_ai.core.telemetry_tracker import get_telemetry_tracker

        tracker = get_telemetry_tracker()
        sfx = get_sfx_engine()
        guard = LoopGuard(max_identical_calls=3)

        # Verificación perimetral de inyección de prompt en la meta
        from src.darius_ai.core.security_guard import InjectionScanner, ThreatLevel

        scanner = InjectionScanner()
        findings = scanner.scan(goal)
        if any(f.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL) for f in findings):
            log.warning(f"[Planner] Meta bloqueada por inyección de prompt: {goal[:60]}")
            return {
                "ok": False,
                "error": "Meta bloqueada por reglas de seguridad (inyección de prompt detectada).",
            }

        tracker.push_event("agent_planner", f"Planificando meta: '{goal[:50]}'", status="running")
        sfx.play_scan_pulse()

        if status_fn:
            status_fn("🧠 PLANIFICANDO META…", "#A855F7")

        steps = self.create_plan(goal)
        if not steps:
            tracker.push_event("agent_planner", "Fallo al generar plan de acción", status="error")
            return {"ok": False, "error": "No se pudo generar un plan de acción."}

        step_results = []
        last_output = ""
        success_count = 0

        for i, step in enumerate(steps, 1):
            tool = step.get("tool", "unknown")
            params = step.get("params", {})

            # Protección determinista con LoopGuard
            loop_status, loop_msg = guard.record_call(tool, params)
            if loop_status == LoopStatus.BLOCK:
                log.error(f"[Planner] {loop_msg}")
                tracker.push_event(tool, "Bloqueado por LoopGuard", status="error")
                step_results.append(
                    {
                        "step_index": i,
                        "tool": tool,
                        "params": params,
                        "success": False,
                        "output": loop_msg,
                    }
                )
                break

            tracker.push_event(tool, f"Paso {i}/{len(steps)}: {tool}", status="running")
            sfx.play_target_lock()

            if status_fn:
                status_fn(f"⚡ PASO {i}/{len(steps)}: {tool.upper()[:16]}", "#38BDF8")

            ok, output = self.execute_step(tool, params, prev_result=last_output)
            step_results.append(
                {
                    "step_index": i,
                    "tool": tool,
                    "params": params,
                    "success": ok,
                    "output": output,
                }
            )


            if ok:
                success_count += 1
                last_output = output
                tracker.push_event(tool, f"Paso {i} completado con éxito", status="success")
            else:
                log.warning(f"[Planner] Paso {i} falló: {output}")
                tracker.push_event(tool, f"Paso {i} falló: {output[:40]}", status="error")

        summary = f"Meta completada: '{goal}'. Se ejecutaron {success_count} de {len(steps)} pasos correctamente."

        if success_count > 0:
            sfx.play_success_chime()
            tracker.push_event("agent_planner", f"Meta completada ({success_count}/{len(steps)} OK)", status="success")
        else:
            sfx.play_alert_tone()
            tracker.push_event("agent_planner", "Meta fallida en todos los pasos", status="error")

        if speak_fn:
            # Si el último paso fue una herramienta informativa, hablar su salida
            final_voice_text = last_output if len(last_output) < 300 and last_output else summary
            speak_fn(final_voice_text)

        if status_fn:
            status_fn("SISTEMA LISTO", "#10B981")

        return {
            "ok": success_count > 0,
            "goal": goal,
            "steps_count": len(steps),
            "success_count": success_count,
            "results": step_results,
            "final_output": last_output,
            "summary": summary,
        }


# Instancia singleton del planificador agéntico
agent_planner = AgentPlannerEngine()
