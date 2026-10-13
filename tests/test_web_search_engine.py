"""Unit tests for WebSearchEngine (multi-provider DuckDuckGo search, Anti-SSRF, LRU caching)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src is on sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import darius_ai.core.web_search_engine as _wse
    from darius_ai.core.web_search_engine import SearchResult, WebSearchEngine
except ImportError:
    import src.darius_ai.core.web_search_engine as _wse
    from src.darius_ai.core.web_search_engine import SearchResult, WebSearchEngine


# ============================================================================
# SearchResult Dataclass Tests
# ============================================================================


def test_search_result_dataclass_fields():
    """Verify SearchResult fields and representation."""
    result = SearchResult(
        title="Darius AI Architecture",
        url="https://github.com/darius-ai/core",
        snippet="Autonomous system agent framework.",
        source="duckduckgo_html",
    )
    assert result.title == "Darius AI Architecture"
    assert result.url == "https://github.com/darius-ai/core"
    assert result.snippet == "Autonomous system agent framework."
    assert result.source == "duckduckgo_html"


# ============================================================================
# WebSearchEngine Search & Fallback Tests
# ============================================================================


def test_search_empty_query():
    """Verify empty or whitespace-only queries immediately return empty results without network calls."""
    engine = WebSearchEngine()
    assert engine.search("") == []
    assert engine.search("   \t  ") == []


@patch.object(_wse.httpx, "get")
def test_search_duckduckgo_instant_answer_success(mock_get):
    """Verify instant answer API provides structured search results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Heading": "Python (programming language)",
        "AbstractText": "Python is a high-level, general-purpose programming language.",
        "AbstractURL": "https://en.wikipedia.org/wiki/Python_(programming_language)",
        "RelatedTopics": [
            {
                "Text": "Python Software Foundation - Non-profit organization",
                "FirstURL": "https://www.python.org/psf/",
            }
        ],
    }
    mock_get.return_value = mock_response

    engine = WebSearchEngine()
    results = engine.search("python programming", max_results=3)

    assert len(results) >= 1
    assert results[0].title == "Python (programming language)"
    assert "Python is a high-level" in results[0].snippet
    assert results[0].url == "https://en.wikipedia.org/wiki/Python_(programming_language)"
    assert results[0].source == "duckduckgo_instant"


@patch.object(_wse.httpx, "get")
def test_search_fallback_to_html_scraping_when_instant_empty(mock_get):
    """Verify fallback from empty instant answer to HTML scraping provider."""
    # First call: Instant answer returns empty abstract
    instant_response = MagicMock()
    instant_response.status_code = 200
    instant_response.json.return_value = {
        "Heading": "",
        "AbstractText": "",
        "AbstractURL": "",
        "RelatedTopics": [],
    }

    # Second call: DuckDuckGo HTML scraping returns search results page
    html_content = """
    <html>
        <body>
            <div class="result results_links">
                <a class="result__url" href="https://fastapi.tiangolo.com/">FastAPI Framework</a>
                <a class="result__snippet" href="#">FastAPI framework, high performance, easy to learn.</a>
            </div>
            <div class="result results_links">
                <a class="result__url" href="https://github.com/tiangolo/fastapi">GitHub - tiangolo/fastapi</a>
                <a class="result__snippet" href="#">FastAPI source code repository.</a>
            </div>
        </body>
    </html>
    """
    html_response = MagicMock()
    html_response.status_code = 200
    html_response.text = html_content

    mock_get.side_effect = [instant_response, html_response]

    engine = WebSearchEngine()
    results = engine.search("fastapi", max_results=2)

    assert len(results) == 2
    assert results[0].title == "FastAPI Framework"
    assert results[0].url == "https://fastapi.tiangolo.com/"
    assert "high performance" in results[0].snippet
    assert results[0].source == "duckduckgo_html"


# ============================================================================
# Anti-SSRF Integration Tests
# ============================================================================


@patch.object(_wse.httpx, "get")
def test_search_filters_out_ssrf_malicious_urls(mock_get):
    """Verify URLs pointing to private IPs, localhost, or cloud metadata are dropped."""
    instant_response = MagicMock()
    instant_response.status_code = 200
    instant_response.json.return_value = {
        "Heading": "Internal Admin",
        "AbstractText": "Internal cluster manager.",
        "AbstractURL": "http://169.254.169.254/latest/meta-data/",
        "RelatedTopics": [
            {
                "Text": "Loopback Admin - http://127.0.0.1:8080/",
                "FirstURL": "http://127.0.0.1:8080/admin",
            },
            {
                "Text": "Safe Official Documentation",
                "FirstURL": "https://docs.python.org/3/",
            },
            {
                "Text": "Private Subnet - http://192.168.1.1/",
                "FirstURL": "http://192.168.1.1/dashboard",
            },
        ],
    }
    mock_get.return_value = instant_response

    engine = WebSearchEngine()
    results = engine.search("cluster admin", max_results=5)

    # Only public safe URLs must survive
    assert len(results) == 1
    assert results[0].url == "https://docs.python.org/3/"
    assert "Safe Official Documentation" in results[0].title or "Safe Official Documentation" in results[0].snippet


# ============================================================================
# HTML Snippet Sanitization Tests
# ============================================================================


def test_clean_html_snippet_extraction():
    """Verify HTML stripping, entity decoding, and whitespace normalization."""
    raw_html = "  <b>Darius&nbsp;AI</b> &amp; <i>Autonomous</i> &quot;Agents&#39; system&quot;  <br/>  \n\n  "
    cleaned = WebSearchEngine.clean_snippet(raw_html)
    assert cleaned == 'Darius AI & Autonomous "Agents\' system"'


