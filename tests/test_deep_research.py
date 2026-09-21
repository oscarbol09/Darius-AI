"""
test_deep_research.py — Pruebas unitarias para el pipeline de investigación profunda
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from deep_research import DeepResearchPipeline, _clean_html_text
from obsidian_brain import ObsidianBrain


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
    with patch("deep_research.get_ai_response", return_value=(mock_llm_response, "Gemini")):
        queries = pipeline.generate_search_queries("fugas de memoria en python", count=3)
        assert len(queries) == 3
        assert "python async memory leak" in queries


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

        with patch.object(pipeline, "generate_search_queries", return_value=["query 1"]), \
             patch("deep_research._search_duckduckgo", return_value=mock_sources), \
             patch("deep_research._fetch_page_content", return_value="Contenido extraído de prueba"), \
             patch("deep_research.get_ai_response", return_value=(mock_report, "OpenAI")), \
             patch("deep_research.brain", test_brain):

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
