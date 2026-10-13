"""Unit tests for NewsSentinel (multi-provider news aggregation, Anti-SSRF, TTL cache, Butler vocal briefing)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

# Ensure src is in sys.path
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    from src.darius_ai.core.news_sentinel import NewsHeadline, NewsSentinel
except ImportError:
    from darius_ai.core.news_sentinel import NewsHeadline, NewsSentinel  # type: ignore[import-not-found,no-redef]


# Sample valid RSS XML for tests
SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News - Technology</title>
    <link>https://www.bbc.co.uk/news/technology</link>
    <description>Technology news from BBC</description>
    <item>
      <title>Quantum Breakthrough in Computing</title>
      <link>https://www.bbc.co.uk/news/technology-101</link>
      <pubDate>Mon, 13 Oct 2026 12:00:00 GMT</pubDate>
      <description>Scientists achieve milestone in quantum coherence.</description>
    </item>
    <item>
      <title>Autonomous AI Butler Upgraded</title>
      <link>https://www.bbc.co.uk/news/technology-102</link>
      <pubDate>Mon, 13 Oct 2026 13:00:00 GMT</pubDate>
      <description>Advanced tactical voice systems reach parity with human assistants.</description>
    </item>
  </channel>
</rss>
"""

# Sample RSS XML with SSRF links
SAMPLE_SSRF_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Internal Feed</title>
    <link>https://news.example.com</link>
    <item>
      <title>Legitimate Story</title>
      <link>https://news.example.com/story1</link>
      <pubDate>Mon, 13 Oct 2026 12:00:00 GMT</pubDate>
      <description>Clean headline.</description>
    </item>
    <item>
      <title>Malicious Internal Metadata Story</title>
      <link>http://169.254.169.254/latest/meta-data/</link>
      <pubDate>Mon, 13 Oct 2026 12:05:00 GMT</pubDate>
      <description>Exploit attempt.</description>
    </item>
    <item>
      <title>Localhost Port Scan Story</title>
      <link>http://localhost:8080/admin</link>
      <pubDate>Mon, 13 Oct 2026 12:10:00 GMT</pubDate>
      <description>Localhost exploit.</description>
    </item>
  </channel>
