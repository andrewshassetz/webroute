"""Search providers behind one common interface.

Every provider takes a query and returns a list of SearchResult objects,
so the router (and the agent) never has to care which API is underneath.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

USER_AGENT = "webroute-demo/0.1 (https://github.com/)"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str


class ProviderError(Exception):
    """Raised when a provider can't answer (outage, bad key, timeout...)."""


@dataclass
class Provider:
    """Base class. Subclasses implement `_search`."""

    name: str
    # Which kinds of task this provider is good at.
    capabilities: set[str] = field(default_factory=set)
    # Rough numbers the router uses to rank providers.
    cost_per_call: float = 0.0  # USD
    avg_latency_ms: int = 500
    quality: int = 3  # 1-5
    needs_key: str | None = None  # env var name, if any
    simulate_outage: bool = False

    def available(self) -> bool:
        return self.needs_key is None or bool(os.getenv(self.needs_key))

    def search(self, query: str, max_results: int = 3) -> list[SearchResult]:
        if self.simulate_outage:
            raise ProviderError(f"{self.name}: simulated outage (HTTP 503)")
        try:
            return self._search(query, max_results)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: {exc.__class__.__name__}: {exc}") from exc

    def _search(self, query: str, max_results: int) -> list[SearchResult]:
        raise NotImplementedError


class WikipediaProvider(Provider):
    """Free, no key. Great for definitions and background facts."""

    def __init__(self, **kw):
        super().__init__(
            name="wikipedia",
            capabilities={"reference", "general"},
            cost_per_call=0.0,
            avg_latency_ms=350,
            quality=4,
            **kw,
        )

    def _search(self, query, max_results):
        r = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        r.raise_for_status()
        hits = r.json().get("query", {}).get("search", [])
        return [
            SearchResult(
                title=h["title"],
                url="https://en.wikipedia.org/wiki/" + h["title"].replace(" ", "_"),
                snippet=_strip_tags(h.get("snippet", "")),
                provider=self.name,
            )
            for h in hits
        ]


class DuckDuckGoProvider(Provider):
    """Free, no key. DuckDuckGo's Instant Answer API."""

    def __init__(self, **kw):
        super().__init__(
            name="duckduckgo",
            capabilities={"general", "reference"},
            cost_per_call=0.0,
            avg_latency_ms=450,
            quality=2,
            **kw,
        )

    def _search(self, query, max_results):
        r = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        results = []
        if data.get("AbstractText"):
            results.append(
                SearchResult(data.get("Heading", query), data.get("AbstractURL", ""),
                             data["AbstractText"], self.name)
            )
        for topic in data.get("RelatedTopics", []):
            if "Text" in topic and "FirstURL" in topic:
                results.append(SearchResult(topic["Text"][:80], topic["FirstURL"],
                                            topic["Text"], self.name))
            if len(results) >= max_results:
                break
        return results[:max_results]


class TavilyProvider(Provider):
    """Paid, needs TAVILY_API_KEY. Built for agents: fresh web + news."""

    def __init__(self, **kw):
        super().__init__(
            name="tavily",
            capabilities={"general", "news", "research"},
            cost_per_call=0.008,
            avg_latency_ms=900,
            quality=5,
            needs_key="TAVILY_API_KEY",
            **kw,
        )

    def _search(self, query, max_results):
        r = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": os.environ["TAVILY_API_KEY"], "query": query,
                  "max_results": max_results},
            timeout=15,
        )
        r.raise_for_status()
        return [
            SearchResult(h["title"], h["url"], h.get("content", "")[:300], self.name)
            for h in r.json().get("results", [])
        ]


def _strip_tags(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", text)


def default_providers() -> list[Provider]:
    return [WikipediaProvider(), DuckDuckGoProvider(), TavilyProvider()]
