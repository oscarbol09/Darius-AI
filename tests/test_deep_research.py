"""
test_deep_research.py — Pruebas unitarias para el pipeline de investigación profunda
y DeepResearchAgent en Darius AI.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.darius_ai.core.deep_research import (
    DeepResearchPipeline,
    _clean_html_text,
    _fetch_page_content,
)
from src.darius_ai.core.deep_research_agent import (
    DeepResearchAgent,
    ResearchBrief,
    WebSearchEngine,
)
from src.darius_ai.core.obsidian_brain import ObsidianBrain


def test_clean_html_text():
    """Valida la limpieza y desinfección de texto HTML."""
    sample_html = """
    <html>
        <head><title>Test</title><script>var x = 1;</script></head>
        <body>
            <header>Cabecera a descartar</header>
            <h1>Título Importante</h1>
            <p>Este es el <b>contenido</b> principal de la investigación.</p>
            <footer>Pie de página</footer>
        </body>
    </html>
    """
    cleaned = _clean_html_text(sample_html)
    assert "Título Importante" in cleaned
    assert "contenido principal" in cleaned
    assert "var x = 1" not in cleaned


def test_generate_search_queries_mocked():
    """Verifica que el generador de queries produzca una lista válida."""
    pipeline = DeepResearchPipeline()

    mock_llm_response = '{"queries": ["python async memory leak", "python tracemalloc debug", "python gc tuning"]}'
    with patch("src.darius_ai.core.deep_research.get_ai_response", return_value=(mock_llm_response, "Gemini")):
        queries = pipeline.generate_search_queries("fugas de memoria en python", count=3)
        assert len(queries) == 3
        assert "python async memory leak" in queries


def test_generate_search_queries_fallback():
    """Verifica que si el LLM falla, se generen consultas heurísticas de rescate."""
    pipeline = DeepResearchPipeline()
    with patch("src.darius_ai.core.deep_research.get_ai_response", side_effect=Exception("Timeout")):
        queries = pipeline.generate_search_queries("Rust async tokio", count=3)
        assert len(queries) == 3
        assert any("Rust async tokio" in q for q in queries)


def test_fetch_page_content_handles_errors():
    """Verifica que URLs inválidas o con fallos de red devuelvan string vacío sin excepciones."""
    res = _fetch_page_content("http://127.0.0.1:9999/nonexistent-dummy-path-xyz")
    assert res == ""


def test_run_research_full_flow_mocked():
    """Verifica el flujo completo de investigación y persistencia en Obsidian."""
    pipeline = DeepResearchPipeline()

    mock_sources = [
        {"title": "Doc 1", "url": "https://example.com/1", "snippet": "Info sobre rendimiento"},
        {"title": "Doc 2", "url": "https://example.com/2", "snippet": "Detalles técnicos"},
    ]

    mock_report = "## 1. Resumen Ejecutivo\n\nEl sistema es altamente eficiente."

    with tempfile.TemporaryDirectory() as tmpdir:
        test_brain = ObsidianBrain(vault_path=tmpdir)

        with (
            patch.object(pipeline, "generate_search_queries", return_value=["query 1"]),
            patch("src.darius_ai.core.deep_research._search_duckduckgo", return_value=mock_sources),
            patch("src.darius_ai.core.deep_research._fetch_page_content", return_value="Contenido extraído de prueba"),
            patch("src.darius_ai.core.deep_research.get_ai_response", return_value=(mock_report, "OpenAI")),
            patch("src.darius_ai.core.deep_research.brain", test_brain),
        ):
            spoken_messages = []
            res = pipeline.run_research(
                topic="Arquitectura de Microservicios",
                depth="quick",
                save_to_obsidian=True,
                speak_fn=spoken_messages.append,
            )

            assert res["ok"] is True
            assert res["topic"] == "Arquitectura de Microservicios"
            assert len(res["sources"]) == 2
            assert "Investigación completada" in res["summary"]
            assert len(spoken_messages) == 2

            # Validar que el archivo se creó en Obsidian
            report_path = Path(res["obsidian_path"])
            assert report_path.exists()
            content = report_path.read_text(encoding="utf-8")
            assert "Informe de Investigación: Arquitectura de Microservicios" in content
            assert "https://example.com/1" in content


def test_run_research_no_obsidian_and_synthesis_error():
    """Verifica la ejecución cuando save_to_obsidian es False y el LLM falla en la síntesis."""
    pipeline = DeepResearchPipeline()

    with (
        patch.object(pipeline, "generate_search_queries", return_value=["query test"]),
        patch("src.darius_ai.core.deep_research._search_duckduckgo", return_value=[]),
        patch("src.darius_ai.core.deep_research.get_ai_response", side_effect=RuntimeError("LLM out of quota")),
    ):
        res = pipeline.run_research(
            topic="Test Offline",
            depth="quick",
            save_to_obsidian=False,
        )
        assert res["ok"] is True
        assert res["obsidian_path"] == ""
        assert "Error al sintetizar el informe" in res["report"]


# ============================================================================
# DeepResearchAgent Tests
# ============================================================================


def test_research_brief_structure():
    """Validates ResearchBrief dataclass attributes."""
    brief = ResearchBrief(
        summary="Brief summary of research",
        key_findings=["Finding A", "Finding B"],
        sources=[{"title": "Source 1", "url": "https://source1.org", "snippet": "Snippet 1"}],
        citations=["[1] Source 1: https://source1.org"],
        markdown_report="# Report\n\nContent [1]\n\n## Sources\n- [1] Source 1",
        topic="Sample Topic",
    )
    assert brief.summary == "Brief summary of research"
    assert len(brief.key_findings) == 2
    assert len(brief.sources) == 1
    assert brief.citations[0].startswith("[1]")
    assert "[1]" in brief.markdown_report
    assert brief.topic == "Sample Topic"


def test_web_search_engine_default_or_mock():
    """Validates WebSearchEngine interface and results."""
    mock_engine = MagicMock(spec=WebSearchEngine)
    mock_engine.search.return_value = [
        {"title": "T1", "url": "https://t1.com", "snippet": "S1"},
    ]
    results = mock_engine.search("query", max_results=5)
    assert len(results) == 1
    assert results[0]["title"] == "T1"


def test_deep_research_agent_subqueries_deconstruction():
    """Validates that DeepResearchAgent splits a topic into 2-3 focused subqueries."""
    mock_search = MagicMock()
    mock_search.search.return_value = []

    agent = DeepResearchAgent(search_engine=mock_search)

    mock_llm_json = '{"queries": ["quantum computing qubits", "quantum error correction", "quantum supremacy"]}'
    with patch("src.darius_ai.core.deep_research_agent.get_ai_response", return_value=(mock_llm_json, "Gemini")):
        subqueries = agent.generate_subqueries("Computación Cuántica", max_subqueries=3)
        assert 2 <= len(subqueries) <= 3
        assert "quantum computing qubits" in subqueries


def test_deep_research_agent_subqueries_fallback():
    """Validates heuristic subquery generation when LLM fails."""
    mock_search = MagicMock()
    agent = DeepResearchAgent(search_engine=mock_search)

    with patch("src.darius_ai.core.deep_research_agent.get_ai_response", side_effect=RuntimeError("AI Offline")):
        subqueries = agent.generate_subqueries("Deep Learning Transformers", max_subqueries=3)
        assert len(subqueries) <= 3
        assert any("Deep Learning Transformers" in q for q in subqueries)


def test_deep_research_agent_full_research_workflow():
    """Validates full end-to-end research synthesis with citations and bibliography."""
    mock_search = MagicMock()

    # Search results with duplicate URLs across queries to test deduplication
    mock_search.search.side_effect = [
        [
            {"title": "Quantum Supremacy Nature", "url": "https://nature.com/quantum", "snippet": "Major milestone"},
            {"title": "IBM Quantum Roadmap", "url": "https://ibm.com/quantum", "snippet": "1000 qubits by 2025"},
        ],
        [
            # Duplicate URL
            {"title": "Quantum Milestone", "url": "https://nature.com/quantum", "snippet": "Repetition"},
            {"title": "Google Quantum AI", "url": "https://quantumai.google", "snippet": "Willow chip breakthrough"},
        ],
    ]

    agent = DeepResearchAgent(search_engine=mock_search)

    # Synthesis LLM response
    synthesis_llm_response = (
        "## Summary\n"
        "Quantum computing has achieved significant milestones [1], "
        "expanding processor scales [2] and error suppression [3].\n\n"
        "## Key Findings\n"
        "- Quantum advantage established in specific benchmarks [1].\n"
        "- Industrial scaling roadmap exceeds 1,000 physical qubits [2].\n"
        "- Novel quantum chips show real-time error suppression [3]."
    )

    with (
        patch.object(agent, "generate_subqueries", return_value=["quantum milestone", "quantum scaling"]),
        patch(
            "src.darius_ai.core.deep_research_agent.get_ai_response",
            return_value=(synthesis_llm_response, "OpenAI"),
        ),
    ):
        brief = agent.research(topic="Computación Cuántica", max_subqueries=2, max_pages=5)

        assert isinstance(brief, ResearchBrief)
        # Deduplication check: 3 unique sources from 4 items
        assert len(brief.sources) == 3
        assert brief.sources[0]["url"] == "https://nature.com/quantum"
        assert brief.sources[1]["url"] == "https://ibm.com/quantum"
        assert brief.sources[2]["url"] == "https://quantumai.google"

        # Citations check
        assert len(brief.citations) == 3
        assert "[1]" in brief.citations[0]
        assert "https://nature.com/quantum" in brief.citations[0]

        # Key findings check
        assert len(brief.key_findings) >= 2

        # Footnotes & Bibliography formatting in markdown_report
        assert "[1]" in brief.markdown_report
        assert "[2]" in brief.markdown_report
        assert "## Bibliography" in brief.markdown_report or "## Fuentes" in brief.markdown_report
        assert "https://nature.com/quantum" in brief.markdown_report


def test_deep_research_agent_with_code_interpreter():
    """Validates optional code_interpreter integration."""
    mock_search = MagicMock()
    mock_search.search.return_value = [
        {"title": "Math Constants", "url": "https://math.org", "snippet": "pi and e"},
    ]
    mock_interpreter = MagicMock()
    mock_interpreter.execute.return_value = "3.14159265"

    agent = DeepResearchAgent(search_engine=mock_search, code_interpreter=mock_interpreter)
    assert agent.code_interpreter is mock_interpreter


def test_deep_research_agent_empty_search_fallback():
    """Validates graceful synthesis when search yields no sources."""
    mock_search = MagicMock()
    mock_search.search.return_value = []

    agent = DeepResearchAgent(search_engine=mock_search)

    with (
        patch.object(agent, "generate_subqueries", return_value=["subquery 1"]),
        patch("src.darius_ai.core.deep_research_agent.get_ai_response", side_effect=Exception("No LLM")),
    ):
        brief = agent.research(topic="Unknown Subject", max_subqueries=1, max_pages=3)
        assert isinstance(brief, ResearchBrief)
        assert len(brief.sources) == 0
        assert len(brief.citations) == 0
        assert "No sources found" in brief.summary or "Unknown Subject" in brief.summary


def test_web_search_engine_implementation():
    """Validates WebSearchEngine delegating to _search_duckduckgo and handling exceptions."""
    engine = WebSearchEngine()

    with patch("src.darius_ai.core.deep_research._search_duckduckgo", return_value=[{"title": "T", "url": "U"}]):
        res = engine.search("test", max_results=2)
        assert len(res) == 1
        assert res[0]["title"] == "T"

    with patch("src.darius_ai.core.deep_research._search_duckduckgo", side_effect=RuntimeError("Network down")):
        res = engine.search("test", max_results=2)
        assert res == []


def test_deep_research_agent_search_error_resilience():
    """Validates that search engine errors during individual queries do not crash research()."""
    mock_search = MagicMock()
    mock_search.search.side_effect = [
        RuntimeError("Query 1 failed"),
        [{"title": "Resilient Source", "url": "https://ok.com", "snippet": "Working fine"}],
    ]
    agent = DeepResearchAgent(search_engine=mock_search)

    with (
        patch.object(agent, "generate_subqueries", return_value=["q1", "q2"]),
        patch(
            "src.darius_ai.core.deep_research_agent.get_ai_response",
            return_value=("## Summary\nGood.\n## Key Findings\n- Point [1]", "mock"),
        ),
    ):
        brief = agent.research("Resilience Topic", max_subqueries=2)
        assert len(brief.sources) == 1
        assert brief.sources[0]["title"] == "Resilient Source"


def test_deep_research_agent_synthesis_llm_failure_heuristic_fallback():
    """Validates heuristic synthesis when LLM fails to synthesize."""
    mock_search = MagicMock()
    mock_search.search.return_value = [
        {"title": "Primary Doc", "url": "https://doc.org", "snippet": "Essential details on topic"},
    ]
    agent = DeepResearchAgent(search_engine=mock_search)

    with (
        patch.object(agent, "generate_subqueries", return_value=["query"]),
        patch("src.darius_ai.core.deep_research_agent.get_ai_response", side_effect=RuntimeError("LLM quota")),
    ):
        brief = agent.research("Heuristic Topic", max_subqueries=1)
        assert "Primary Doc" in brief.summary
        assert len(brief.key_findings) >= 1
        assert "[1]" in brief.citations[0]
        assert "## Bibliography" in brief.markdown_report


def test_deep_research_agent_empty_snippet_findings():
    """Validates fallback findings when sources lack snippet text."""
    agent = DeepResearchAgent()
    sources = [{"title": "No Snippet Doc", "url": "https://nosnippet.org", "snippet": ""}]
    summary, findings = agent._extract_summary_and_findings("", sources, "No Snippet Topic")
    assert "No Snippet Topic" in summary
    assert len(findings) == 1
    assert "verified sources" in findings[0]