</rss>
"""


# ============================================================================
# NewsHeadline Dataclass Tests
# ============================================================================


def test_news_headline_dataclass_fields():
    """Verify NewsHeadline fields and default summary value."""
    headline = NewsHeadline(
        title="Breakthrough in Fusion Energy",
        source="Nature",
        url="https://www.nature.com/articles/fusion-2026",
        category="science",
        published_at="2026-10-13T10:00:00Z",
        summary="Net positive energy recorded.",
    )
    assert headline.title == "Breakthrough in Fusion Energy"
    assert headline.source == "Nature"
    assert headline.url == "https://www.nature.com/articles/fusion-2026"
    assert headline.category == "science"
    assert headline.published_at == "2026-10-13T10:00:00Z"
    assert headline.summary == "Net positive energy recorded."


def test_news_headline_default_summary():
    """Verify NewsHeadline summary defaults to empty string."""
    headline = NewsHeadline(
        title="Tech Update",
        source="TechCrunch",
        url="https://techcrunch.com/sample",
        category="technology",
        published_at="2026-10-13",
    )
    assert headline.summary == ""


# ============================================================================
# NewsSentinel Initialization and Category Mapping
# ============================================================================


def test_news_sentinel_init_defaults():
    """Verify default parameters for NewsSentinel."""
    sentinel = NewsSentinel()
    assert sentinel.ttl_seconds == 900.0  # 15 minutes
    assert sentinel.timeout_seconds > 0


def test_category_normalization():
    """Verify Spanish and alias mappings for standard categories."""
    sentinel = NewsSentinel()
    assert sentinel.normalize_category("tecnologia") == "technology"
    assert sentinel.normalize_category("ciencia") == "science"
    assert sentinel.normalize_category("negocios") == "business"
    assert sentinel.normalize_category("finanzas") == "business"
    assert sentinel.normalize_category("mundo") == "world"
    assert sentinel.normalize_category("internacional") == "world"
    assert sentinel.normalize_category("TECHNOLOGY") == "technology"
    assert sentinel.normalize_category("unknown_xyz") == "general"


# ============================================================================
# RSS Provider & Anti-SSRF Tests
# ============================================================================


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_rss_fetch_success(mock_get):
    """Verify successful parsing of public RSS syndication feed."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_RSS_XML
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel()
    headlines = sentinel.get_top_headlines(category="technology", limit=5)

    assert len(headlines) == 2
    assert headlines[0].title == "Quantum Breakthrough in Computing"
    assert "bbc" in headlines[0].source.lower()
    assert headlines[0].url == "https://www.bbc.co.uk/news/technology-101"
    assert headlines[0].category == "technology"
    assert "quantum" in headlines[0].summary.lower()


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_rss_fetch_with_anti_ssrf_filtering(mock_get):
    """Verify headlines with private/metadata URLs are dropped by AntiSSRFValidator."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_SSRF_RSS_XML
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel()
    headlines = sentinel.get_top_headlines(category="technology", limit=5)

    # Should only retain the legitimate external story, dropping 169.254 and localhost
    assert len(headlines) == 1
    assert headlines[0].title == "Clean Headline" or headlines[0].title == "Legitimate Story"
    assert "169.254" not in headlines[0].url
    assert "localhost" not in headlines[0].url


def test_anti_ssrf_validator_blocks_internal_custom_feed():
    """Verify NewsSentinel blocks attempts to fetch RSS from private or loopback feeds."""
    sentinel = NewsSentinel()
    unsafe_feed = "http://127.0.0.1:8000/feed.xml"
    safe, msg = sentinel.is_safe_url(unsafe_feed)
    assert safe is False
    assert "loopback" in msg.lower() or "blocked" in msg.lower() or "private" in msg.lower()


# ============================================================================
# Multi-Provider Fallbacks: DuckDuckGo and NewsAPI
# ============================================================================


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_rss_failure_falls_back_to_duckduckgo(mock_get):
    """Verify fallback to DuckDuckGo when RSS syndication endpoints fail."""
    # First call (RSS) fails with Connection Error
    # Second call (DDG Instant Answer or HTML) succeeds
    ddg_payload = {
        "Heading": "Tech Innovations 2026",
        "AbstractText": "Artificial Intelligence continues rapid evolution.",
        "AbstractURL": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "RelatedTopics": [
            {
                "FirstURL": "https://example.com/ai-robotics",
                "Text": "Robotics Leap - Robots perform complex manual tasks.",
            }
        ],
    }

    def side_effect(url, **kwargs):
        if "rss" in url or "xml" in url or "feeds" in url:
            raise httpx.ConnectError("Feed connection failed")
        if "duckduckgo" in url:
            mock_ddg = MagicMock()
            mock_ddg.status_code = 200
            mock_ddg.json.return_value = ddg_payload
            return mock_ddg
        raise httpx.RequestError("Unknown endpoint")

    mock_get.side_effect = side_effect

    sentinel = NewsSentinel()
    headlines = sentinel.get_top_headlines(category="technology", limit=5)

    assert len(headlines) >= 1
    assert any("ai" in h.title.lower() or "robotics" in h.title.lower() for h in headlines)


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_newsapi_support_when_key_provided(mock_get):
    """Verify NewsAPI integration when api_key is configured."""
    newsapi_payload = {
        "status": "ok",
        "totalResults": 1,
        "articles": [
            {
                "source": {"id": "wired", "name": "Wired"},
                "author": "Tech Editor",
                "title": "Silicon Advancements in Optical Computing",
                "description": "Photonic chips provide 10x throughput boost.",
                "url": "https://www.wired.com/story/optical-computing",
                "publishedAt": "2026-10-13T09:00:00Z",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = newsapi_payload
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel(news_api_key="mock_secret_key")
    headlines = sentinel.get_top_headlines(category="technology", limit=5)

    assert len(headlines) == 1
    assert headlines[0].title == "Silicon Advancements in Optical Computing"
    assert headlines[0].source == "Wired"
    assert headlines[0].category == "technology"


# ============================================================================
# Cache with TTL (15 min) Tests
# ============================================================================


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_cache_hit_prevents_duplicate_network_calls(mock_get):
    """Verify second call within TTL uses cached data and does not issue HTTP requests."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_RSS_XML
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel(ttl_seconds=900.0)
    # First call - fetches and populates cache
    first_headlines = sentinel.get_top_headlines(category="technology", limit=2)
    assert len(first_headlines) == 2
    initial_call_count = mock_get.call_count

    # Second call - should hit cache
    second_headlines = sentinel.get_top_headlines(category="technology", limit=2)
    assert len(second_headlines) == 2
    assert mock_get.call_count == initial_call_count


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_cache_ttl_expiration_triggers_fresh_fetch(mock_get):
    """Verify expired cache triggers fresh network fetch."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_RSS_XML
    mock_get.return_value = mock_resp

    # Sentinel with short TTL (0.05 seconds)
    sentinel = NewsSentinel(ttl_seconds=0.05)
    sentinel.get_top_headlines(category="technology", limit=2)
    assert mock_get.call_count >= 1

    time.sleep(0.06)

    # Next call should re-fetch
    sentinel.get_top_headlines(category="technology", limit=2)
    assert mock_get.call_count >= 2


def test_clear_cache():
    """Verify manual cache clearance resets stored entries."""
    sentinel = NewsSentinel()
    sentinel._cache["technology"] = (time.time(), [MagicMock()])
    assert len(sentinel._cache) == 1
    sentinel.clear_cache()
    assert len(sentinel._cache) == 0


# ============================================================================
# Resilience and Offline Handling
# ============================================================================


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_network_down_resilience_zero_exceptions(mock_get):
    """Verify total network failure returns empty list without raising exceptions."""
    mock_get.side_effect = httpx.ConnectError("No internet connection")

    sentinel = NewsSentinel()
    # Must not raise any unhandled exceptions
    headlines = sentinel.get_top_headlines(category="science", limit=5)
    assert isinstance(headlines, list)
    assert len(headlines) == 0


# ============================================================================
# J.A.R.V.I.S. Butler Vocal Briefing Formatting
# ============================================================================


def test_format_vocal_briefing_with_multiple_headlines():
    """Verify Butler cadence vocal briefing with multiple headlines."""
    sentinel = NewsSentinel()
    headlines = [
        NewsHeadline(
            title="Nuevo chip cuántico supera límites térmicos",
            source="MIT Tech Review",
            url="https://technologyreview.com/chip-2026",
            category="technology",
            published_at="2026-10-13",
        ),
        NewsHeadline(
            title="Red neuronal autónoma resuelve ecuación de Navier-Stokes",
            source="Nature",
            url="https://nature.com/navier-stokes",
            category="technology",
            published_at="2026-10-13",
        ),
    ]

    briefing = sentinel.format_vocal_briefing(headlines, category="technology")

    assert "señor" in briefing.lower()
    assert "titulares de tecnolog" in briefing.lower()
    assert "MIT Tech Review" in briefing
    assert "Nuevo chip cuántico" in briefing
    assert "Navier-Stokes" in briefing


def test_format_vocal_briefing_empty_headlines():
    """Verify graceful Butler message when offline or no headlines available."""
    sentinel = NewsSentinel()
    briefing = sentinel.format_vocal_briefing([], category="science")

    assert "señor" in briefing.lower()
    lower_b = briefing.lower()
    assert "no dispongo" in lower_b or "no he podido" in lower_b or "sin novedades" in lower_b


def test_format_vocal_briefing_single_headline():
    """Verify briefing formatting when only a single headline is returned."""
    sentinel = NewsSentinel()
    headlines = [
        NewsHeadline(
            title="Misión a Europa confirma océanos subglaciares habitables",
            source="NASA JPL",
            url="https://jpl.nasa.gov/europa-2026",
            category="science",
            published_at="2026-10-13",
        )
    ]
    briefing = sentinel.format_vocal_briefing(headlines, category="science")

    assert "señor" in briefing.lower()
    assert "NASA JPL" in briefing
    assert "Europa confirma" in briefing


# ============================================================================
# Additional Edge Case & Branch Coverage Tests
# ============================================================================


SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Nature Biotechnology News</title>
  <entry>
    <title>CRISPR Precision Editing Advance</title>
    <link href="https://nature.com/articles/crispr-2026"/>
    <published>2026-10-13T08:00:00Z</published>
    <summary>Novel base editor minimizes off-target indels.</summary>
  </entry>
</feed>
"""


