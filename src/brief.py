from __future__ import annotations

import json
from pathlib import Path

from .models import CompetitorAnalysis, ContentBrief


def infer_intent(query: str) -> str:
    q = query.lower()
    if any(x in q for x in ["how", "what", "guide", "rules"]):
        return "Informational"
    if any(x in q for x in ["best", "top", "review", "vs"]):
        return "Commercial investigation"
    if any(x in q for x in ["buy", "price", "coupon"]):
        return "Transactional"
    return "Mixed"


def build_brief(query: str, comp: CompetitorAnalysis) -> ContentBrief:
    low, high = comp.word_count_range
    if low == 0 and high == 0:
        low, high = 700, 1200

    outline = [f"## {h.title()}" for h in comp.common_headings[:8]]
    questions = [f"What should readers know about {s}?" for s in comp.recommended_subtopics[:8]]
    titles = [
        f"{query.title()}: Complete Guide",
        f"{query.title()} Explained Step by Step",
        f"Practical {query.title()} Guide for Beginners",
    ]

    return ContentBrief(
        primary_query=query,
        likely_intent=infer_intent(query),
        target_word_count_range=(max(400, low), max(low + 200, high)),
        candidate_titles=titles,
        suggested_outline=outline,
        recommended_concepts_entities=(comp.recommended_entities[:12] + comp.recommended_phrases[:12]),
        questions_to_answer=questions,
        phrases_to_use_naturally=comp.recommended_phrases[:20],
        warnings=comp.warnings,
        source_urls=comp.source_urls,
    )


def load_saved_brief(path: str | Path) -> tuple[CompetitorAnalysis, ContentBrief]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    brief_payload = payload.get("content_brief", payload)
    comp_payload = payload.get("competitor_analysis")

    brief = content_brief_from_dict(brief_payload)
    if comp_payload:
        comp = competitor_analysis_from_dict(comp_payload)
    else:
        comp = CompetitorAnalysis(
            query=brief.primary_query,
            page_count=0,
            median_word_count=0,
            word_count_range=(0, 0),
            common_headings=[],
            recommended_phrases=brief.phrases_to_use_naturally,
            recommended_entities=brief.recommended_concepts_entities,
            recommended_subtopics=[q.removeprefix("What should readers know about ").rstrip("?") for q in brief.questions_to_answer],
            weak_source_warning=True,
            warnings=brief.warnings,
            source_urls=brief.source_urls,
        )
    if not comp.common_headings and brief.suggested_outline:
        comp.common_headings = [_outline_heading_text(h) for h in brief.suggested_outline]
    return comp, brief


def competitor_analysis_from_dict(payload: dict) -> CompetitorAnalysis:
    return CompetitorAnalysis(
        query=payload.get("query", ""),
        page_count=payload.get("page_count", 0),
        median_word_count=payload.get("median_word_count", 0),
        word_count_range=tuple(payload.get("word_count_range", (0, 0))),
        common_headings=payload.get("common_headings", []),
        recommended_phrases=payload.get("recommended_phrases", []),
        recommended_entities=payload.get("recommended_entities", []),
        recommended_subtopics=payload.get("recommended_subtopics", []),
        weak_source_warning=payload.get("weak_source_warning", False),
        warnings=payload.get("warnings", []),
        source_urls=payload.get("source_urls", []),
    )


def content_brief_from_dict(payload: dict) -> ContentBrief:
    return ContentBrief(
        primary_query=payload["primary_query"],
        likely_intent=payload.get("likely_intent", "Mixed"),
        target_word_count_range=tuple(payload.get("target_word_count_range", (700, 1200))),
        candidate_titles=payload.get("candidate_titles", []),
        suggested_outline=payload.get("suggested_outline", []),
        recommended_concepts_entities=payload.get("recommended_concepts_entities", []),
        questions_to_answer=payload.get("questions_to_answer", []),
        phrases_to_use_naturally=payload.get("phrases_to_use_naturally", []),
        warnings=payload.get("warnings", []),
        source_urls=payload.get("source_urls", []),
    )


def _outline_heading_text(heading: str) -> str:
    return heading.lstrip("#").strip().lower()
