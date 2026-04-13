from __future__ import annotations

import re

from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:
    trafilatura = None

from .models import PageData
from .utils import tokenize


JUNK_SELECTOR_PATTERN = re.compile(r"(cookie|consent|banner|nav|menu|footer|sidebar|subscribe|promo)", re.I)


def _extract_with_trafilatura(html: str) -> tuple[str, str]:
    if trafilatura is None:
        return "", ""
    text = trafilatura.extract(html, include_comments=False, include_tables=False, output_format="txt") or ""
    md = trafilatura.extract(html, include_comments=False, include_tables=False, output_format="markdown") or ""
    return text, md


def _extract_with_beautifulsoup(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "form", "iframe"]):
        tag.decompose()

    for tag in soup.find_all(True):
        class_text = " ".join(tag.get("class", []))
        id_text = tag.get("id", "")
        if JUNK_SELECTOR_PATTERN.search(f"{class_text} {id_text}"):
            tag.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    text = container.get_text("\n", strip=True)

    markdown_lines: list[str] = []
    for node in container.find_all(["h1", "h2", "h3", "p", "li"]):
        line = node.get_text(" ", strip=True)
        if not line:
            continue
        if node.name == "h1":
            markdown_lines.append(f"# {line}")
        elif node.name == "h2":
            markdown_lines.append(f"## {line}")
        elif node.name == "h3":
            markdown_lines.append(f"### {line}")
        elif node.name == "li":
            markdown_lines.append(f"- {line}")
        else:
            markdown_lines.append(line)

    return text, "\n\n".join(markdown_lines)


def extract_main_content(page: PageData, html: str) -> PageData:
    try:
        text, md = _extract_with_trafilatura(html)
    except ImportError:
        text, md = "", ""

    if not text.strip():
        text, md = _extract_with_beautifulsoup(html)
        page.source_quality_flags.append("fallback_extraction")

    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    page.text = cleaned
    page.markdownish = md.strip()
    page.word_count = len(tokenize(cleaned))

    if page.word_count < 150:
        page.source_quality_flags.append("thin_content")
    if not page.headings["h2"]:
        page.source_quality_flags.append("weak_structure")

    return page