SAMPLE_DDG_HTML = """<!DOCTYPE html>
<html>
<body>
  <div class="result">
    <a class="result__a" href="/html/?uddg=https%3A%2F%2Fwired.com%2Fstory%2Fai-future">AI Future in Robotics</a>
    <div class="result__snippet">Robotics intelligence reaches landmark efficiency.</div>
  </div>
</body>
</html>
"""


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_atom_feed_parsing(mock_get):
    """Verify Atom XML syndication feed is parsed when RSS <item> tags are absent."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_ATOM_XML
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel()
    headlines = sentinel.get_top_headlines(category="science", limit=5)

    assert len(headlines) == 1
    assert "crispr" in headlines[0].title.lower()
    assert "editor" in headlines[0].summary.lower()


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_rss_malformed_xml_handled_gracefully(mock_get):
    """Verify XML parsing errors are caught and logged without raising exceptions."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "This is not valid XML <broken><tag>"
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel()
    headlines = sentinel._parse_rss_xml(mock_resp.text, category="technology", limit=5)
    assert headlines == []


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_duckduckgo_html_scraper_fallback(mock_get):
    """Verify DuckDuckGo HTML scraping operates when Instant Answer is empty."""
    def side_effect(url, **kwargs):
        if "api.duckduckgo.com" in url:
            mock_api = MagicMock()
            mock_api.status_code = 200
            mock_api.json.return_value = {}  # Empty instant answer
            return mock_api
        if "html.duckduckgo.com" in url:
            mock_html = MagicMock()
            mock_html.status_code = 200
            mock_html.text = SAMPLE_DDG_HTML
            return mock_html
        raise httpx.RequestError("Unknown endpoint")

    mock_get.side_effect = side_effect

    sentinel = NewsSentinel()
    headlines = sentinel._fetch_from_duckduckgo(category="technology", limit=5)

    assert len(headlines) == 1
    assert headlines[0].title == "AI Future in Robotics"
    assert headlines[0].url == "https://wired.com/story/ai-future"
    assert headlines[0].source == "wired.com"


