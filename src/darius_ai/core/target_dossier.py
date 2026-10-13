"""
target_dossier.py — Motor de Inteligencia y Dossiers Estructurados para DARIUS AI
==================================================================================
Genera fichas de inteligencia táctica estructuradas sobre personas, empresas, proyectos,
repositorios o tecnologías. Arquitectura táctica de síntesis de dossiers de Darius AI.

Características:
  1. Extracción de entidades estructuradas: biografía, carrera, enlaces sociales,
     ganchos de conversación (conversation hooks), y alertas de riesgo (risk flags).
  2. Persistencia automática en la bóveda local de Obsidian (`Darius/Dossiers/`)
     con Frontmatter YAML y callouts visuales de Markdown.
  3. Soporte opcional para búsqueda neuronal con Exa API (`EXA_API_KEY`) y fallback
     transparente al buscador de Darius.
  4. Generador de resúmenes fonéticos concisos para lectura fluida por TTS.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from src.darius_ai.core.ai_client import get_ai_response
from src.darius_ai.core.config_loader import cfg
from src.darius_ai.core.obsidian_brain import ObsidianBrain, brain

log = logging.getLogger("DARIUS.Dossier")


@dataclass
class TargetDossier:
    """Modelo estructurado para una Ficha de Inteligencia / Dossier."""

    target_name: str
    category: str = "person"  # person | company | repository | topic
    title_or_role: str = ""
    organization: str = ""
    summary: str = ""
    key_attributes: list[str] = field(default_factory=list)
    career_or_history: list[dict[str, str]] = field(default_factory=list)
    social_profiles: dict[str, str] = field(default_factory=dict)
    conversation_hooks: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence_score: float = 0.85
    generated_at: str = field(
        default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    def to_markdown(self) -> str:
        """Genera la representación completa en Markdown con Frontmatter YAML para Obsidian."""
        clean_name = self.target_name.replace('"', '\\"')
        clean_org = self.organization.replace('"', '\\"')

        social_yaml = "\n".join(f'  {k}: "{v}"' for k, v in self.social_profiles.items())
        sources_yaml = "\n".join(f'  - "{s}"' for s in self.sources)

        lines = [
            "---",
            f'target: "{clean_name}"',
            f"category: {self.category}",
            f'role: "{self.title_or_role}"',
            f'organization: "{clean_org}"',
            f"confidence_score: {self.confidence_score:.2f}",
            f"generated_at: {self.generated_at}",
            "tags:",
            "  - darius/dossier",
            f"  - intelligence/{self.category}",
        ]
        if self.social_profiles:
            lines.append("social_profiles:")
            lines.append(social_yaml)
        if self.sources:
            lines.append("sources:")
            lines.append(sources_yaml)
        lines.append("---\n")

        # Cuerpo del documento
        lines.append(f"# 🛡️ Dossier de Inteligencia: {self.target_name}\n")

        # Subtítulo de cargo / empresa
        role_line = f"**{self.title_or_role}**" if self.title_or_role else ""
        org_line = f" *({self.organization})*" if self.organization else ""
        if role_line or org_line:
            lines.append(f"> [!INFO] **Ficha:** {role_line}{org_line}\n")

        lines.append("## 📌 Resumen Ejecutivo")
        lines.append(self.summary or "Sin resumen disponible.")
        lines.append("")

        if self.key_attributes:
            lines.append("## ⚡ Atributos Clave y Especialidades")
            for attr in self.key_attributes:
                lines.append(f"- **{attr}**")
            lines.append("")

        if self.conversation_hooks:
            lines.append("## 🎯 Ganchos de Conversación (Conversation Hooks)")
            lines.append("> [!TIP] Temas ideales para romper el hielo o conectar:")
            for hook in self.conversation_hooks:
                lines.append(f"- 💡 {hook}")
            lines.append("")

        if self.career_or_history:
            lines.append("## 📜 Historial y Trayectoria")
            for item in self.career_or_history:
                role = item.get("role", "Rol")
                company = item.get("company", "")
                period = item.get("period", "")
                period_str = f" `[{period}]`" if period else ""
                lines.append(f"- **{role}** en *{company}*{period_str}")
            lines.append("")

        if self.risk_flags:
            lines.append("## ⚠️ Señales de Alerta (Risk Flags)")
            lines.append("> [!WARNING] Puntos de atención:")
            for flag in self.risk_flags:
                lines.append(f"- ⚠️ {flag}")
            lines.append("")

        if self.sources:
            lines.append("## 🔗 Fuentes y Referencias Verificadas")
            for src in self.sources:
                lines.append(f"- [{src}]({src})")
            lines.append("")

        return "\n".join(lines)

    def to_speech_summary(self) -> str:
        """Resumen fonético natural de 1 o 2 frases ideal para el motor de voz (TTS)."""
        role_part = f", {self.title_or_role}" if self.title_or_role else ""
        org_part = f" en {self.organization}" if self.organization else ""
        intro = f"Dossier de {self.target_name}{role_part}{org_part}."

        first_sentence = self.summary.split(".")[0].strip() if self.summary else ""
        if first_sentence:
            return f"{intro} {first_sentence}."
        return intro


DOSSIER_SYSTEM_PROMPT = """Eres el analista de inteligencia de DARIUS AI.
Tu tarea es sintetizar la información proporcionada sobre el objetivo en un objeto JSON estricto.
No agregues comentarios ni texto fuera del bloque JSON.

