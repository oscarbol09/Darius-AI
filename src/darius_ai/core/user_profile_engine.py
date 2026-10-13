"""user_profile_engine.py — Perfil de usuario dinámico y memoria en Markdown para DARIUS AI
======================================================================================
Gestiona la memoria declarativa y perfil del usuario en formato Markdown persistente (USER.md / User_Profile.md).
Permite lectura estructurada por categorías, mutaciones seguras (thread-safe), extracción heurística de hechos
desde el diálogo del usuario e inyección compacta en el prompt del sistema sin token bloat.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Final

from src.darius_ai.core.config_loader import cfg, get_user_data_dir

log = logging.getLogger("DARIUS.UserProfile")

DEFAULT_CATEGORIES: Final[list[str]] = [
    "Identidad y Rol",
    "Preferencias y Estilo",
    "Proyectos Activos",
    "Stack Tecnológico",
    "Restricciones y Hábitos",
]

_CATEGORY_ALIASES: Final[dict[str, str]] = {
    "identidad": "Identidad y Rol",
    "rol": "Identidad y Rol",
    "identidad y rol": "Identidad y Rol",
    "identity": "Identidad y Rol",
    "role": "Identidad y Rol",
    "preferencias": "Preferencias y Estilo",
    "estilo": "Preferencias y Estilo",
    "preferencias y estilo": "Preferencias y Estilo",
    "preferences": "Preferencias y Estilo",
    "style": "Preferencias y Estilo",
    "proyectos": "Proyectos Activos",
    "proyecto": "Proyectos Activos",
    "proyectos activos": "Proyectos Activos",
    "projects": "Proyectos Activos",
    "stack": "Stack Tecnológico",
    "tecnologia": "Stack Tecnológico",
    "tecnología": "Stack Tecnológico",
    "tecnologias": "Stack Tecnológico",
    "tecnologías": "Stack Tecnológico",
    "stack tecnológico": "Stack Tecnológico",
    "stack tecnologico": "Stack Tecnológico",
    "tech": "Stack Tecnológico",
    "tech stack": "Stack Tecnológico",
    "restricciones": "Restricciones y Hábitos",
    "habitos": "Restricciones y Hábitos",
    "hábitos": "Restricciones y Hábitos",
    "restricciones y hábitos": "Restricciones y Hábitos",
    "restricciones y habitos": "Restricciones y Hábitos",
    "constraints": "Restricciones y Hábitos",
    "habits": "Restricciones y Hábitos",
}


class UserProfileEngine:
    """Motor de perfil dinámico de usuario con almacenamiento en Markdown persistente y thread-safe."""

    def __init__(self, profile_path: Path | str | None = None) -> None:
        self._lock = threading.RLock()
        if profile_path is not None:
            self._profile_path = Path(profile_path).expanduser().resolve()
        else:
            self._profile_path = self._resolve_default_path()

    @property
    def profile_path(self) -> Path:
        """Ruta al archivo Markdown del perfil."""
        return self._profile_path

    @staticmethod
    def _resolve_default_path() -> Path:
        """Determina la ruta por defecto: vault de Obsidian o AppData/user_data_dir."""
        try:
            vault_dir: Path | None = None
            if hasattr(cfg, "obsidian_vault_path") and cfg.obsidian_vault_path:
                vault_dir = Path(cfg.obsidian_vault_path).expanduser().resolve()
            else:
                default_vault = Path.home() / "Documents" / "Obsidian Vault"
                if default_vault.exists():
                    vault_dir = default_vault

            if vault_dir and vault_dir.exists():
                obsidian_file = vault_dir / "Darius" / "User_Profile.md"
                obsidian_file.parent.mkdir(parents=True, exist_ok=True)
                return obsidian_file
        except OSError as e:
            log.warning("No se pudo resolver la ruta en Obsidian Vault: %s. Usando fallback local.", e)

        data_dir = get_user_data_dir()
        return data_dir / "USER.md"

    def _canonicalize_category(self, category: str) -> str:
        """Normaliza categorías conocidas mediante alias o preserva títulos personalizados."""
        cat_clean = category.strip()
        return _CATEGORY_ALIASES.get(cat_clean.lower(), cat_clean)


    def _read_profile_unlocked(self) -> dict[str, list[str]]:
        """Lectura interna del perfil sin adquirir candado (requiere lock externo)."""
        profile: dict[str, list[str]] = {cat: [] for cat in DEFAULT_CATEGORIES}
        if not self._profile_path.exists():
            return profile

        try:
            content = self._profile_path.read_text(encoding="utf-8")
        except OSError as e:
            log.error("Error leyendo archivo de perfil %s: %s", self._profile_path, e)
            return profile

        current_category: str | None = None
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("## "):
                raw_header = line_str[3:].strip()
                current_category = self._canonicalize_category(raw_header)
                if current_category not in profile:
                    profile[current_category] = []
            elif (line_str.startswith("- ") or line_str.startswith("* ")) and current_category is not None:
                fact = line_str[2:].strip()
                if fact and fact not in profile[current_category]:
                    profile[current_category].append(fact)

        return profile

    def _write_profile_unlocked(self, profile: dict[str, list[str]]) -> None:
        """Escritura atómica/interna del perfil (requiere lock externo)."""
        self._profile_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = ["# Perfil del Usuario", ""]

        for category, facts in profile.items():
            lines.append(f"## {category}")
            for fact in facts:
                lines.append(f"- {fact}")
            lines.append("")

        content = "\n".join(lines).strip() + "\n"
        self._profile_path.write_text(content, encoding="utf-8")

    def read_profile(self) -> dict[str, list[str]]:
        """Retorna las secciones y hechos del perfil del usuario."""
        with self._lock:
            return self._read_profile_unlocked()

    def add_fact(self, category: str, fact: str) -> bool:
        """Añade un hecho a la categoría especificada. Deduplica entradas existentes."""
        clean_fact = fact.strip()
        if not clean_fact:
            return False

        canonical_cat = self._canonicalize_category(category)

        with self._lock:
            profile = self._read_profile_unlocked()
            entries = profile.setdefault(canonical_cat, [])

            if any(existing.lower() == clean_fact.lower() for existing in entries):
                return False

            entries.append(clean_fact)
            self._write_profile_unlocked(profile)
            return True

    def update_fact(self, category: str, old_fact: str, new_fact: str) -> bool:
        """Actualiza un hecho existente dentro de una categoría."""
        clean_old = old_fact.strip()
        clean_new = new_fact.strip()
        if not clean_old or not clean_new:
            return False

        canonical_cat = self._canonicalize_category(category)

        with self._lock:
            profile = self._read_profile_unlocked()
            if canonical_cat not in profile:
                return False

            entries = profile[canonical_cat]
            match_idx = -1
            for idx, item in enumerate(entries):
                if item.lower() == clean_old.lower():
                    match_idx = idx
                    break

            if match_idx == -1:
                return False

            entries[match_idx] = clean_new
            self._write_profile_unlocked(profile)
            return True

    def remove_fact(self, category: str, fact: str) -> bool:
        """Elimina un hecho existente de la categoría especificada."""
        clean_fact = fact.strip()
        if not clean_fact:
            return False

        canonical_cat = self._canonicalize_category(category)

        with self._lock:
            profile = self._read_profile_unlocked()
            if canonical_cat not in profile:
                return False

            entries = profile[canonical_cat]
            match_idx = -1
            for idx, item in enumerate(entries):
                if item.lower() == clean_fact.lower():
                    match_idx = idx
                    break

            if match_idx == -1:
                return False

            entries.pop(match_idx)
            self._write_profile_unlocked(profile)
            return True

    def extract_facts_from_text(self, text: str) -> list[tuple[str, str]]:
        """Extrae heurísticamente hechos duraderos a partir de declaraciones en lenguaje natural."""
        raw_text = (text or "").strip()
        if not raw_text:
            return []

        # Segmentar texto por saltos de línea o puntuación delimitadora (. ! ?)
        sentences = [s.strip() for s in re.split(r"[\r\n.!?]+", raw_text) if s.strip()]
        results: list[tuple[str, str]] = []
        seen_keys: set[str] = set()

        for sentence in sentences:
            # Sub-segmentar si hay cláusulas compuestas separadas por coma o 'y' que inicien un patrón clave
            clauses = re.split(
                r",\s*(?=(?:soy|mi\s+rol|trabajo\s+como|prefiero|me\s+gusta|no\s+me\s+gusta|odio|evita|mi\s+proyecto|estoy\s+construyendo|estoy\s+desarrollando|uso|utilizo|mi\s+stack|i\s+use|i\s+prefer|i\s+like|i\s+don't\s+like)\b)",
                sentence,
                flags=re.IGNORECASE,
            )

            for clause in clauses:
                clean_clause = clause.strip()
                if not clean_clause:
                    continue

                fact_extracted: tuple[str, str] | None = self._evaluate_clause_heuristics(clean_clause)
                if fact_extracted:
                    cat, fact = fact_extracted
                    dedup_key = f"{cat}::{fact.lower()}"
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        results.append((cat, fact))

        return results

    def _evaluate_clause_heuristics(self, clause: str) -> tuple[str, str] | None:
        """Evalúa una cláusula individual contra las heurísticas de cada categoría."""
        # 1. Restricciones y Hábitos (prevalencia sobre preferencias para 'no me gusta')
        m_restr = re.search(
            r"\b(?:no\s+me\s+gusta|no\s+soporto|no\s+quiero\s+que|no\s+quiero|no\s+uses|no\s+utilices|"
            r"odio|detesto|evita|evitar|nunca|jamás|prohibido|i\s+don't\s+like|avoid|never)\s+(.+)",
            clause,
            re.IGNORECASE,
        )
        if m_restr:
            fact_text = clause[m_restr.start():].strip()
            return ("Restricciones y Hábitos", self._format_fact(fact_text))

        # 2. Preferencias y Estilo
        m_pref = re.search(
            r"\b(?:prefiero|mi\s+preferencia\s+es|me\s+gusta|i\s+prefer|i\s+like)\s+(.+)",
            clause,
            re.IGNORECASE,
        )
        if m_pref:
            fact_text = clause[m_pref.start():].strip()
            return ("Preferencias y Estilo", self._format_fact(fact_text))

        # 3. Proyectos Activos
        m_proj = re.search(
            r"\b(?:(?:actualmente\s+)?mi\s+proyecto(?:\s+actual)?\s+es|estoy\s+construyendo|"
            r"estoy\s+desarrollando|estoy\s+creando|trabajando\s+en(?:\s+el\s+proyecto)?|"
            r"my\s+project\s+is|working\s+on)\s+(.+)",
            clause,
            re.IGNORECASE,
        )
        if m_proj:
            fact_text = clause[m_proj.start():].strip()
            return ("Proyectos Activos", self._format_fact(fact_text))

        # 4. Stack Tecnológico
        m_tech = re.search(
            r"\b(?:(?:yo\s+)?(?:uso|utilizo|programo\s+en|mi\s+stack\s+es|desarrollo\s+con)|"
            r"i\s+use|my\s+stack\s+is)\s+(.+)",
            clause,
            re.IGNORECASE,
        )
        if m_tech:
            fact_text = clause[m_tech.start():].strip()
            return ("Stack Tecnológico", self._format_fact(fact_text))

        # 5. Identidad y Rol
        m_id = re.search(
            r"\b(?:soy|mi\s+rol\s+es|trabajo\s+como|me\s+llamo|mi\s+nombre\s+es|"
            r"i\s+am(?:\s+(?:a|an))?|my\s+role\s+is|my\s+name\s+is)\s+(.+)",
            clause,
            re.IGNORECASE,
        )
        if m_id:
            fact_text = clause[m_id.start():].strip()
            return ("Identidad y Rol", self._format_fact(fact_text))

        return None

    @staticmethod
    def _format_fact(text: str) -> str:
        """Formatea y sanitiza el texto del hecho."""
        clean = text.strip(" \t\n\r.,;").strip()
        if not clean:
            return ""
        # Capitalizar primera letra preservando el resto
        return clean[0].upper() + clean[1:]


    def get_profile_prompt_injection(self) -> str:
        """Genera un fragmento compacto en Markdown para inyectar en el prompt del sistema."""
        profile = self.read_profile()
        sections: list[str] = []

        for category, facts in profile.items():
            if facts:
                bullet_lines = "\n".join(f"- {f}" for f in facts)
                sections.append(f"**{category}**:\n{bullet_lines}")

        if not sections:
            return ""

        body = "\n\n".join(sections)
        return f"### Perfil de Usuario\n{body}\n"


__all__ = ["DEFAULT_CATEGORIES", "UserProfileEngine"]