def test_clean_text_utility_cases():
    """Verify clean_text strips entities, spaces, and handles empty inputs."""
    assert NewsSentinel.clean_text("") == ""
    assert NewsSentinel.clean_text("<p>Hello&nbsp;<b>World</b></p>") == "Hello World"


def test_is_safe_url_empty():
    """Verify is_safe_url handles empty string."""
    safe, msg = NewsSentinel.is_safe_url("")
    assert safe is False
    assert "empty" in msg.lower()


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_newsapi_empty_articles_and_invalid_data(mock_get):
    """Verify NewsAPI returns empty list when payload has no articles."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "articles": []}
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel(news_api_key="valid_key")
    headlines = sentinel._fetch_from_newsapi(category="technology", limit=5)
    assert headlines == []


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_newsapi_http_error_handled(mock_get):
    """Verify NewsAPI non-200 response returns empty list."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel(news_api_key="invalid_key")
    headlines = sentinel._fetch_from_newsapi(category="technology", limit=5)
    assert headlines == []


@patch("src.darius_ai.core.news_sentinel.httpx.get")
def test_duckduckgo_html_http_error_handled(mock_get):
    """Verify DuckDuckGo HTML non-200 response returns empty list."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp

    sentinel = NewsSentinel()
    headlines = sentinel._fetch_from_duckduckgo_html(
        query="test", category="technology", limit=5
    )
    assert headlines == []

