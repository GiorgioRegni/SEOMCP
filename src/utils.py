from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

DATA_DIR = Path("data")
HTML_CACHE = DATA_DIR / "html"
JSON_CACHE = DATA_DIR / "json"

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "is", "are", "on", "with", "as", "by", "from",
    "that", "this", "it", "at", "be", "can", "you", "your", "how", "what", "when", "why", "which", "about",
}


def ensure_dirs() -> None:
    HTML_CACHE.mkdir(parents=True, exist_ok=True)
    JSON_CACHE.mkdir(parents=True, exist_ok=True)


def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    clean = p._replace(fragment="", query="")
    scheme = clean.scheme or "https"
    return urlunparse((scheme, clean.netloc.lower(), clean.path.rstrip("/"), "", "", ""))


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9'-]+", text.lower())


def ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(max(0, len(tokens) - n + 1))]


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_text(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")
