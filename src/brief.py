from __future__ import annotations

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
    )
