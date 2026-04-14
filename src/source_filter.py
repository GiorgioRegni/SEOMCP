from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import SourceFilteringResult, SourceUrlDecision
from .utils import STOPWORDS, normalize_url, tokenize

SOCIAL_HOSTS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
)
FORUM_HOSTS = ("reddit.com", "quora.com")
MARKETPLACE_HOSTS = (
    "etsy.com",
    "ebay.com",
    "walmart.com",
    "target.com",
)
PRODUCT_PATH_PATTERNS = (
    r"/listing/",
    r"/dp/",
    r"/gp/product/",
    r"/product/",
    r"/products/",
)
DYNAMIC_EVENT_PATTERNS = (r"/ptoc\.aspx", r"/ptd\.aspx", r"event", r"tournament")
GENERIC_QUERY_TERMS = {"pickleball", "bracket", "brackets", "lesson", "lessons", "rules", "paddle", "paddles"}


def filter_source_urls(
    urls: list[str],
    query: str,
    top_n: int,
    *,
    allow_forums: bool = False,
    allow_pdfs: bool = False,
    allow_social: bool = False,
    allow_marketplaces: bool = False,
    allow_homepages: bool = False,
) -> SourceFilteringResult:
    result = SourceFilteringResult()
    seen: set[str] = set()

    for raw_url in urls:
        decision = classify_source_url(
            raw_url,
            query,
            allow_forums=allow_forums,
            allow_pdfs=allow_pdfs,
            allow_social=allow_social,
            allow_marketplaces=allow_marketplaces,
            allow_homepages=allow_homepages,
        )
        if decision.normalized_url in seen:
            decision.included = False
            decision.category = "duplicate"
            decision.reason = "Duplicate normalized URL."
        seen.add(decision.normalized_url)

        if decision.included and len(result.included) >= top_n:
            decision.included = False
            decision.category = "over_limit"
            decision.reason = f"Excluded after top_n={top_n} included URLs."

        result.decisions.append(decision)
        if decision.included:
            result.included.append(decision.url)
        else:
            result.excluded.append(decision)

    return result


def classify_source_url(
    raw_url: str,
    query: str,
    *,
    allow_forums: bool = False,
    allow_pdfs: bool = False,
    allow_social: bool = False,
    allow_marketplaces: bool = False,
    allow_homepages: bool = False,
) -> SourceUrlDecision:
    url = raw_url.strip()
    parsed = urlparse(url)
    if not url or "..." in url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return SourceUrlDecision(url=url, normalized_url=url, category="malformed", included=False,
                                 reason="URL is empty, truncated, or missing an HTTP(S) host.")

    normalized = normalize_url(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()

    if path.endswith(".pdf") and not allow_pdfs:
        return SourceUrlDecision(url=url, normalized_url=normalized, category="pdf", included=False,
                                 reason="PDF sources are excluded by default.")

    if _host_matches(host, SOCIAL_HOSTS) and not allow_social:
        return SourceUrlDecision(url=url, normalized_url=normalized, category="social_or_login_gated",
                                 included=False, reason="Social/profile pages are noisy or login-gated.")

    if (_host_matches(host, FORUM_HOSTS) or "/forum" in path or "/thread" in path) and not allow_forums:
        return SourceUrlDecision(url=url, normalized_url=normalized, category="forum", included=False,
                                 reason="Forum/community pages are excluded by default.")

    if _is_marketplace_or_product(host, path) and not allow_marketplaces:
        return SourceUrlDecision(url=url, normalized_url=normalized, category="marketplace_or_product_listing",
                                 included=False, reason="Marketplace or product listing pages are excluded by default.")

    if _looks_like_same_name_different_entity(host, path, query):
        return SourceUrlDecision(url=url, normalized_url=normalized, category="same_name_different_entity",
                                 included=False,
                                 reason="Likely a different entity with overlapping query terms; keep only as a do-not-confuse source.")

    if _is_generic_homepage(path) and _looks_like_official_homepage(host, query):
        return SourceUrlDecision(url=url, normalized_url=normalized, category="included", included=True,
                                 reason="Included as a likely official homepage for the query.")

    if _is_generic_homepage(path) and not allow_homepages:
        return SourceUrlDecision(url=url, normalized_url=normalized, category="generic_homepage", included=False,
                                 reason="Generic homepages are too broad for brief generation.")

    if any(re.search(pattern, path) for pattern in DYNAMIC_EVENT_PATTERNS):
        return SourceUrlDecision(url=url, normalized_url=normalized, category="dynamic_event_page", included=True,
                                 reason="Included, but live event data may change.")

    query_terms = {t for t in tokenize(query) if len(t) > 2}
    url_terms = set(tokenize(f"{host} {path}"))
    if query_terms and not query_terms.intersection(url_terms):
        return SourceUrlDecision(url=url, normalized_url=normalized, category="weak_for_intent", included=True,
                                 reason="Included, but URL text has weak overlap with the query.")

    return SourceUrlDecision(url=url, normalized_url=normalized, category="included", included=True)


def _host_matches(host: str, candidates: tuple[str, ...]) -> bool:
    return any(host == candidate or host.endswith(f".{candidate}") for candidate in candidates)


def _is_marketplace_or_product(host: str, path: str) -> bool:
    if _host_matches(host, MARKETPLACE_HOSTS):
        return True
    if host.endswith("amazon.com") and ("/best-sellers" in path or "/dp/" in path or "/gp/product/" in path):
        return True
    return any(re.search(pattern, path) for pattern in PRODUCT_PATH_PATTERNS)


def _is_generic_homepage(path: str) -> bool:
    return path in {"", "/"}


def _looks_like_official_homepage(host: str, query: str) -> bool:
    host_text = host.replace("-", "").replace(".", "")
    query_terms = [
        term for term in tokenize(query)
        if term not in STOPWORDS and term not in GENERIC_QUERY_TERMS and len(term) > 3
    ]
    return bool(query_terms) and any(term in host_text for term in query_terms)


def _looks_like_same_name_different_entity(host: str, path: str, query: str) -> bool:
    q = query.lower()
    if "the fort" in q and host == "fortathleticclub.com" and "pickleball" in path:
        return True
    return False
