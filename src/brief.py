from __future__ import annotations

import json
import re
from pathlib import Path

from .models import CompetitorAnalysis, ContentBrief, SourceFilteringResult, SourceUrlDecision


def infer_intent(query: str) -> str:
    q = query.lower()
    if any(x in q for x in ["how", "what", "guide", "rules"]):
        return "Informational"
    if any(x in q for x in ["best", "top", "review", "vs"]):
        return "Commercial investigation"
    if any(x in q for x in ["buy", "price", "coupon"]):
        return "Transactional"
    return "Mixed"


NOISY_TERMS = {
    "the latest",
    "featured partners",
    "privacy policy",
    "terms of service",
    "sign in",
    "log in",
    "subscribe",
    "related articles",
    "more pickleball news",
    "subscribe to get the latest pickleball news",
    "table of contents",
    "footer",
}
NOISY_TOKENS = {
    "presented",
    "sponsor",
    "sponsored",
    "cookie",
    "cookies",
    "newsletter",
    "copyright",
    "pb5star",
}
NOISY_PATTERNS = (
    r"do you need .* bag",
    r"basic rules of",
    r"drills for beginners",
    r"gear up for",
    r"related articles",
    r"more .* news",
    r"subscribe .* latest",
)
MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}
INTENT_HEADING_WORDS = {
    "best",
    "beginner",
    "beginners",
    "choose",
    "comparison",
    "cost",
    "explained",
    "faq",
    "guide",
    "how",
    "lesson",
    "lessons",
    "review",
    "tips",
    "types",
    "vs",
    "what",
    "when",
    "where",
    "why",
}


def curate_competitor_analysis(query: str, comp: CompetitorAnalysis) -> CompetitorAnalysis:
    query_terms = set(_tokens(query))

    headings = _clean_list(
        comp.common_headings,
        query_terms=query_terms,
        keep_if_intent_heading=True,
        limit=12,
    )
    phrases = _clean_list(comp.recommended_phrases, query_terms=query_terms, limit=25, allow_weak_seed=True)
    entities = _clean_list(
        comp.recommended_entities,
        query_terms=query_terms,
        limit=20,
        keep_if_intent_heading=False,
        allow_weak_seed=True,
    )
    subtopics = _clean_list(
        comp.recommended_subtopics,
        query_terms=query_terms,
        keep_if_intent_heading=True,
        limit=20,
    )

    if not headings:
        headings = _fallback_headings(query)
    elif comp.weak_source_warning and len(headings) < 8:
        headings = _extend_with_fallbacks(headings, query, 8)
    if not subtopics:
        subtopics = [_heading_text(h) for h in headings]
    elif comp.weak_source_warning and len(subtopics) < 8:
        subtopics = _extend_with_fallbacks(subtopics, query, 8)

    low, high = comp.word_count_range
    median = comp.median_word_count
    if high <= 0:
        low, high, median = 700, 1200, 950
    elif median < 500 and high > 900:
        median = min(max(900, high // 2), high)

    warnings = list(comp.warnings)
    removed = (
        len(comp.common_headings) - len(headings)
        + len(comp.recommended_phrases) - len(phrases)
        + len(comp.recommended_subtopics) - len(subtopics)
    )
    if removed > 0:
        warnings.append(f"Curated noisy or transient extracted terms before building the writing brief ({removed} item(s)).")

    return CompetitorAnalysis(
        query=comp.query,
        page_count=comp.page_count,
        median_word_count=median,
        word_count_range=(low, high),
        common_headings=headings,
        recommended_phrases=phrases,
        recommended_entities=entities,
        recommended_subtopics=subtopics,
        weak_source_warning=comp.weak_source_warning,
        warnings=warnings,
        source_urls=comp.source_urls,
    )


def build_brief(query: str, comp: CompetitorAnalysis) -> ContentBrief:
    low, high = comp.word_count_range
    if low == 0 and high == 0:
        low, high = 700, 1200

    outline = [f"## {_title_case(h)}" for h in comp.common_headings[:8]]
    questions = [_question_for_subtopic(s) for s in comp.recommended_subtopics[:8]]
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


def load_source_filtering(path: str | Path) -> SourceFilteringResult:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return source_filtering_from_dict(payload.get("source_filtering", {}))


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


def source_filtering_from_dict(payload: dict) -> SourceFilteringResult:
    included = payload.get("included", [])
    excluded = [source_decision_from_dict(item) for item in payload.get("excluded", [])]
    decisions = [source_decision_from_dict(item) for item in payload.get("decisions", [])]
    return SourceFilteringResult(included=included, excluded=excluded, decisions=decisions)


def source_decision_from_dict(payload: dict) -> SourceUrlDecision:
    return SourceUrlDecision(
        url=payload.get("url", ""),
        normalized_url=payload.get("normalized_url", ""),
        category=payload.get("category", ""),
        included=payload.get("included", False),
        reason=payload.get("reason", ""),
    )


def _outline_heading_text(heading: str) -> str:
    return heading.lstrip("#").strip().lower()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _clean_list(
    values: list[str],
    *,
    query_terms: set[str],
    limit: int,
    keep_if_intent_heading: bool = True,
    allow_weak_seed: bool = False,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if ":" in value:
            continue
        normalized = " ".join(_tokens(value))
        if not normalized or normalized in seen or _is_noisy(normalized):
            continue
        value_terms = set(normalized.split())
        has_query_overlap = bool(query_terms.intersection(value_terms))
        has_intent_word = keep_if_intent_heading and bool(value_terms.intersection(INTENT_HEADING_WORDS))
        if has_query_overlap or has_intent_word or (allow_weak_seed and len(cleaned) < 4):
            cleaned.append(value.strip())
            seen.add(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def _is_noisy(normalized: str) -> bool:
    terms = set(normalized.split())
    if normalized in NOISY_TERMS:
        return True
    if any(re.search(pattern, normalized) for pattern in NOISY_PATTERNS):
        return True
    if terms.intersection(NOISY_TOKENS):
        return True
    if terms.intersection(MONTHS) and len(terms) <= 3:
        return True
    return False


def _fallback_headings(query: str) -> list[str]:
    return [
        f"what to know about {query}",
        f"how to use {query}",
        f"{query} options and examples",
        f"common mistakes with {query}",
        f"{query} faq",
    ]


def _extend_with_fallbacks(values: list[str], query: str, limit: int) -> list[str]:
    merged = list(values)
    seen = {" ".join(_tokens(value)) for value in merged}
    for fallback in _fallback_headings(query):
        normalized = " ".join(_tokens(fallback))
        if normalized not in seen:
            merged.append(fallback)
            seen.add(normalized)
        if len(merged) >= limit:
            break
    return merged


def _title_case(value: str) -> str:
    return " ".join(word.capitalize() if len(word) > 3 else word for word in value.split())


def _question_for_subtopic(subtopic: str) -> str:
    text = subtopic.strip().rstrip("?")
    if text.lower().startswith(("what ", "how ", "where ", "when ", "why ", "which ")):
        return f"{text}?"
    return f"What should readers know about {text}?"


def _heading_text(heading: str) -> str:
    return heading.lstrip("#").strip().lower()
