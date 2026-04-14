from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests

from .browser_session import DEFAULT_CDP_PORT, cdp_endpoint, ensure_chrome
from .models import SERPDiscoveryResult, SERPResult, to_dict
from .utils import JSON_CACHE, dump_json, ensure_dirs, normalize_url, slugify


DEFAULT_GOOGLE_PROFILE_DIR = Path("data/chrome/google-serp")
DEFAULT_GOOGLE_START_URL = "about:blank"
SUPPORTED_PROVIDER_NAMES = ("brave", "serper", "serpapi", "google-chrome", "none")


class SERPProvider(Protocol):
    name: str

    def search(
        self,
        query: str,
        top_n: int = 8,
        geo: str | None = None,
        language: str | None = None,
    ) -> SERPDiscoveryResult:
        ...


def _dedupe_results(results: list[SERPResult], top_n: int) -> list[SERPResult]:
    deduped: list[SERPResult] = []
    seen: set[str] = set()
    for result in results:
        normalized = normalize_url(result.url)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(SERPResult(
            position=len(deduped) + 1,
            url=result.url,
            title=result.title,
            snippet=result.snippet,
            source=result.source,
        ))
        if len(deduped) >= top_n:
            break
    return deduped


def _result_payload(
    *,
    query: str,
    provider: str,
    results: list[SERPResult],
    warnings: list[str] | None = None,
) -> SERPDiscoveryResult:
    urls = [result.url for result in results]
    return SERPDiscoveryResult(
        query=query,
        provider=provider,
        count=len(urls),
        urls=urls,
        results=results,
        warnings=warnings or [],
    )


@dataclass
class ManualURLProvider:
    urls: list[str]
    name: str = "manual"

    def search(
        self,
        query: str,
        top_n: int = 8,
        geo: str | None = None,
        language: str | None = None,
    ) -> SERPDiscoveryResult:
        del geo, language
        results = [
            SERPResult(position=index + 1, url=url, source=self.name)
            for index, url in enumerate(self.urls)
        ]
        results = _dedupe_results(results, top_n)
        return _result_payload(query=query, provider=self.name, results=results)


@dataclass
class EmptySearchProvider:
    name: str = "none"
    warning: str = (
        "No SERP provider configured. Pass URLs manually or set SEO_WRITER_SERP_PROVIDER "
        "plus the matching API key environment variable."
    )

    def search(
        self,
        query: str,
        top_n: int = 8,
        geo: str | None = None,
        language: str | None = None,
    ) -> SERPDiscoveryResult:
        del top_n, geo, language
        return _result_payload(query=query, provider=self.name, results=[], warnings=[self.warning])


@dataclass
class BraveSearchProvider:
    api_key: str
    name: str = "brave"

    def search(
        self,
        query: str,
        top_n: int = 8,
        geo: str | None = None,
        language: str | None = None,
    ) -> SERPDiscoveryResult:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params = {
            "q": query,
            "count": min(max(top_n, 1), 20),
        }
        if language:
            params["search_lang"] = language.split("_")[0].split("-")[0].lower()
        if geo:
            params["country"] = geo.upper()

        response = requests.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("web", {}).get("results", [])
        results = [
            SERPResult(
                position=index + 1,
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("description", ""),
                source=self.name,
            )
            for index, item in enumerate(raw_results)
            if item.get("url")
        ]
        return _result_payload(query=query, provider=self.name, results=_dedupe_results(results, top_n))


@dataclass
class SerperSearchProvider:
    api_key: str
    name: str = "serper"

    def search(
        self,
        query: str,
        top_n: int = 8,
        geo: str | None = None,
        language: str | None = None,
    ) -> SERPDiscoveryResult:
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key,
        }
        body: dict[str, Any] = {
            "q": query,
            "num": min(max(top_n, 1), 100),
        }
        if geo:
            body["gl"] = geo.lower()
        if language:
            body["hl"] = language.split("_")[0].split("-")[0].lower()

        response = requests.post("https://google.serper.dev/search", headers=headers, json=body, timeout=20)
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("organic", [])
        results = [
            SERPResult(
                position=item.get("position") or index + 1,
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                source=self.name,
            )
            for index, item in enumerate(raw_results)
            if item.get("link")
        ]
        return _result_payload(query=query, provider=self.name, results=_dedupe_results(results, top_n))


