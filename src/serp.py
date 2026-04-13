from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .utils import normalize_url


class SERPProvider(Protocol):
    def search(self, query: str, top_n: int = 8, geo: str | None = None, language: str | None = None) -> list[str]:
        ...


@dataclass
class ManualURLProvider:
    urls: list[str]

    def search(self, query: str, top_n: int = 8, geo: str | None = None, language: str | None = None) -> list[str]:
        del query, geo, language
        deduped: list[str] = []
        seen: set[str] = set()
        for url in self.urls:
            normalized = normalize_url(url)
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(url)
        return deduped[:top_n]


@dataclass
class PlaceholderSearchProvider:
    """v1 placeholder for plug-in providers (SerpAPI, Tavily, Brave, etc.)."""

    def search(self, query: str, top_n: int = 8, geo: str | None = None, language: str | None = None) -> list[str]:
        del query, top_n, geo, language
        return []



def collect_serp_urls(query: str, top_n: int, manual_urls: list[str] | None = None,
                      geo: str | None = None, language: str | None = None) -> list[str]:
    provider: SERPProvider
    if manual_urls:
        provider = ManualURLProvider(manual_urls)
    else:
        provider = PlaceholderSearchProvider()
    return provider.search(query=query, top_n=top_n, geo=geo, language=language)
