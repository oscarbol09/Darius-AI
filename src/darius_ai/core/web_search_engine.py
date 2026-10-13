"""Web Search Engine — Multi-provider DuckDuckGo search with Anti-SSRF validation and LRU caching."""

from __future__ import annotations

import html
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, unquote

import httpx

try:
    from src.darius_ai.core.security_guard import AntiSSRFValidator
except ImportError:
    from darius_ai.core.security_guard import AntiSSRFValidator  # type: ignore[import-not-found,no-redef]

logger = logging.getLogger(__name__)

_HTML_TAG_RE: re.Pattern[str] = re.compile(r"<[^>]+>")
_WHITESPACE_RE: re.Pattern[str] = re.compile(r"\s+")
_UDDG_RE: re.Pattern[str] = re.compile(r"uddg=([^&]+)")


@dataclass
class SearchResult:
    """Encapsulates a single search engine hit."""

    title: str
    url: str
    snippet: str
    source: str


class WebSearchEngine:
    """Robust web search engine featuring multi-provider DuckDuckGo fallback and SSRF protection."""

    def __init__(
        self,
        ttl_seconds: float = 900.0,  # 15 minutes default
        max_cache_size: int = 128,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_cache_size = max_cache_size
        self._timeout_seconds = timeout_seconds
        self._cache: OrderedDict[str, tuple[float, list[SearchResult]]] = OrderedDict()

    @staticmethod
    def clean_snippet(raw_html: str) -> str:
        """Strip HTML tags, decode HTML entities, and normalize whitespace."""
        if not raw_html:
            return ""
        text = _HTML_TAG_RE.sub(" ", raw_html)
        text = html.unescape(text)
        text = text.replace("\xa0", " ")
        return _WHITESPACE_RE.sub(" ", text).strip()

    @staticmethod
    def is_safe_search_url(url: str) -> bool:
        """Validate whether a candidate result URL is safe from SSRF and metadata leaks."""
        if not url:
            return False
        safe, _ = AntiSSRFValidator.is_safe_url(url, allow_dns_lookup=False)
        return safe

    def clear_cache(self) -> None:
        """Purge all cached search queries."""
        self._cache.clear()

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Execute web search across DuckDuckGo providers with Anti-SSRF filtering and caching.

        Args:
            query: The search keywords or phrase.
            max_results: Maximum number of safe results to return.

        Returns:
            List of SearchResult objects conforming to safety guardrails.
        """
        trimmed = query.strip()
        if not trimmed:
            return []

        norm_key = " ".join(trimmed.lower().split())

        # Check in-memory LRU cache
        if norm_key in self._cache:
            timestamp, cached_results = self._cache[norm_key]
            if time.time() - timestamp <= self._ttl_seconds:
                self._cache.move_to_end(norm_key)
                return cached_results[:max_results]
            del self._cache[norm_key]

        results = self._fetch_with_fallback(trimmed, max_results)

        # Enforce max_results and cache if results found
        final_results = results[:max_results]
        if final_results:
            if norm_key in self._cache:
                self._cache.move_to_end(norm_key)
            self._cache[norm_key] = (time.time(), final_results)
            if len(self._cache) > self._max_cache_size:
                self._cache.popitem(last=False)

        return final_results

    def _fetch_with_fallback(self, query: str, max_results: int) -> list[SearchResult]:
        """Attempt Instant Answer API first, falling back to HTML scraping on failure or empty results."""
        # Provider 1: Instant Answer JSON API
        try:
            instant_results = self._search_instant_answer(query, max_results)
            if instant_results:
                return instant_results
        except Exception as exc:  # noqa: BLE001
            logger.debug("DuckDuckGo Instant Answer API failed (%s); falling back to HTML", exc)

        # Provider 2: DuckDuckGo HTML scraping
        try:
            html_results = self._search_html(query, max_results)
            if html_results:
                return html_results
        except Exception as exc:  # noqa: BLE001
            logger.warning("DuckDuckGo HTML scraping failed: %s", exc)

        return []

    def _search_instant_answer(self, query: str, max_results: int) -> list[SearchResult]:
        """Fetch search results from DuckDuckGo Instant Answer API."""
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
        headers = {
            "User-Agent": "Darius-AI/1.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
        }

        response = httpx.get(url, headers=headers, timeout=self._timeout_seconds)
        if response.status_code != 200:
            return []

        payload: dict[str, Any] = response.json()
        results: list[SearchResult] = []

        heading = payload.get("Heading") or ""
        abstract = payload.get("AbstractText") or ""
        abstract_url = payload.get("AbstractURL") or ""

        if abstract_url and (abstract or heading) and self.is_safe_search_url(abstract_url):
            results.append(
                SearchResult(
                    title=self.clean_snippet(heading or abstract[:60]),
                    url=abstract_url,
                    snippet=self.clean_snippet(abstract),
                    source="duckduckgo_instant",
                )
            )

        related = payload.get("RelatedTopics") or []
        for item in related:
            if len(results) >= max_results:
                break
            if not isinstance(item, dict):
                continue

            subtopics = item.get("Topics")
            candidates = subtopics if isinstance(subtopics, list) else [item]

            for cand in candidates:
                if len(results) >= max_results:
                    break
                if not isinstance(cand, dict):
                    continue

                first_url = cand.get("FirstURL") or ""
                text = cand.get("Text") or ""
                if not first_url or not text:
                    continue

                if not self.is_safe_search_url(first_url):
                    continue

                parts = text.split(" - ", 1)
                title = self.clean_snippet(parts[0])
                snippet = self.clean_snippet(parts[1] if len(parts) > 1 else text)

                results.append(
                    SearchResult(
                        title=title,
                        url=first_url,
                        snippet=snippet,
                        source="duckduckgo_instant",
                    )
                )

        return results[:max_results]

    def _search_html(self, query: str, max_results: int) -> list[SearchResult]:
        """Scrape DuckDuckGo HTML search results."""
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept": "text/html,application/xhtml+xml",
        }

        response = httpx.get(url, headers=headers, timeout=self._timeout_seconds)
        if response.status_code != 200:
            return []

        html_text = response.text
        results: list[SearchResult] = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_text, "html.parser")
            result_divs = soup.find_all("div", class_=re.compile(r"\bresult\b"))

            for div in result_divs:
                if len(results) >= max_results:
                    break

                # Extract URL
                link_elem = div.find("a", class_=re.compile(r"result__(url|title)")) or div.find("a", href=True)
                if not link_elem:
                    continue

                raw_href = link_elem.get("href", "")
                if not raw_href or raw_href.startswith("#"):
                    continue

                # Unwrap DuckDuckGo redirect link
                match = _UDDG_RE.search(raw_href)
                final_url = unquote(match.group(1)) if match else raw_href

                if not self.is_safe_search_url(final_url):
                    continue

                title = self.clean_snippet(link_elem.get_text()) or "Untitled"

                # Extract Snippet
                snippet_elem = div.find("a", class_=re.compile(r"result__snippet")) or div.find(
                    class_=re.compile(r"snippet")
                )
                snippet = self.clean_snippet(snippet_elem.get_text()) if snippet_elem else ""

                results.append(
                    SearchResult(
                        title=title,
                        url=final_url,
                        snippet=snippet,
                        source="duckduckgo_html",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("HTML parsing exception: %s", exc)

        return results[:max_results]


__all__ = [
    "SearchResult",
    "WebSearchEngine",
]
