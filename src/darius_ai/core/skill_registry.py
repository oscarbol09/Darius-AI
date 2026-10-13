"""
skill_registry.py — Registro dinámico de habilidades (Skills) y playbooks en Markdown para Darius AI
====================================================================================================
Arquitectura Nativa Darius AI. Permite a Darius AI descubrir,
registrar e inyectar habilidades procedimentales definidas en Markdown (Obsidian / local) directamente
en el catálogo de herramientas y planificador del asistente.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.darius_ai.core.config_loader import get_user_data_dir

log = logging.getLogger("DARIUS.SkillRegistry")


@dataclass
class SkillParam:
    name: str
    description: str = ""
    default: Any = ""


@dataclass
class SkillManifest:
    name: str
    description: str = ""
    parameters: list[SkillParam] = field(default_factory=list)
    required_tier: str = "trivial"
    playbook: str = ""


class SkillRegistry:
    """
    Registro y cargador dinámico de habilidades agénticas.
    """

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        if storage_dir is None:
            storage_dir = get_user_data_dir() / "skills"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, SkillManifest] = {}

    def register_skill(self, manifest: SkillManifest) -> None:
        """Registra imperativamente una habilidad."""
        self._skills[manifest.name] = manifest
        log.info(f"[SkillRegistry] Registrada habilidad: {manifest.name}")

    def get_skill(self, name: str) -> SkillManifest | None:
        """Obtiene una habilidad registrada por su nombre."""
        return self._skills.get(name)

    def list_skills(self) -> list[SkillManifest]:
        """Devuelve la lista de todas las habilidades registradas."""
        return list(self._skills.values())

    def discover_skills(self) -> dict[str, SkillManifest]:
        """
        Escanea archivos `.md` en el directorio de almacenamiento y extrae el frontmatter YAML
        y el cuerpo del procedimiento (playbook).
        """
        if not self.storage_dir.exists():
            return self._skills

        for file_path in self.storage_dir.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                # Parsear frontmatter simple entre ---
                fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, flags=re.DOTALL)
                if fm_match:
                    fm_text, playbook = fm_match.group(1), fm_match.group(2).strip()
                    meta: dict[str, str] = {}
                    for line in fm_text.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            meta[k.strip().lower()] = v.strip()

                    name = meta.get("name", file_path.stem)
                    desc = meta.get("description", "")
                    tier = meta.get("required_tier", "trivial")

                    manifest = SkillManifest(
                        name=name,
                        description=desc,
                        parameters=[],
                        required_tier=tier,
                        playbook=playbook,
                    )
                    self._skills[name] = manifest
            except Exception as exc:
                log.warning(f"[SkillRegistry] Error leyendo habilidad en {file_path}: {exc}")

        return self._skills

    def format_catalog_prompt(self) -> str:
        """
        Formatea el catálogo de habilidades como un bloque de texto descriptivo para el system prompt del LLM.
        """
        lines = ["HABILIDADES PROCEDIMENTALES DISPONIBLES:"]
        for s in self._skills.values():
            params_str = ", ".join(f"{p.name}: {p.description}" for p in s.parameters)
            params_sec = f" (Parámetros: {params_str})" if params_str else ""
            lines.append(f"- {s.name}{params_sec}: {s.description} [Riesgo: {s.required_tier}]")
        return "\n".join(lines)
