"""News Sentinel — Multi-provider RSS, DuckDuckGo & NewsAPI news aggregation with Anti-SSRF and TTL caching."""

from __future__ import annotations

import html
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, unquote, urlsplit

try:
    from defusedxml import ElementTree
except ImportError:
    from xml.etree import ElementTree  # noqa: S405

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
class NewsHeadline:
    """Represents an individual news article headline and its provenance."""

    title: str
    source: str
    url: str
    category: str
    published_at: str
    summary: str = ""


class NewsSentinel:
    """Multi-provider news sentinel with Anti-SSRF validation, TTL caching, and Butler vocal formatting."""

    CATEGORY_ALIASES: dict[str, str] = {
        "tech": "technology",
        "tecnologia": "technology",
        "tecnología": "technology",
        "technology": "technology",
        "science": "science",
        "ciencia": "science",
        "ciencias": "science",
        "business": "business",
        "negocios": "business",
        "finanzas": "business",
        "economia": "business",
        "economía": "business",
        "world": "world",
        "mundo": "world",
        "internacional": "world",
        "global": "world",
        "general": "general",
    }

    CATEGORY_NAMES_ES: dict[str, str] = {
        "technology": "tecnología",
        "science": "ciencia",
        "business": "negocios y finanzas",
        "world": "actualidad internacional",
        "general": "información general",
    }

    RSS_FEEDS: dict[str, list[str]] = {
        "technology": [
            "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
            "https://www.wired.com/feed/rss",
        ],
        "science": [
            "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
        ],
        "business": [
            "https://feeds.bbci.co.uk/news/business/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        ],
        "world": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        ],
        "general": [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        ],
    }

    def __init__(
        self,
        news_api_key: str | None = None,
        ttl_seconds: float = 900.0,  # 15 minutes
        timeout_seconds: float = 6.0,
    ) -> None:
        self.news_api_key = news_api_key or os.getenv("NEWS_API_KEY")
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, tuple[float, list[NewsHeadline]]] = {}

    @staticmethod
    def is_safe_url(url: str) -> tuple[bool, str]:
        """Validate an external URL against SSRF and cloud metadata endpoints."""
        if not url:
            return False, "URL is empty"
        return AntiSSRFValidator.is_safe_url(url, allow_dns_lookup=False)

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """Strip HTML tags, decode entities, and normalize whitespace."""
        if not raw_text:
            return ""
        text = _HTML_TAG_RE.sub(" ", raw_text)
        text = html.unescape(text)
        text = text.replace("\xa0", " ")
        return _WHITESPACE_RE.sub(" ", text).strip()

    def normalize_category(self, category: str) -> str:
        """Normalize category name from aliases or Spanish terms to canonical English key."""
        clean = category.strip().lower()
        return self.CATEGORY_ALIASES.get(clean, "general")

    def clear_cache(self) -> None:
        """Purge in-memory news cache."""
        self._cache.clear()

    def get_top_headlines(self, category: str = "technology", limit: int = 5) -> list[NewsHeadline]:
        """Fetch top headlines for category across providers with Anti-SSRF filtering and TTL cache.

        Args:
            category: News category (e.g., 'technology', 'ciencia', 'business', 'world').
            limit: Maximum headlines to return (default 5).

        Returns:
            List of verified NewsHeadline instances.
        """
        norm_cat = self.normalize_category(category)
        cache_key = norm_cat

        # Check TTL cache
        if cache_key in self._cache:
            timestamp, cached_headlines = self._cache[cache_key]
            if time.time() - timestamp <= self.ttl_seconds:
                return cached_headlines[:limit]
            del self._cache[cache_key]

        headlines: list[NewsHeadline] = []

        # Provider 1: NewsAPI (if configured)
        if self.news_api_key:
            try:
                headlines = self._fetch_from_newsapi(norm_cat, limit)
            except Exception as exc:  # noqa: BLE001
                logger.debug("NewsAPI provider encountered exception: %s", exc)

        # Provider 2: RSS Public Syndication Feeds (fallback if no NewsAPI or empty)
        if not headlines:
            try:
                headlines = self._fetch_from_rss(norm_cat, limit)
            except Exception as exc:  # noqa: BLE001
                logger.debug("RSS feeds provider encountered exception: %s", exc)

        # Provider 3: DuckDuckGo News Query Fallback
        if not headlines:
            try:
                headlines = self._fetch_from_duckduckgo(norm_cat, limit)
            except Exception as exc:  # noqa: BLE001
                logger.debug("DuckDuckGo news provider encountered exception: %s", exc)

        # Truncate to requested limit and update cache
        final_headlines = headlines[:limit]
        if final_headlines:
            self._cache[cache_key] = (time.time(), final_headlines)

        return final_headlines

    def _fetch_from_newsapi(self, category: str, limit: int) -> list[NewsHeadline]:
        """Fetch articles from NewsAPI REST service."""
        url = f"https://newsapi.org/v2/top-headlines?category={category}&apiKey={self.news_api_key}&pageSize={limit}"
        safe, msg = self.is_safe_url(url)
        if not safe:
            logger.warning("NewsAPI URL blocked by Anti-SSRF: %s", msg)
            return []

        headers = {
            "User-Agent": "Darius-AI/1.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
        }
        resp = httpx.get(url, headers=headers, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            return []

        data: dict[str, Any] = resp.json()
        articles = data.get("articles") or []
        headlines: list[NewsHeadline] = []

        for art in articles:
            if not isinstance(art, dict):
                continue
            art_url = art.get("url") or ""
            safe_url, _ = self.is_safe_url(art_url)
            if not safe_url:
                continue

            title = self.clean_text(art.get("title") or "")
            if not title:
                continue

            source_name = "NewsAPI"
            src_obj = art.get("source")
            if isinstance(src_obj, dict) and src_obj.get("name"):
                source_name = str(src_obj["name"])

            headlines.append(
                NewsHeadline(
                    title=title,
                    source=source_name,
                    url=art_url,
                    category=category,
                    published_at=str(art.get("publishedAt") or ""),
                    summary=self.clean_text(art.get("description") or ""),
                )
            )
            if len(headlines) >= limit:
                break

        return headlines

    def _fetch_from_rss(self, category: str, limit: int) -> list[NewsHeadline]:
        """Fetch headlines from curated public RSS feeds with Anti-SSRF validation."""
        feed_urls = self.RSS_FEEDS.get(category, self.RSS_FEEDS["general"])
        headers = {
            "User-Agent": "Darius-AI/1.0 (Windows NT 10.0; Win64; x64; RSS Reader)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        }

        headlines: list[NewsHeadline] = []

        for feed_url in feed_urls:
            safe, msg = self.is_safe_url(feed_url)
            if not safe:
                logger.warning("RSS Feed URL blocked by Anti-SSRF: %s (%s)", feed_url, msg)
                continue

            try:
                resp = httpx.get(feed_url, headers=headers, timeout=self.timeout_seconds)
                if resp.status_code != 200:
                    continue

                parsed = self._parse_rss_xml(resp.text, category, limit)
                for item in parsed:
                    if len(headlines) >= limit:
                        break
                    headlines.append(item)

                if headlines:
                    return headlines[:limit]
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed fetching feed %s: %s", feed_url, exc)
                continue

        return headlines

    def _parse_rss_xml(self, xml_text: str, category: str, limit: int) -> list[NewsHeadline]:
        """Parse RSS or Atom XML content safely and extract validated headlines."""
        headlines: list[NewsHeadline] = []
        try:
            root = ElementTree.fromstring(xml_text)  # noqa: S314
        except ElementTree.ParseError as err:
            logger.debug("Failed to parse RSS XML: %s", err)
            return []

        channel_title = ""
        channel_node = root.find("channel")
        if channel_node is not None:
            c_title_node = channel_node.find("title")
            if c_title_node is not None and c_title_node.text:
                channel_title = self.clean_text(c_title_node.text)
        else:
            feed_title_node = root.find("{http://www.w3.org/2005/Atom}title")
            if feed_title_node is None:
                feed_title_node = root.find("title")
            if feed_title_node is not None and feed_title_node.text:
                channel_title = self.clean_text(feed_title_node.text)

        default_source = channel_title or "RSS Feed"

        # Search standard RSS <item> tags
        items = root.findall(".//item")
        for item in items:
            if len(headlines) >= limit:
                break

            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pub_el = item.find("pubDate")

            raw_title = title_el.text if title_el is not None and title_el.text else ""
            raw_link = link_el.text if link_el is not None and link_el.text else ""
            raw_desc = desc_el.text if desc_el is not None and desc_el.text else ""
            raw_pub = pub_el.text if pub_el is not None and pub_el.text else ""

            clean_title = self.clean_text(raw_title)
            clean_link = raw_link.strip()
            if not clean_title or not clean_link:
                continue

            # Anti-SSRF validation on headline link
            safe_url, _ = self.is_safe_url(clean_link)
            if not safe_url:
                continue

            headlines.append(
                NewsHeadline(
                    title=clean_title,
                    source=default_source,
                    url=clean_link,
                    category=category,
                    published_at=raw_pub.strip(),
                    summary=self.clean_text(raw_desc),
                )
            )

        # Fallback to Atom <entry> tags if no RSS items found
        if not headlines:
            atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            entries = atom_entries if atom_entries else root.findall(".//entry")
            for entry in entries:
                if len(headlines) >= limit:
                    break
                t_el = entry.find("{http://www.w3.org/2005/Atom}title")
                if t_el is None:
                    t_el = entry.find("title")
                l_el = entry.find("{http://www.w3.org/2005/Atom}link")
                if l_el is None:
                    l_el = entry.find("link")
                s_el = entry.find("{http://www.w3.org/2005/Atom}summary")
                if s_el is None:
                    s_el = entry.find("summary")
                p_el = entry.find("{http://www.w3.org/2005/Atom}published")
                if p_el is None:
                    p_el = entry.find("published")

                clean_title = self.clean_text(t_el.text) if t_el is not None and t_el.text else ""
                clean_link = (l_el.attrib.get("href", "") if l_el is not None else "").strip()
                if not clean_title or not clean_link:
                    continue

                safe_url, _ = self.is_safe_url(clean_link)
                if not safe_url:
                    continue

                headlines.append(
                    NewsHeadline(
                        title=clean_title,
                        source=default_source,
                        url=clean_link,
                        category=category,
                        published_at=p_el.text.strip() if p_el is not None and p_el.text else "",
                        summary=self.clean_text(s_el.text) if s_el is not None and s_el.text else "",
                    )
                )

        return headlines

    def _fetch_from_duckduckgo(self, category: str, limit: int) -> list[NewsHeadline]:
        """Query DuckDuckGo Instant Answer or HTML fallback for news topics."""
        query = f"{category} latest news"
        url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
        safe, msg = self.is_safe_url(url)
        if not safe:
            logger.warning("DuckDuckGo URL blocked by Anti-SSRF: %s", msg)
            return []

        headers = {
            "User-Agent": "Darius-AI/1.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
        }

        headlines: list[NewsHeadline] = []

        try:
            resp = httpx.get(url, headers=headers, timeout=self.timeout_seconds)
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                heading = data.get("Heading") or ""
                abstract = data.get("AbstractText") or ""
                abstract_url = data.get("AbstractURL") or ""

                if abstract_url and (heading or abstract):
                    safe_url, _ = self.is_safe_url(abstract_url)
                    if safe_url:
                        headlines.append(
                            NewsHeadline(
                                title=self.clean_text(heading or abstract[:80]),
                                source="DuckDuckGo News",
                                url=abstract_url,
                                category=category,
                                published_at="",
                                summary=self.clean_text(abstract),
                            )
                        )

                related = data.get("RelatedTopics") or []
                for item in related:
                    if len(headlines) >= limit:
                        break
                    if not isinstance(item, dict):
                        continue
                    first_url = item.get("FirstURL") or ""
                    text = item.get("Text") or ""
                    if not first_url or not text:
                        continue
                    safe_url, _ = self.is_safe_url(first_url)
                    if not safe_url:
                        continue

                    parts = text.split(" - ", 1)
                    title = self.clean_text(parts[0])
                    summary = self.clean_text(parts[1] if len(parts) > 1 else text)

                    headlines.append(
                        NewsHeadline(
                            title=title,
                            source="DuckDuckGo News",
                            url=first_url,
                            category=category,
                            published_at="",
                            summary=summary,
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.debug("DuckDuckGo Instant Answer failed: %s", exc)

        # Fallback to DuckDuckGo HTML scraping if empty
        if not headlines:
            try:
                headlines = self._fetch_from_duckduckgo_html(query, category, limit)
            except Exception as exc:  # noqa: BLE001
                logger.debug("DuckDuckGo HTML fallback failed: %s", exc)

        return headlines

    def _fetch_from_duckduckgo_html(self, query: str, category: str, limit: int) -> list[NewsHeadline]:
        """Scrape DuckDuckGo HTML search results for news headlines."""
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        safe, msg = self.is_safe_url(url)
        if not safe:
            return []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = httpx.get(url, headers=headers, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            return []

        html_text = resp.text
        headlines: list[NewsHeadline] = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_text, "html.parser")
            result_divs = soup.find_all("div", class_=re.compile(r"\bresult\b"))
            for div in result_divs:
                if len(headlines) >= limit:
                    break
                title_elem = div.find("a", class_=re.compile(r"result__snippet|result__url|result__a"))
                if not title_elem:
                    continue

                raw_href = title_elem.get("href", "")
                final_url = ""
                uddg_match = _UDDG_RE.search(raw_href)
                if uddg_match:
                    final_url = unquote(uddg_match.group(1))
                elif raw_href.startswith("http"):
                    final_url = raw_href

                if not final_url:
                    continue

                safe_url, _ = self.is_safe_url(final_url)
                if not safe_url:
                    continue

                title = self.clean_text(title_elem.get_text())
                snippet_elem = div.find(class_=re.compile(r"result__snippet"))
                snippet = self.clean_text(snippet_elem.get_text()) if snippet_elem else ""

                if title:
                    domain = urlsplit(final_url).hostname or "DuckDuckGo"
                    headlines.append(
                        NewsHeadline(
                            title=title,
                            source=domain,
                            url=final_url,
                            category=category,
                            published_at="",
                            summary=snippet,
                        )
                    )
        except ImportError:
            logger.debug("bs4 not available for DuckDuckGo HTML parsing")

        return headlines

    def format_vocal_briefing(self, headlines: list[NewsHeadline], category: str = "technology") -> str:
        """Format headlines in authentic J.A.R.V.I.S. butler cadence for Text-to-Speech vocalization.

        Args:
            headlines: List of NewsHeadline items.
            category: Target category for contextual phrasing.

        Returns:
            Vocal script string formatted for British Butler TTS.
        """
        norm_cat = self.normalize_category(category)
        cat_es = self.CATEGORY_NAMES_ES.get(norm_cat, "actualidad general")

        if not headlines:
            return (
                f"Señor, en este momento no dispongo de nuevos titulares para la categoría de {cat_es}. "
                "Los servicios de noticias no registran actualizaciones o la conexión externa está inaccesible."
            )

        if len(headlines) == 1:
            h = headlines[0]
            return (
                f"Señor, el principal titular de {cat_es} es: '{h.title}', publicado por {h.source}. "
                "No se registran más novedades críticas por ahora en este frente, señor."
            )

        ordinal_prefixes = [
            "En primer lugar",
            "Seguidamente",
            "Asimismo",
            "En otra nota relevante",
            "Por último",
        ]

        lines: list[str] = [f"Señor, los principales titulares de {cat_es} son:"]

        for idx, h in enumerate(headlines):
            prefix = ordinal_prefixes[idx] if idx < len(ordinal_prefixes) else "Adicionalmente"
            lines.append(f"{prefix}: '{h.title}', según {h.source}.")

        lines.append("Eso concluye el reporte informativo por el momento, señor.")
        return " ".join(lines)