@dataclass
class SerpApiSearchProvider:
    api_key: str
    name: str = "serpapi"

    def search(
        self,
        query: str,
        top_n: int = 8,
        geo: str | None = None,
        language: str | None = None,
    ) -> SERPDiscoveryResult:
        params = {
            "engine": "google",
            "q": query,
            "num": min(max(top_n, 1), 100),
            "api_key": self.api_key,
        }
        if geo:
            params["gl"] = geo.lower()
        if language:
            params["hl"] = language.split("_")[0].split("-")[0].lower()

        response = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("organic_results", [])
        results = [
            SERPResult(
                position=item.get("position") or index + 1,
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                source=self.name,
            )
            for index, item in enumerate(raw_results)
            if item.get("link")
        ]
        warnings = []
        if payload.get("error"):
            warnings.append(str(payload["error"]))
        return _result_payload(query=query, provider=self.name, results=_dedupe_results(results, top_n), warnings=warnings)


@dataclass
class GoogleChromeSearchProvider:
    profile_dir: str | Path = DEFAULT_GOOGLE_PROFILE_DIR
    port: int | None = DEFAULT_CDP_PORT
    launch_if_missing: bool = True
    headless: bool = True
    name: str = "google-chrome"

    def search(
        self,
        query: str,
        top_n: int = 8,
        geo: str | None = None,
        language: str | None = None,
    ) -> SERPDiscoveryResult:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Install Playwright with `python3 -m pip install -r requirements.txt`.") from exc

        google_url = _google_search_url(query, top_n=top_n, geo=geo, language=language)
        browser_info = ensure_chrome(
            profile_dir=self.profile_dir,
            port=self.port,
            start_url=DEFAULT_GOOGLE_START_URL,
            launch_if_missing=self.launch_if_missing,
            headless=self.headless,
        )
        active_port = int(browser_info["port"])

        warnings: list[str] = []
        rows: list[dict[str, str]] = []
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_endpoint(active_port))
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            page.goto(google_url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                warnings.append("Timed out waiting for Google network idle; scraping current DOM.")
            page.wait_for_timeout(1000)
            title = page.title().lower()
            if "captcha" in title or "sorry" in page.url.lower():
                warnings.append("Google showed a CAPTCHA or unusual-traffic page. Try an API provider or a different Chrome profile.")
            rows = page.evaluate(
                """
                (limit) => {
                  const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                  const ignoredHosts = new Set([
                    'google.com',
                    'www.google.com',
                    'accounts.google.com',
                    'support.google.com',
                    'policies.google.com',
                    'maps.google.com',
                    'news.google.com',
                    'translate.google.com',
                    'webcache.googleusercontent.com'
                  ]);
                  const normalizeHref = (href) => {
                    try {
                      const u = new URL(href, location.href);
                      if (u.pathname === '/url' && u.searchParams.get('q')) {
                        return u.searchParams.get('q');
                      }
                      return u.href;
                    } catch {
                      return '';
                    }
                  };
                  const isCandidate = (href) => {
                    try {
                      const u = new URL(href);
                      const host = u.hostname.replace(/^www\\./, '');
                      return /^https?:$/.test(u.protocol) && !ignoredHosts.has(host) && !host.endsWith('.google.com');
                    } catch {
                      return false;
                    }
                  };
                  const seen = new Set();
                  const out = [];
                  const push = (href, title, snippet) => {
                    const normalized = normalizeHref(href);
                    if (!normalized || !isCandidate(normalized) || seen.has(normalized)) return;
                    seen.add(normalized);
                    out.push({url: normalized, title: clean(title), snippet: clean(snippet)});
                  };

                  for (const block of Array.from(document.querySelectorAll('div.g, div[data-sokoban-container], div.MjjYud'))) {
                    const link = block.querySelector('a[href]');
                    const heading = block.querySelector('h3');
                    if (!link || !heading) continue;
                    const text = clean(block.innerText);
                    const title = clean(heading.innerText);
                    const snippet = text.replace(title, '').trim();
                    push(link.href, title, snippet);
                    if (out.length >= limit) return out;
                  }

                  for (const link of Array.from(document.querySelectorAll('a[href]'))) {
                    const heading = link.querySelector('h3') || link.closest('div')?.querySelector('h3');
                    if (!heading) continue;
                    const block = link.closest('div.g, div[data-sokoban-container], div.MjjYud, div') || link;
                    push(link.href, clean(heading.innerText), clean(block.innerText));
                    if (out.length >= limit) return out;
                  }
                  return out;
                }
                """,
                top_n,
            )
            page.close()

        results = [
            SERPResult(
                position=index + 1,
                url=row.get("url", ""),
                title=row.get("title", ""),
                snippet=row.get("snippet", ""),
                source=self.name,
            )
            for index, row in enumerate(rows)
            if row.get("url")
        ]
        if not results:
            warnings.append("No Google organic links were extracted from the rendered page.")
        return _result_payload(query=query, provider=self.name, results=_dedupe_results(results, top_n), warnings=warnings)


def _google_search_url(query: str, *, top_n: int, geo: str | None, language: str | None) -> str:
    params = {
        "q": query,
        "num": str(min(max(top_n, 1), 100)),
        "pws": "0",
    }
    if language:
        params["hl"] = language.split("_")[0].split("-")[0].lower()
    if geo:
        params["gl"] = geo.lower()
    return "https://www.google.com/search?" + "&".join(f"{key}={quote_plus(value)}" for key, value in params.items())


def _env(name: str, fallback: str | None = None) -> str | None:
    return os.environ.get(name) or (os.environ.get(fallback) if fallback else None)


def configured_provider_name(provider_name: str | None = None) -> str:
    explicit = (provider_name or os.environ.get("SEO_WRITER_SERP_PROVIDER") or "").strip().lower().replace("_", "-")
    if explicit:
        return explicit
    if _env("BRAVE_SEARCH_API_KEY", "SEO_WRITER_BRAVE_API_KEY"):
        return "brave"
    if _env("SERPER_API_KEY", "SEO_WRITER_SERPER_API_KEY"):
        return "serper"
    if _env("SERPAPI_API_KEY", "SEO_WRITER_SERPAPI_API_KEY"):
        return "serpapi"
    return "none"


def provider_from_env(provider_name: str | None = None) -> SERPProvider:
    name = configured_provider_name(provider_name)
    if name in {"", "none", "manual", "placeholder"}:
        return EmptySearchProvider()
    if name == "brave":
        api_key = _env("BRAVE_SEARCH_API_KEY", "SEO_WRITER_BRAVE_API_KEY")
        if not api_key:
            return EmptySearchProvider(name="brave", warning="Brave provider selected but BRAVE_SEARCH_API_KEY is not set.")
        return BraveSearchProvider(api_key=api_key)
    if name == "serper":
        api_key = _env("SERPER_API_KEY", "SEO_WRITER_SERPER_API_KEY")
        if not api_key:
            return EmptySearchProvider(name="serper", warning="Serper provider selected but SERPER_API_KEY is not set.")
        return SerperSearchProvider(api_key=api_key)
    if name == "serpapi":
        api_key = _env("SERPAPI_API_KEY", "SEO_WRITER_SERPAPI_API_KEY")
        if not api_key:
            return EmptySearchProvider(name="serpapi", warning="SerpAPI provider selected but SERPAPI_API_KEY is not set.")
        return SerpApiSearchProvider(api_key=api_key)
    if name in {"google-chrome", "chrome-google", "google"}:
        profile_dir = os.environ.get("SEO_WRITER_GOOGLE_CHROME_PROFILE", str(DEFAULT_GOOGLE_PROFILE_DIR))
        port = os.environ.get("SEO_WRITER_GOOGLE_CHROME_PORT")
        headless = os.environ.get("SEO_WRITER_GOOGLE_CHROME_HEADLESS", "1").lower() not in {"0", "false", "no"}
        return GoogleChromeSearchProvider(
            profile_dir=profile_dir,
            port=int(port) if port else DEFAULT_CDP_PORT,
            headless=headless,
        )
    return EmptySearchProvider(name=name, warning=f"Unsupported SERP provider {name!r}. Supported: {', '.join(SUPPORTED_PROVIDER_NAMES)}.")


def discover_serp_urls(
    query: str,
    top_n: int,
    provider_name: str | None = None,
    geo: str | None = None,
    language: str | None = None,
    manual_urls: list[str] | None = None,
    save: bool = True,
) -> SERPDiscoveryResult:
    provider: SERPProvider
    if manual_urls:
        provider = ManualURLProvider(manual_urls)
    else:
        provider = provider_from_env(provider_name)
    result = provider.search(query=query, top_n=top_n, geo=geo, language=language)
    if save:
        ensure_dirs()
        out = JSON_CACHE / f"serp-{slugify(query)}.json"
        dump_json(out, to_dict(result))
    return result


def collect_serp_urls(
    query: str,
    top_n: int,
    manual_urls: list[str] | None = None,
    geo: str | None = None,
    language: str | None = None,
    provider_name: str | None = None,
) -> list[str]:
    return discover_serp_urls(
        query=query,
        top_n=top_n,
        provider_name=provider_name,
        geo=geo,
        language=language,
        manual_urls=manual_urls,
    ).urls


def extract_google_target_url(href: str) -> str:
    """Best-effort helper for tests and future non-rendered Google parsing."""
    parsed = urlparse(href)
    if parsed.path == "/url":
        target = parse_qs(parsed.query).get("q", [""])[0]
        return unquote(target)
    return href
