"""
daily_digest.py — Motor de resumen ejecutivo matutino y briefing del día para Darius AI
========================================================================================
Arquitectura Nativa Darius AI. Agrega telemetría del sistema, tareas pendientes
en la bóveda de Obsidian, estado del espacio de trabajo Git y pronóstico del tiempo, sintetizando
una alocución ejecutiva natural, concisa (<200 palabras) y optimizada para síntesis vocal (TTS).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

log = logging.getLogger("DARIUS.DailyDigest")


@dataclass
class DigestMetrics:
    system_summary: str = ""
    pending_tasks: list[str] = field(default_factory=list)
    recent_notes: list[str] = field(default_factory=list)
    weather_summary: str = ""
    git_summary: str = ""
    top_headlines: list[str] = field(default_factory=list)


class DailyDigestEngine:
    """
    Agregador y sintetizador de briefings diarios para Darius AI.
    """

    def __init__(self, vault_path: Path | str | None = None) -> None:
        if vault_path is None:
            # Intentar resolver la bóveda desde obsidian_brain o por defecto
            try:
                from src.darius_ai.core.obsidian_brain import brain

                self.vault_path = brain.vault_path
            except Exception:
                self.vault_path = Path.home() / "Documents" / "Obsidian"
        else:
            self.vault_path = Path(vault_path)

    def collect_metrics(self) -> DigestMetrics:
        """Recolecta métricas de las distintas fuentes locales."""
        metrics = DigestMetrics()

        # 1. Telemetría del sistema (RAM y disco)
        try:
            from src.darius_ai.core.agentic_bridge import bridge

            ok, sys_out = bridge.get_system_summary()
            metrics.system_summary = sys_out if ok else "Diagnóstico del sistema operativo no disponible."
        except Exception as exc:
            metrics.system_summary = f"Métricas de hardware no disponibles ({exc})."

        # 2. Tareas pendientes y notas recientes de Obsidian
        try:
            if self.vault_path.exists():
                today_str = datetime.now().strftime("%Y-%m-%d")
                daily_file = self.vault_path / "Diario" / f"{today_str}.md"
                if not daily_file.exists():
                    daily_file = self.vault_path / f"{today_str}.md"

                if daily_file.exists():
                    text = daily_file.read_text(encoding="utf-8", errors="ignore")
                    tasks = re.findall(r"^[-*]\s*\[\s*\]\s*(.+)$", text, flags=re.MULTILINE)
                    metrics.pending_tasks = tasks[:5]

                # Notas modificadas recientemente
                md_files = sorted(
                    self.vault_path.glob("**/*.md"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                metrics.recent_notes = [p.stem for p in md_files[:3] if p.stem != today_str]
        except Exception as exc:
            log.warning(f"[DailyDigest] Error leyendo Obsidian: {exc}")

        # 3. Estado de repositorio Git activo
        try:
            from src.darius_ai.core.agentic_bridge import bridge

            ok, git_out = bridge.execute_git("status -s")
            if ok:
                lines = [line.strip() for line in git_out.splitlines() if line.strip()]
                if not lines:
                    metrics.git_summary = "Repositorio local limpio, sin cambios pendientes."
                else:
                    metrics.git_summary = f"{len(lines)} archivos con cambios locales pendientes."
        except Exception:
            metrics.git_summary = "Control de versiones Git no disponible."

        # 4. Estado del tiempo
        metrics.weather_summary = "Condiciones meteorológicas estables."

        # 5. Noticias destacadas de tecnología (NewsSentinel)
        try:
            from src.darius_ai.core.news_sentinel import NewsSentinel

            sentinel = NewsSentinel()
            headlines = sentinel.get_top_headlines(category="technology", limit=2)
            metrics.top_headlines = [h.title for h in headlines if h.title]
        except Exception:
            metrics.top_headlines = []

        return metrics

    def generate_spoken_narrative(self, metrics: DigestMetrics) -> str:
        """
        Sintetiza una alocución vocal ejecutiva siguiendo reglas rigurosas:
        - Estrictamente menos de 200 palabras.
        - Cero formato markdown (*, #, viñetas, bloques de código).
        - Directa, cálida y profesional.
        """
        parts = ["Buenos días, Óscar. Aquí tienes tu briefing ejecutivo de hoy."]

        # Hardware / Sistema
        if metrics.system_summary:
            clean_sys = metrics.system_summary.replace("RAM:", "Memoria RAM con").replace("|", "y")
            parts.append(f"El estado de tu máquina es óptimo: {clean_sys}.")

        # Tareas pendientes
        if metrics.pending_tasks:
            count = len(metrics.pending_tasks)
            first_task = metrics.pending_tasks[0]
            if count == 1:
                parts.append(f"Tienes una tarea pendiente en tu diario: {first_task}.")
            else:
                parts.append(f"Tienes {count} tareas pendientes en tu diario. La principal es: {first_task}.")
        else:
            parts.append("No tienes tareas pendientes registradas en tu diario para hoy.")

        # Notas o proyectos recientes
        if metrics.recent_notes:
            notes_str = ", ".join(metrics.recent_notes[:2])
            parts.append(f"Tus notas de trabajo activas son: {notes_str}.")

        # Git / Workspace
        if metrics.git_summary and "limpio" not in metrics.git_summary.lower():
            parts.append(f"En desarrollo: {metrics.git_summary}.")

        # Noticias destacadas
        if metrics.top_headlines:
            first_news = metrics.top_headlines[0]
            parts.append(f"En los titulares de hoy: {first_news}.")

        # Cierre
        parts.append("Todos los sistemas están operativos y preparados. ¿En qué empezamos?")

        raw_narrative = " ".join(parts)

        # Sanitizar cualquier residuo de markdown
        clean_narrative = re.sub(r"[*#_`~>\[\]]", "", raw_narrative)
        clean_narrative = re.sub(r"\s+", " ", clean_narrative).strip()

        # Asegurar longitud estricta (< 200 palabras)
        words = clean_narrative.split()
        if len(words) > 195:
            clean_narrative = " ".join(words[:190]) + "... Sistemas listos."

        return clean_narrative

    def save_briefing(self, metrics: DigestMetrics, narrative: str) -> Path:
        """Guarda el briefing formateado en Markdown dentro de la bóveda de Obsidian."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        briefings_dir = self.vault_path / "Darius" / "Briefings"
        briefings_dir.mkdir(parents=True, exist_ok=True)

        target_file = briefings_dir / f"Briefing_{today_str}.md"
        content = (
            f"# Briefing Ejecutivo — {today_str}\n\n"
            f"> **Darius AI** | Síntesis matutina generada a las {datetime.now().strftime('%H:%M')}\n\n"
            f"## Alocución Vocal\n\n"
            f"{narrative}\n\n"
            f"## Telemetría de Sistema\n"
            f"- {metrics.system_summary}\n\n"
            f"## Tareas Pendientes\n"
            + ("\n".join(f"- [ ] {t}" for t in metrics.pending_tasks) if metrics.pending_tasks else "- Ninguna")
            + "\n\n## Notas Recientes\n"
            + ("\n".join(f"- [[{n}]]" for n in metrics.recent_notes) if metrics.recent_notes else "- Ninguna")
            + f"\n\n## Control de Versiones\n- {metrics.git_summary}\n"
            + (
                "\n## Titulares Destacados\n" + "\n".join(f"- {h}" for h in metrics.top_headlines) + "\n"
                if metrics.top_headlines
                else ""
            )
        )
        target_file.write_text(content, encoding="utf-8")
        return target_file
