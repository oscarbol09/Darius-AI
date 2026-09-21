"""
deep_research.py — Pipeline de Investigación Profunda y Síntesis Web para DARIUS AI
====================================================================================
Realiza investigaciones autónomas multi-fuente sobre cualquier tema técnico o consulta:
  1. Generación dinámica de sub-consultas de búsqueda optimizadas con el LLM activo.
  2. Búsqueda y recopilación web multi-fuente (DuckDuckGo / scraping HTTP).
  3. Extracción de contenido, limpieza HTML y eliminación de duplicados.
  4. Síntesis analítica estructurada con citas y referencias explícitas.
  5. Persistencia automática del informe en la bóveda de Obsidian (`Darius/Investigaciones/`).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from ai_client import get_ai_response
from config_loader import cfg
from obsidian_brain import brain

log = logging.getLogger("DARIUS.Research")

# Configuración de profundidad
DEPTH_CONFIG = {
    "quick": {"queries": 2, "max_sources": 5},
    "standard": {"queries": 4, "max_sources": 10},
    "deep": {"queries": 6, "max_sources": 18},
}


def _clean_html_text(html_content: str) -> str:
    """Limpia el HTML extrayendo únicamente el texto legible."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
    except Exception:
        # Fallback regex simple
        text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:4000]


