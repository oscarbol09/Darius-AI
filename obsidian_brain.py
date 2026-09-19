"""
obsidian_brain.py — Motor de memoria y notas en Obsidian para DARIUS AI
========================================================================
Gestiona la memoria a largo plazo, el diario personal y las notas del
asistente directamente sobre una bóveda (vault) local de Obsidian en formato
Markdown con metadatos frontmatter YAML.

Características principales:
  - Detección automática o configurable de la bóveda de Obsidian en Windows.
  - Almacenamiento de hechos, proyectos y preferencias en notas individuales.
  - Inserción cronológica en la nota diaria (Daily Note: YYYY-MM-DD.md).
  - Búsqueda semántica/léxica sobre el contenido de la bóveda.
  - Extracción y formateo de contexto relevante para inyectar en el prompt de Gemini.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path

from config_loader import cfg

log = logging.getLogger("DARIUS.Obsidian")


def _sanitize_filename(name: str) -> str:
    """Convierte un texto arbitrario en un nombre de archivo seguro para Windows."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    clean = re.sub(r"\s+", " ", clean)
    return clean[:80] if clean else "nota_sin_titulo"


class ObsidianBrain:
    """
    Cerebro y sistema de memoria de Darius AI integrado con Obsidian.
    """

    def __init__(self, vault_path: str | Path | None = None):
        self._custom_path = Path(vault_path) if vault_path else None
        self._vault_dir: Path | None = None

    @property
    def vault_path(self) -> Path:
        """Resuelve y asegura la existencia del directorio de la bóveda de Obsidian."""
        if self._vault_dir is not None and self._vault_dir.exists():
            return self._vault_dir

        configured = self._custom_path or cfg.obsidian_vault_path
        path = (
            Path(configured).expanduser().resolve()
            if configured
            else Path.home() / "Documents" / "Obsidian Vault"
        )

        try:
            path.mkdir(parents=True, exist_ok=True)
            self._vault_dir = path
        except Exception as e:
            log.warning(f"No se pudo crear la bóveda en '{path}': {e}. Usando directorio local.")
            fallback = Path(__file__).parent / "darius_vault"
            fallback.mkdir(parents=True, exist_ok=True)
            self._vault_dir = fallback

        return self._vault_dir

    # ── Guardado de Memorias y Notas ──────────────────────────────────────────

    def save_memory(
        self,
        title: str,
        content: str,
        category: str = "hecho",
        tags: list[str] | None = None,
    ) -> Path:
        """
        Guarda una memoria o nota permanente en la carpeta de memorias de Obsidian.
        """
        vault = self.vault_path
        folder = vault / cfg.obsidian_memories_folder
        folder.mkdir(parents=True, exist_ok=True)

        filename = f"{_sanitize_filename(title)}.md"
        filepath = folder / filename

        tag_list = list(set(["darius", "memoria", category] + (tags or [])))
        tags_yaml = "\n".join(f"  - {t}" for t in tag_list)
        now_iso = datetime.datetime.now().astimezone().isoformat()

        markdown = (
            f"---\n"
            f"tipo: memoria\n"
            f"categoria: {category}\n"
            f"fecha_creacion: '{now_iso}'\n"
            f"tags:\n"
            f"{tags_yaml}\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"{content.strip()}\n"
        )

        filepath.write_text(markdown, encoding="utf-8")
        log.info(f"[Obsidian] Memoria guardada: {filepath.relative_to(vault)}")
        return filepath

    def append_daily_note(self, entry: str) -> Path:
        """
        Agrega una entrada con marca de tiempo a la nota diaria de hoy (YYYY-MM-DD.md).
        """
        vault = self.vault_path
        folder = vault / cfg.obsidian_daily_notes_folder
        folder.mkdir(parents=True, exist_ok=True)

        today = datetime.date.today()
        today_str = today.strftime("%Y-%m-%d")
        filepath = folder / f"{today_str}.md"

        now_time = datetime.datetime.now().strftime("%H:%M:%S")
        entry_line = f"- **{now_time}** | {entry.strip()}\n"

        if not filepath.exists():
            header = (
                f"---\n"
                f"tipo: diario\n"
                f"fecha: '{today_str}'\n"
                f"tags:\n"
                f"  - diario\n"
                f"  - darius\n"
                f"---\n\n"
                f"# Diario — {today_str}\n\n"
            )
            filepath.write_text(header + entry_line, encoding="utf-8")
        else:
            with filepath.open("a", encoding="utf-8") as f:
                f.write(entry_line)

        log.info(f"[Obsidian] Entrada agregada al diario: {filepath.name}")
        return filepath

    # ── Búsqueda y Recuperación de Contexto ───────────────────────────────────

    def search_vault(self, query: str, max_results: int = 3) -> list[dict]:
        """
        Realiza una búsqueda de texto en los archivos markdown de la bóveda.
        Devuelve una lista de diccionarios con título, ruta y extracto de contenido.
        """
        vault = self.vault_path
        if not vault.exists():
            return []

        words = [w.lower() for w in re.split(r"\W+", query) if len(w) > 2]
        if not words:
            return []

        matches = []
        for file in vault.rglob("*.md"):
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                log.debug(f"No se pudo leer '{file}': {e}")
                continue

            text_lower = text.lower()
            score = sum(text_lower.count(w) for w in words)
            title_score = sum(file.stem.lower().count(w) * 3 for w in words)
            total_score = score + title_score

            if total_score > 0:
                # Extraer cuerpo sin frontmatter
                body = re.sub(r"^---[\s\S]*?---\n", "", text).strip()
                preview = body[:300] + ("..." if len(body) > 300 else "")
                matches.append({
                    "title": file.stem,
                    "path": str(file.relative_to(vault)),
                    "score": total_score,
                    "snippet": preview,
                })

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:max_results]

    def get_memory_context(self, query: str = "") -> str:
        """
        Genera un bloque de texto contextual a partir de memorias y notas
        relevantes en Obsidian para incluir en las instrucciones de Gemini.
        """
        if not cfg.obsidian_auto_inject_context:
            return ""

        context_parts = []

        # 1. Búsqueda de memorias relevantes para la consulta actual
        if query:
            results = self.search_vault(query, max_results=3)
            if results:
                mem_lines = ["Notas relevantes encontradas en la memoria de Obsidian:"]
                for r in results:
                    mem_lines.append(f"- [{r['title']}]: {r['snippet']}")
                context_parts.append("\n".join(mem_lines))

        # 2. Resumen de memorias recientes generales si no hay consulta específica
        if not context_parts:
            recent = self.list_recent_memories(limit=3)
            if recent:
                mem_lines = ["Memorias recientes de Obsidian:"]
                for r in recent:
                    mem_lines.append(f"- [{r['title']}]: {r['snippet']}")
                context_parts.append("\n".join(mem_lines))

        return "\n\n".join(context_parts)

    def list_recent_memories(self, limit: int = 5) -> list[dict]:
        """Devuelve las últimas memorias modificadas en la carpeta de memorias."""
        vault = self.vault_path
        folder = vault / cfg.obsidian_memories_folder
        if not folder.exists():
            return []

        files = list(folder.glob("*.md"))
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        results = []
        for file in files[:limit]:
            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
                body = re.sub(r"^---[\s\S]*?---\n", "", text).strip()
                preview = body[:200] + ("..." if len(body) > 200 else "")
                results.append({
                    "title": file.stem,
                    "path": str(file.relative_to(vault)),
                    "snippet": preview,
                })
            except Exception as e:
                log.debug(f"No se pudo leer memoria '{file}': {e}")
                continue

        return results


# Instancia global del cerebro de Obsidian
brain = ObsidianBrain()
