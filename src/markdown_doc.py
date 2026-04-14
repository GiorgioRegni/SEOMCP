from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

import tomli
import tomli_w
import yaml

from .models import ContentBrief, MarkdownDocument

YAML_DELIMITER = "---"
TOML_DELIMITER = "+++"
SEO_FIELDS = {"title", "description", "tags", "draft"}
NOISY_TAGS = {
    "helpful-thanks",
    "thanks-love",
    "the-rest",
    "table-of-contents",
    "subscribe",
    "footer",
}


def parse_markdown_document(markdown: str) -> MarkdownDocument:
    if markdown.startswith(f"{YAML_DELIMITER}\n"):
        return _parse_delimited_frontmatter(markdown, YAML_DELIMITER, "yaml")
    if markdown.startswith(f"{TOML_DELIMITER}\n"):
        return _parse_delimited_frontmatter(markdown, TOML_DELIMITER, "toml")
    return MarkdownDocument(frontmatter_format=None, frontmatter={}, raw_frontmatter="", body=markdown)


def _parse_delimited_frontmatter(markdown: str, delimiter: str, fmt: str) -> MarkdownDocument:
    closing = f"\n{delimiter}\n"
    end = markdown.find(closing, len(delimiter) + 1)
    if end == -1:
        return MarkdownDocument(frontmatter_format=None, frontmatter={}, raw_frontmatter="", body=markdown)

    raw = markdown[len(delimiter) + 1:end]
    body = markdown[end + len(closing):]
    if body.startswith("\n"):
        body = body[1:]
    frontmatter = _loads_frontmatter(raw, fmt)
    return MarkdownDocument(frontmatter_format=fmt, frontmatter=frontmatter, raw_frontmatter=raw, body=body)


def _loads_frontmatter(raw: str, fmt: str) -> dict[str, Any]:
    if fmt == "yaml":
        data = yaml.safe_load(raw) or {}
    elif fmt == "toml":
        data = tomli.loads(raw) if raw.strip() else {}
    else:
        data = {}

    if not isinstance(data, dict):
        return {}
    return data


def render_markdown_document(doc: MarkdownDocument) -> str:
    if not doc.frontmatter_format:
        return doc.body

    raw = doc.raw_frontmatter
    if not raw:
        raw = dump_frontmatter(doc.frontmatter, doc.frontmatter_format).rstrip("\n")

    delimiter = YAML_DELIMITER if doc.frontmatter_format == "yaml" else TOML_DELIMITER
    raw_block = raw if raw.endswith("\n") else f"{raw}\n"
    body = doc.body.lstrip("\n")
    return f"{delimiter}\n{raw_block}{delimiter}\n\n{body}"


def dump_frontmatter(frontmatter: dict[str, Any], fmt: str) -> str:
    if fmt == "yaml":
        return yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    if fmt == "toml":
        return tomli_w.dumps(frontmatter)
    raise ValueError(f"Unsupported front matter format: {fmt}")


def build_frontmatter_suggestions(brief: ContentBrief, doc: MarkdownDocument | None = None) -> dict[str, Any]:
    title = brief.candidate_titles[0] if brief.candidate_titles else brief.primary_query.title()
    existing_draft = doc.frontmatter.get("draft") if doc else None
    return {
        "title": title,
        "description": _description_for_brief(brief),
        "tags": _tags_for_brief(brief),
        "draft": False if existing_draft is False else True,
    }


def update_hugo_seo_fields(doc: MarkdownDocument, brief: ContentBrief, *, overwrite: bool) -> MarkdownDocument:
    fmt = doc.frontmatter_format or "yaml"
    updated = MarkdownDocument(
        frontmatter_format=fmt,
        frontmatter=deepcopy(doc.frontmatter),
        raw_frontmatter=doc.raw_frontmatter,
        body=doc.body,
    )
    suggestions = build_frontmatter_suggestions(brief, updated)

    changed = False
    for key in SEO_FIELDS:
        if overwrite or not updated.frontmatter.get(key):
            updated.frontmatter[key] = suggestions[key]
            changed = True

    if changed:
        updated.raw_frontmatter = dump_frontmatter(updated.frontmatter, fmt).rstrip("\n")
    return updated


def title_from_document(doc: MarkdownDocument) -> str | None:
    title = doc.frontmatter.get("title")
    return str(title) if title else None


def h1_from_body(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return None


def build_hugo_document(brief: ContentBrief, body: str, fmt: str) -> str:
    if fmt == "none":
        return body
    if fmt not in {"yaml", "toml"}:
        raise ValueError("--frontmatter-format must be one of: yaml, toml, none")

    frontmatter = build_frontmatter_suggestions(brief)
    raw = dump_frontmatter(frontmatter, fmt).rstrip("\n")
    doc = MarkdownDocument(frontmatter_format=fmt, frontmatter=frontmatter, raw_frontmatter=raw, body=body)
    return render_markdown_document(doc)


def _description_for_brief(brief: ContentBrief) -> str:
    title = brief.candidate_titles[0] if brief.candidate_titles else brief.primary_query.title()
    concepts = [
        c for c in brief.recommended_concepts_entities[:4]
        if c.lower() not in title.lower()
    ]
    if concepts:
        return f"A practical guide to {brief.primary_query}, including {', '.join(concepts[:3])}, and answers to common questions."
    return (
        f"A practical guide to {brief.primary_query}, with clear explanations, useful context, and answers to common questions."
    )


def _tags_for_brief(brief: ContentBrief) -> list[str]:
    candidates = [brief.primary_query, *brief.recommended_concepts_entities[:12]]
    tags: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        tag = _normalize_tag(candidate)
        if tag and tag not in seen:
            tags.append(tag)
            seen.add(tag)
        if len(tags) >= 8:
            break
    return tags


def _normalize_tag(value: str) -> str:
    tag = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if tag in NOISY_TAGS:
        return ""
    return tag[:48]
