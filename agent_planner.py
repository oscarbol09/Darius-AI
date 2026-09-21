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

from ai_client import get_ai_response

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
        prompt = f"{PLANNER_SYSTEM_PROMPT}\n\nMeta del usuario: \"{goal.strip()}\"\n\nJSON:"
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
        """Ejecuta una herramienta individual del plan agéntico."""
        p = dict(params or {})

        # Inyectar resultado previo si el campo está vacío o contiene marcador
        for k, v in list(p.items()):
            if isinstance(v, str) and ("{{PREV}}" in v or not v.strip()) and prev_result:
                p[k] = v.replace("{{PREV}}", prev_result) if "{{PREV}}" in v else prev_result

        t = tool.lower().strip()
        log.info(f"[Planner] Ejecutando paso: {t} con params: {p}")

        try:
            if t == "screen_vision":
                from screen_vision import vision_engine
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
                from deep_research import research_pipeline
                topic = p.get("topic", "") or prev_result or "tema general"
                depth = p.get("depth", "standard")
                res = research_pipeline.run_research(topic=topic, depth=depth, save_to_obsidian=True)
                return True, res["summary"]

            elif t == "web_search":
                query = p.get("query", "") or prev_result
                from deep_research import _search_duckduckgo
                results = _search_duckduckgo(query, max_results=3)
                out = "\n".join(f"- {r['title']}: {r['snippet']} ({r['url']})" for r in results)
                return True, out or "No se encontraron resultados en la web."

            elif t == "save_obsidian_memory":
                from obsidian_brain import brain
                title = p.get("title", "Nota de Darius")
                content = p.get("content", "") or prev_result
                path = brain.save_memory(title=title, content=content)
                return True, f"Memoria guardada en Obsidian: {path.name}"

            elif t == "append_daily_note":
                from obsidian_brain import brain
                entry = p.get("entry", "") or prev_result
                path = brain.append_daily_note(entry=entry)
                return True, f"Entrada añadida a la nota diaria: {path.name}"

            elif t == "open_app":
                from windows_commands import resolve_and_launch
                app_name = p.get("app_name", "")
                desc = resolve_and_launch(app_name)
                return True, f"Lanzando aplicación: {desc or app_name}"

            elif t == "human_gui":
                from human_gui import gui
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
                from windows_commands import resolve_action, run_action
                cmd = p.get("command", "")
                entry = resolve_action(cmd)
                if entry:
                    ok, out = run_action(entry)
                    return ok, out or f"Acción '{cmd}' completada."
                return False, f"Comando de sistema no reconocido: {cmd}"

            elif t == "speak":
                txt = p.get("text", "") or prev_result
                return True, txt

            return False, f"Herramienta desconocida: {t}"

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
        if status_fn:
            status_fn("🧠 PLANIFICANDO META…", "#A855F7")

        steps = self.create_plan(goal)
        if not steps:
            return {"ok": False, "error": "No se pudo generar un plan de acción."}

        step_results = []
        last_output = ""
        success_count = 0

        for i, step in enumerate(steps, 1):
            tool = step.get("tool", "unknown")
            params = step.get("params", {})

            if status_fn:
                status_fn(f"⚡ PASO {i}/{len(steps)}: {tool.upper()[:16]}", "#38BDF8")

            ok, output = self.execute_step(tool, params, prev_result=last_output)
            step_results.append({
                "step_index": i,
                "tool": tool,
                "params": params,
                "success": ok,
                "output": output,
            })

            if ok:
                success_count += 1
                last_output = output
            else:
                log.warning(f"[Planner] Paso {i} falló: {output}")

        summary = (
            f"Meta completada: '{goal}'. "
            f"Se ejecutaron {success_count} de {len(steps)} pasos correctamente."
        )

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