ESTRUCTURA JSON REQUERIDA:
{
  "target_name": "Nombre exacto del objetivo",
  "category": "person" | "company" | "repository" | "topic",
  "title_or_role": "Cargo, función o descripción breve",
  "organization": "Empresa, grupo o ecosistema",
  "summary": "Resumen ejecutivo claro y sustancial (2 a 4 frases)",
  "key_attributes": ["habilidad o fortaleza 1", "stack o tecnología 2"],
  "career_or_history": [
    {"role": "Cargo", "company": "Empresa/Proyecto", "period": "Año"}
  ],
  "social_profiles": {
    "github": "url_o_usuario",
    "linkedin": "url_o_usuario",
    "twitter": "url_o_usuario",
    "website": "url"
  },
  "conversation_hooks": [
    "Gancho de conversación 1 relevante para conectar",
    "Gancho 2"
  ],
  "risk_flags": [
    "Advertencia o inconsistencia relevante (si existe)"
  ],
  "sources": ["urls encontradas"],
  "confidence_score": 0.90
}
"""


class TargetDossierEngine:
    """
    Motor de investigación de objetivos y generación de dossiers.
    """

    def __init__(self):
        self._lock = threading.Lock()

    def query_exa_api(self, query: str, api_key: str | None = None) -> list[dict[str, Any]]:
        """
        Consulta la API neural de Exa si hay una clave disponible.
        Retorna una lista de resultados con título, url y fragmentos de texto.
        """
        key = api_key or os.environ.get("EXA_API_KEY") or cfg.get("exa_api_key", "")
        if not key:
            return []

        url = "https://api.exa.ai/search"
        payload = {
            "query": query,
            "type": "neural",
            "numResults": 5,
            "contents": {"text": {"maxCharacters": 800}},
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": key,
            "User-Agent": "Darius-AI/7.1.0",
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)  # noqa: S310
            with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results", [])
                hits = []
                for item in results:
                    text_content = ""
                    if isinstance(item.get("text"), str):
                        text_content = item.get("text", "")
                    hits.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": text_content[:500],
                    })
                return hits
        except Exception as e:
            log.debug(f"[Dossier] Exa API consulta falló o no respondió: {e}")
            return []

    def synthesize_dossier(
        self,
        target_name: str,
        category: str = "person",
        context: str = "",
        raw_research_text: str = "",
    ) -> TargetDossier:
        """
        Sintetiza la información de investigación en un objeto TargetDossier mediante el LLM activo.
        """
        prompt = (
            f"{DOSSIER_SYSTEM_PROMPT}\n\n"
            f"OBJETIVO: {target_name}\n"
            f"CATEGORÍA: {category}\n"
            f"CONTEXTO ADICIONAL: {context}\n\n"
            f"INFORMACIÓN RECOPILADA:\n{raw_research_text[:6000]}\n\n"
            "JSON:"
        )

        try:
            raw_response, _ = get_ai_response(prompt)
            match = re.search(r"\{[\s\S]*\}", raw_response)
            if match:
                data = json.loads(match.group(0))
                return TargetDossier(
                    target_name=data.get("target_name", target_name),
                    category=data.get("category", category),
                    title_or_role=data.get("title_or_role", ""),
                    organization=data.get("organization", ""),
                    summary=data.get("summary", ""),
                    key_attributes=data.get("key_attributes", []),
                    career_or_history=data.get("career_or_history", []),
                    social_profiles=data.get("social_profiles", {}),
                    conversation_hooks=data.get("conversation_hooks", []),
                    risk_flags=data.get("risk_flags", []),
                    sources=data.get("sources", []),
                    confidence_score=float(data.get("confidence_score", 0.85)),
                )
        except Exception as e:
            log.warning(f"[Dossier] Error estructurando JSON de dossier con IA: {e}")

        # Fallback si no fue posible parsear el JSON
        summary_text = ""
        if "raw_response" in locals() and raw_response and len(raw_response.strip()) > 10:
            summary_text = raw_response.strip()[:800]
        elif raw_research_text:
            summary_text = raw_research_text[:500]
        else:
            summary_text = f"Investigación sobre {target_name}."

        return TargetDossier(
            target_name=target_name,
            category=category,
            summary=summary_text,
            confidence_score=0.60,
        )

    def save_to_obsidian(
        self,
        dossier: TargetDossier,
        vault_brain: ObsidianBrain | None = None,
    ) -> str:
        """
        Guarda el dossier en la carpeta Darius/Dossiers/ dentro de la bóveda de Obsidian.
        Retorna la ruta del archivo generado.
        """
        b = vault_brain or brain
        safe_name = re.sub(r'[\\/*?:"<>| ]', "_", dossier.target_name).strip("_")
        relative_path = f"Darius/Dossiers/{dossier.category.capitalize()}/{safe_name}.md"

        content = dossier.to_markdown()

        if hasattr(b, "create_note"):
            b.create_note(relative_path, content)
        elif hasattr(b, "vault_path") and b.vault_path:
            full_path = os.path.join(b.vault_path, relative_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        log.info(f"[Dossier] Dossier de '{dossier.target_name}' guardado en Obsidian: {relative_path}")
        return relative_path


_GLOBAL_DOSSIER_ENGINE: TargetDossierEngine | None = None
_GLOBAL_DOSSIER_LOCK = threading.Lock()


def get_dossier_engine() -> TargetDossierEngine:
    """Retorna la instancia global del motor de dossiers."""
    global _GLOBAL_DOSSIER_ENGINE
    if _GLOBAL_DOSSIER_ENGINE is None:
        with _GLOBAL_DOSSIER_LOCK:
            if _GLOBAL_DOSSIER_ENGINE is None:
                _GLOBAL_DOSSIER_ENGINE = TargetDossierEngine()
    return _GLOBAL_DOSSIER_ENGINE
