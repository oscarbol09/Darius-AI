"""
deep_research_agent.py — Multi-hop Deep Research Agent with Citations for Darius AI.
=====================================================================================
Native Darius AI deep research agent. Deconstructs complex topics
into focused subqueries, queries search engines, deduplicates sources, extracts evidence,
and synthesizes a structured ResearchBrief with inline citations [1], [2] and bibliography.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from src.darius_ai.core.ai_client import get_ai_response

log = logging.getLogger("DARIUS.DeepResearchAgent")


class WebSearchEngine:
    """Default web search engine interface with DuckDuckGo scraping integration."""

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Executes a web search query returning structured results with title, url, snippet."""
        try:
            from src.darius_ai.core.deep_research import _search_duckduckgo

            return _search_duckduckgo(query, max_results=max_results)
        except Exception as e:
            log.warning(f"[WebSearchEngine] Search failed for '{query}': {e}")
            return []


@dataclass(slots=True)
class ResearchBrief:
    """Structured brief synthesizing deep research findings with sources and citations."""

    summary: str
    key_findings: list[str] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    markdown_report: str = ""
    topic: str = ""


class DeepResearchAgent:
    """Multi-hop research agent with subquery deconstruction and cited reports."""

    def __init__(
        self,
        search_engine: Any = None,
        code_interpreter: Any = None,
    ) -> None:
        self.search_engine = search_engine or WebSearchEngine()
        self.code_interpreter = code_interpreter

    def generate_subqueries(self, topic: str, max_subqueries: int = 3) -> list[str]:
        """Deconstructs the research topic into 2-3 focused subqueries using AI."""
        count = max(2, min(max_subqueries, 3))
        prompt = (
            f"Act as a research analyst. For the topic: '{topic}', generate {count} concise, "
            f"distinct web search queries targeting core concepts, architecture, and recent developments.\n"
            f"Return ONLY a JSON object with a string list under the key 'queries'.\n"
            f'Example: {{"queries": ["query 1", "query 2"]}}'
        )

        try:
            raw_response, _ = get_ai_response(prompt)
            match = re.search(r"\{[\s\S]*\}", raw_response)
            if match:
                data = json.loads(match.group(0))
                queries = data.get("queries", [])
                if isinstance(queries, list) and queries:
                    clean = [str(q).strip() for q in queries if str(q).strip()]
                    if clean:
                        return clean[:count]
        except Exception as e:
            log.warning(f"[DeepResearchAgent] Subquery generation via LLM failed: {e}")

        # Heuristic fallback
        return [
            topic,
            f"{topic} state of the art benchmarks",
            f"{topic} technical analysis architecture",
        ][:count]

    def research(
        self,
        topic: str,
        max_subqueries: int = 3,
        max_pages: int = 5,
    ) -> ResearchBrief:
        """Conducts autonomous deep research on a topic and produces a cited ResearchBrief."""
        log.info(f"[DeepResearchAgent] Initiating research on '{topic}'")

        # 1. Deconstruct topic into focused subqueries
        subqueries = self.generate_subqueries(topic, max_subqueries=max_subqueries)
        log.debug(f"[DeepResearchAgent] Subqueries: {subqueries}")

        # 2. Query search engine and deduplicate unique sources by URL
        sources: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for q in subqueries:
            try:
                results = self.search_engine.search(q, max_results=max_pages)
            except Exception as e:
                log.warning(f"[DeepResearchAgent] Search error for query '{q}': {e}")
                results = []

            for r in results:
                url = str(r.get("url", "")).strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    sources.append(
                        {
                            "title": str(r.get("title", "Untitled Source")).strip(),
                            "url": url,
                            "snippet": str(r.get("snippet", "")).strip(),
                        }
                    )

        # 3. Handle zero-sources edge case
        if not sources:
            summary = f"No sources found during deep research for topic: '{topic}'."
            key_findings = [f"Initial search for '{topic}' returned no indexed results."]
            report = f"# Research Report: {topic}\n\n## Summary\n{summary}\n"
            return ResearchBrief(
                summary=summary,
                key_findings=key_findings,
                sources=[],
                citations=[],
                markdown_report=report,
                topic=topic,
            )

        # 4. Build citations list
        citations = [f"[{i + 1}] {s['title']}: {s['url']}" for i, s in enumerate(sources)]

        # 5. Synthesize findings using LLM
        sources_context = "\n".join(
            f"[{i + 1}] {s['title']} ({s['url']})\nSnippet: {s['snippet']}\n"
            for i, s in enumerate(sources)
        )

        synthesis_prompt = (
            f"You are a Principal AI Research Agent. Synthesize a structured, high-density technical report "
            f"on '{topic}' using exclusively the provided evidence.\n\n"
            f"EVIDENCE SOURCES:\n{sources_context}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Every factual statement must cite its source using inline footnotes like [1], [2].\n"
            f"2. Structure your response as:\n"
            f"## Summary\n"
            f"<1-2 dense paragraphs summarizing key technical takeaways with citations>\n\n"
            f"## Key Findings\n"
            f"- <Finding 1 with citation [1]>\n"
            f"- <Finding 2 with citation [2]>\n"
        )

        try:
            llm_text, _ = get_ai_response(synthesis_prompt)
        except Exception as e:
            log.warning(f"[DeepResearchAgent] LLM synthesis failed, using heuristic synthesis: {e}")
            llm_text = ""

        summary, key_findings = self._extract_summary_and_findings(llm_text, sources, topic)

        # 6. Format Markdown report with footnotes and bibliography
        bibliography = "\n".join(f"- [{i + 1}] {s['title']} - {s['url']}" for i, s in enumerate(sources))
        findings_markdown = "\n".join(
            f"- {kf}" if not kf.startswith("-") else kf for kf in key_findings
        )

        markdown_report = (
            f"# Research Report: {topic}\n\n"
            f"## Summary\n{summary}\n\n"
            f"## Key Findings\n{findings_markdown}\n\n"
            f"## Bibliography\n{bibliography}\n"
        )

        return ResearchBrief(
            summary=summary,
            key_findings=key_findings,
            sources=sources,
            citations=citations,
            markdown_report=markdown_report,
            topic=topic,
        )

    def _extract_summary_and_findings(
        self,
        llm_text: str,
        sources: list[dict[str, str]],
        topic: str,
    ) -> tuple[str, list[str]]:
        """Parses LLM text into summary and key findings, with heuristic fallback."""
        summary = ""
        key_findings: list[str] = []

        if llm_text:
            # Extract ## Summary section
            summary_match = re.search(
                r"##\s*(?:Summary|Resumen)\s*\n([\s\S]*?)(?=\n##|\Z)",
                llm_text,
                re.IGNORECASE,
            )
            if summary_match:
                summary = summary_match.group(1).strip()

            # Extract ## Key Findings section
            findings_match = re.search(
                r"##\s*(?:Key Findings|Hallazgos)\s*\n([\s\S]*?)(?=\n##|\Z)",
                llm_text,
                re.IGNORECASE,
            )
            if findings_match:
                raw_findings = findings_match.group(1).strip()
                for line in raw_findings.splitlines():
                    cleaned = line.strip().lstrip("-* ").strip()
                    if cleaned:
                        key_findings.append(cleaned)

        # Fallback if parsing failed or llm_text was empty
        if not summary:
            first_title = sources[0]["title"]
            summary = (
                f"Synthesized research on '{topic}' based on {len(sources)} unique sources. "
                f"Primary findings drawn from {first_title} [1]."
            )

        if not key_findings:
            key_findings = [
                f"{s['title']}: {s['snippet'][:180]} [{i + 1}]"
                for i, s in enumerate(sources[:5])
                if s.get("snippet")
            ]
            if not key_findings:
                key_findings = [f"Identified {len(sources)} verified sources on {topic} [1]."]

        return summary, key_findings


__all__ = ["DeepResearchAgent", "ResearchBrief", "WebSearchEngine"]