# ============================================================================
# LRU Cache & TTL Tests
# ============================================================================


@patch.object(_wse.httpx, "get")
def test_lru_cache_prevents_duplicate_network_calls(mock_get):
    """Verify queries within TTL are served from cache without extra HTTP requests."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Heading": "Test Query",
        "AbstractText": "Snippet content.",
        "AbstractURL": "https://example.com/test",
        "RelatedTopics": [],
    }
    mock_get.return_value = mock_response

    engine = WebSearchEngine(ttl_seconds=900)  # 15 minutes TTL

    # 1st call: Misses cache, makes HTTP call
    res1 = engine.search("test query", max_results=3)
    assert len(res1) == 1
    assert mock_get.call_count == 1

    # 2nd call: Hits cache, no extra HTTP call
    res2 = engine.search("test query", max_results=3)
    assert len(res2) == 1
    assert mock_get.call_count == 1

    # 3rd call with normalized case/whitespace: Hits cache
    res3 = engine.search("  TEST QUERY  ", max_results=3)
    assert len(res3) == 1
    assert mock_get.call_count == 1


@patch.object(_wse.httpx, "get")
def test_cache_ttl_expiration(mock_get):
    """Verify expired cache entries trigger new HTTP fetches."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Heading": "TTL Query",
        "AbstractText": "Snippet content.",
        "AbstractURL": "https://example.com/ttl",
        "RelatedTopics": [],
    }
    mock_get.return_value = mock_response

    # Short TTL for test: 0.1s
    engine = WebSearchEngine(ttl_seconds=0.1)
    res1 = engine.search("ttl test")
    assert len(res1) == 1
    assert mock_get.call_count == 1

    time.sleep(0.15)  # Wait for cache expiration

    res2 = engine.search("ttl test")
    assert len(res2) == 1
    assert mock_get.call_count == 2


def test_clear_cache():
    """Verify clear_cache completely resets the cache entries."""
    engine = WebSearchEngine()
    engine._cache["cached_query"] = (time.time(), [SearchResult("T", "https://x.com", "S", "src")])
    assert len(engine._cache) == 1

    engine.clear_cache()
    assert len(engine._cache) == 0


@patch.object(_wse.httpx, "get")
def test_max_results_respected(mock_get):
    """Verify max_results limits the number of returned SearchResults."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Heading": "Result 1",
        "AbstractText": "Snippet 1",
        "AbstractURL": "https://example.com/1",
        "RelatedTopics": [
            {"Text": "Topic 2", "FirstURL": "https://example.com/2"},
            {"Text": "Topic 3", "FirstURL": "https://example.com/3"},
            {"Text": "Topic 4", "FirstURL": "https://example.com/4"},
        ],
    }
    mock_get.return_value = mock_response

    engine = WebSearchEngine()
    results = engine.search("multi results", max_results=2)
    assert len(results) == 2


@patch.object(_wse.httpx, "get")
def test_search_engine_handles_network_failure_gracefully(mock_get):
    """Verify network exceptions in all providers return empty list without crashing."""
    import httpx

    mock_get.side_effect = httpx.ConnectError("Network unreachable")

    engine = WebSearchEngine()
    results = engine.search("failed query")
    assert results == []


@patch.object(_wse.httpx, "get")
def test_search_instant_answer_nested_subtopics(mock_get):
    """Verify nested 'Topics' lists in RelatedTopics are parsed correctly."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Heading": "",
        "AbstractText": "",
        "AbstractURL": "",
        "RelatedTopics": [
            {
                "Name": "Frameworks",
                "Topics": [
                    {"Text": "Django - Web framework for perfectionists", "FirstURL": "https://djangoproject.com"},
                    {"Text": "Flask - Lightweight WSGI web application framework", "FirstURL": "https://flask.palletsprojects.com"},
                ],
            }
        ],
    }
    mock_get.return_value = mock_response

    engine = WebSearchEngine()
    results = engine.search("python web frameworks", max_results=5)
    assert len(results) == 2
    assert results[0].title == "Django"
    assert results[1].title == "Flask"


@patch.object(_wse.httpx, "get")
def test_search_http_non_200_fallback(mock_get):
    """Verify 404/500 HTTP responses in providers are handled gracefully."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    engine = WebSearchEngine()
    results = engine.search("error query")
    assert results == []


@patch.object(_wse.httpx, "get")
def test_lru_cache_capacity_eviction(mock_get):
    """Verify least recently used entries are evicted when max_cache_size is exceeded."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Heading": "Result",
        "AbstractText": "Snippet",
        "AbstractURL": "https://example.com/res",
        "RelatedTopics": [],
    }
    mock_get.return_value = mock_response

    engine = WebSearchEngine(max_cache_size=2)
    engine.search("q1")
    engine.search("q2")
    assert "q1" in engine._cache
    assert "q2" in engine._cache

    # Query q3 triggers eviction of q1
    engine.search("q3")
    assert "q1" not in engine._cache
    assert "q2" in engine._cache
    assert "q3" in engine._cache


def test_is_safe_search_url_edge_cases():
    """Verify edge cases for URL safety validation."""
    assert WebSearchEngine.is_safe_search_url("") is False
    assert WebSearchEngine.is_safe_search_url("http://127.0.0.1") is False
    assert WebSearchEngine.is_safe_search_url("https://python.org") is True


def test_clean_snippet_empty():
    """Verify clean_snippet handles empty/none strings."""
    assert WebSearchEngine.clean_snippet("") == ""

