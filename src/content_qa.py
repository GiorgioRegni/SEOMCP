from __future__ import annotations

import re
from typing import Any

from .markdown_doc import parse_markdown_document
from .utils import tokenize

SCAFFOLD_PATTERNS = (
    r"use this section",
    r"explain why this topic matters",
    r"add practical guidance",
    r"concepts to include naturally",
    r"phrase guidance",
    r"draft note:",
    r"answer this clearly",
)

INTERNAL_META_PATTERNS = (
    r"failed to fetch",
    r"source_filtering",
    r"score_breakdown",
    r"optimization notes?",
    r"cli command",
    r"report-[a-z0-9-]+\.json",
    r"data/json/",
    r"weak-source warning",
    r"filtered urls?",
)

DEFAULT_NOISY_TERMS = {
    "helpful thanks",
    "thanks love",
    "the rest",
    "table of contents",
    "subscribe to get the latest pickleball news",
}


def qa_markdown_content(query: str, markdown: str, noisy_terms: list[str] | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    try:
        doc = parse_markdown_document(markdown)
    except Exception as exc:  # noqa: BLE001
        return {
            "passed": False,
            "query": query,
            "issues": [{"severity": "error", "code": "frontmatter_parse_error", "message": str(exc)}],
            "warnings": [],
            "checks": {"frontmatter_parseable": False},
        }

    body_lower = doc.body.lower()
    for pattern in SCAFFOLD_PATTERNS:
        if re.search(pattern, body_lower):
            issues.append({
                "severity": "error",
                "code": "scaffold_text",
                "message": f"Final content still contains scaffold phrase matching: {pattern}",
            })

    for pattern in INTERNAL_META_PATTERNS:
        if re.search(pattern, body_lower):
            issues.append({
                "severity": "error",
                "code": "internal_metadata",
                "message": f"Final content contains internal workflow metadata matching: {pattern}",
            })

    terms_to_check = sorted(DEFAULT_NOISY_TERMS.union(t.lower() for t in noisy_terms or []))
    found_noisy = [term for term in terms_to_check if term and term in body_lower]
    for term in found_noisy[:12]:
        warnings.append({
            "severity": "warning",
            "code": "noisy_term",
            "message": f"Noisy extracted term appears in content: {term}",
        })

    if doc.frontmatter_format:
        if doc.frontmatter.get("draft") is True:
            warnings.append({
                "severity": "warning",
                "code": "draft_true",
                "message": "Hugo front matter has draft: true.",
            })
        for field in ("title", "description"):
            if not doc.frontmatter.get(field):
                warnings.append({
                    "severity": "warning",
                    "code": f"missing_{field}",
                    "message": f"Hugo front matter is missing {field}.",
                })
    else:
        warnings.append({
            "severity": "warning",
            "code": "missing_frontmatter",
            "message": "No Hugo front matter detected.",
        })

    tokens = tokenize(doc.body)
    repeated = _repeated_terms(tokens)
    for term in repeated[:8]:
        warnings.append({
            "severity": "warning",
            "code": "repetition",
            "message": f"Potentially repetitive term: {term}",
        })

    checks = {
        "frontmatter_parseable": True,
        "frontmatter_format": doc.frontmatter_format,
        "word_count": len(tokens),
        "scaffold_issue_count": sum(1 for issue in issues if issue["code"] == "scaffold_text"),
        "internal_metadata_issue_count": sum(1 for issue in issues if issue["code"] == "internal_metadata"),
        "noisy_term_warning_count": len(found_noisy),
        "repeated_terms": repeated[:12],
    }

    return {
        "passed": not issues,
        "query": query,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
    }


def _repeated_terms(tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    ignore = {"pickleball", "with", "that", "this", "from", "your", "have", "will", "what", "where"}
    threshold = max(14, int(len(tokens) * 0.045))
    counts: dict[str, int] = {}
    for token in tokens:
        if len(token) <= 3 or token in ignore:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [term for term, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count > threshold]