def _search_duckduckgo(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Busca en la web mediante el endpoint público de DuckDuckGo o HTML scraper."""
    results: list[dict[str, str]] = []
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_q}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",  # noqa: E501
    }
    req = urllib.request.Request(url, headers=headers)  # noqa: S310

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            html_doc = resp.read().decode("utf-8", errors="ignore")

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_doc, "html.parser")
            for result_div in soup.find_all("div", class_="result"):
                title_tag = result_div.find("a", class_="result__a")
                snippet_tag = result_div.find("a", class_="result__snippet")

                if title_tag:
                    title = title_tag.get_text(strip=True)
                    raw_href = title_tag.get("href", "")
                    # Extraer URL real de DuckDuckGo uddg redirect
                    if "uddg=" in raw_href:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                        link = parsed.get("uddg", [raw_href])[0]
                    else:
                        link = raw_href

                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    if link.startswith("http"):
                        results.append({
                            "title": title,
                            "url": link,
                            "snippet": snippet,
                        })
                if len(results) >= max_results:
                    break
        except Exception as parse_err:
            log.debug(f"Error parseando resultados DuckDuckGo: {parse_err}")

    except Exception as e:
        log.warning(f"[DeepResearch] Fallo al buscar query '{query}': {e}")

    return results


def _fetch_page_content(url: str, timeout: int = 8) -> str:
    """Descarga y extrae el texto principal de una página web."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    req = urllib.request.Request(url, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw_html = resp.read().decode("utf-8", errors="ignore")
            return _clean_html_text(raw_html)
    except Exception as e:
        log.debug(f"[DeepResearch] No se pudo leer {url}: {e}")
        return ""


class DeepResearchPipeline:
    """
    Pipeline autónomo de investigación profunda.
    """

    def generate_search_queries(self, topic: str, count: int = 3) -> list[str]:
        """Utiliza el LLM para generar sub-consultas de búsqueda efectivas."""
        prompt = (
            f"Actúa como un analista de investigación. Para el tema: '{topic}', "
            f"genera {count} consultas de búsqueda en Google/DuckDuckGo breves y precisas "
            f"para encontrar información técnica, datos actuales y análisis de fondo.\n"
            f"Devuelve ÚNICAMENTE un objeto JSON con una lista de strings en la clave 'queries'. "
            f"Ejemplo: {{\"queries\": [\"query 1\", \"query 2\"]}}"
        )
        try:
            raw, _ = get_ai_response(prompt)
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group(0))
                queries = data.get("queries", [])
                if isinstance(queries, list) and queries:
                    return [str(q).strip() for q in queries[:count] if str(q).strip()]
        except Exception as e:
            log.warning(f"[DeepResearch] Error generando queries con IA: {e}")

        # Fallback heurístico
        return [topic, f"{topic} características análisis", f"{topic} arquitectura documentación"]

    def run_research(
        self,
        topic: str,
        depth: str = "standard",
        save_to_obsidian: bool = True,
        speak_fn: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """
        Ejecuta el ciclo completo de investigación profunda y retorna el informe y metadata.
        """
        depth_key = depth.lower() if depth.lower() in DEPTH_CONFIG else "standard"
        config = DEPTH_CONFIG[depth_key]

        if speak_fn:
            speak_fn(f"Iniciando investigación profunda sobre {topic}.")

        log.info(f"[DeepResearch] Iniciando investigación sobre '{topic}' (Profundidad: {depth_key})")

        # 1. Generar sub-consultas
        queries = self.generate_search_queries(topic, count=config["queries"])
        log.info(f"[DeepResearch] Queries generadas: {queries}")

        # 2. Recopilar fuentes web
        sources: list[dict[str, str]] = []
        seen_urls = set()

        for q in queries:
            results = _search_duckduckgo(q, max_results=4)
            for r in results:
                url = r["url"]
                if url not in seen_urls:
                    seen_urls.add(url)
                    sources.append(r)
                if len(sources) >= config["max_sources"]:
                    break
            if len(sources) >= config["max_sources"]:
                break

        # 3. Extraer contenido de las principales fuentes
        extracted_evidence = []
        for i, src in enumerate(sources[:6]):
            content = _fetch_page_content(src["url"])
            if content and len(content) > 100:
                extracted_evidence.append(
                    f"--- FUENTE [{i+1}]: {src['title']} ({src['url']}) ---\n{content[:1500]}\n"
                )

        evidence_text = "\n".join(extracted_evidence)
        if not evidence_text:
            evidence_text = "No se pudo extraer contenido completo de las páginas, usando snippets de búsqueda."
            for _i, src in enumerate(sources):
                evidence_text += f"\n- {src['title']}: {src['snippet']} ({src['url']})"

        # 4. Sintetizar informe final con el LLM
        synthesis_prompt = (
            f"Eres un investigador senior de {cfg.assistant_name}. "
            f"Elabora un informe técnico, riguroso, estructurado y exhaustivo sobre el tema: '{topic}'.\n\n"
            f"[EVIDENCIA Y CONTENIDO RECOPILADO DE LA WEB]:\n"
            f"{evidence_text[:12000]}\n\n"
            f"ESTRUCTURA DEL INFORME (Markdown profesional en español):\n"
            f"## 1. Resumen Ejecutivo\n"
            f"(Visión general y conclusiones clave en 1-2 párrafos claros)\n\n"
            f"## 2. Hallazgos y Análisis Detallado\n"
            f"(Puntos técnicos, datos, arquitectura, comparativas y conceptos esenciales)\n\n"
            f"## 3. Implicaciones y Recomendaciones\n"
            f"(Buenas prácticas, consideraciones prácticas para el usuario)\n\n"
            f"Redacta con autoridad, claridad y alta densidad técnica, evitando generalidades."
        )

        try:
            report_body, provider = get_ai_response(synthesis_prompt)
        except Exception as e:
            report_body = f"Error al sintetizar el informe con IA: {e}"
            provider = "error"

        # 5. Guardar en Obsidian si está habilitado
        saved_path = None
        if save_to_obsidian:
            try:
                saved_path = brain.save_research_report(topic=topic, content=report_body, sources=sources)
                log.info(f"[DeepResearch] Informe guardado en: {saved_path}")
            except Exception as e:
                log.error(f"[DeepResearch] No se pudo guardar en Obsidian: {e}")

        # Resumen breve para TTS / feedback verbal
        short_summary = (
            f"Investigación completada sobre {topic}. "
            f"He analizado {len(sources)} fuentes web y guardado el informe completo en tu Obsidian."
        )

        if speak_fn:
            speak_fn(short_summary)

        return {
            "ok": True,
            "topic": topic,
            "report": report_body,
            "summary": short_summary,
            "sources": sources,
            "sources_count": len(sources),
            "obsidian_path": str(saved_path) if saved_path else "",
            "provider": provider,
        }


# Instancia singleton del pipeline de investigación profunda
research_pipeline = DeepResearchPipeline()
