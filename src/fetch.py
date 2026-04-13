from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from .models import PageData
from .utils import HTML_CACHE, cache_key, ensure_dirs, normalize_url

JUNK_PATTERNS = [r"\.pdf$", r"/forum", r"/thread", r"reddit\.com", r"quora\.com"]


def is_junk_url(url: str, allow_forums: bool = False) -> bool:
    if allow_forums:
        return False
    lowered = url.lower()
    return any(re.search(pattern, lowered) for pattern in JUNK_PATTERNS)


def fetch_html(url: str, timeout: int = 20) -> str:
    ensure_dirs()
    normalized = normalize_url(url)
    key = cache_key(normalized)
    cache_path = HTML_CACHE / f"{key}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="ignore")
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "seo-writer-skill/0.1"})
    response.raise_for_status()
    html = response.text
    cache_path.write_text(html, encoding="utf-8")
    return html


def extract_basic_metadata(url: str, html: str) -> PageData:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""

    meta = soup.find("meta", attrs={"name": "description"})
    meta_description = meta.get("content", "").strip() if meta else ""

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical = canonical_tag.get("href", "").strip() if canonical_tag else ""

    headings = {
        "h1": [h.get_text(" ", strip=True) for h in soup.find_all("h1")][:20],
        "h2": [h.get_text(" ", strip=True) for h in soup.find_all("h2")][:60],
        "h3": [h.get_text(" ", strip=True) for h in soup.find_all("h3")][:120],
    }

    parsed_host = requests.utils.urlparse(url).netloc
    internal = 0
    external = 0
    for a in soup.find_all("a", href=True):
        host = requests.utils.urlparse(a["href"]).netloc
        if not host or host == parsed_host:
            internal += 1
        else:
            external += 1

    return PageData(
        url=url,
        normalized_url=normalize_url(url),
        title=title,
        meta_description=meta_description,
        canonical=canonical,
        headings=headings,
        internal_links=internal,
        external_links=external,
    )
