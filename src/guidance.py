from __future__ import annotations

from typing import Any

from .models import ContentBrief, SourceFetchResult, SourceFilteringResult, to_dict

EDITORIAL_CHECKLIST = [
    "Use the JSON as guidance, not final prose.",
    "Write original copy; do not copy large spans from sources.",
    "Preserve Hugo front matter and custom fields unless explicitly updating SEO fields.",
    "Remove scaffold phrases and internal workflow metadata before publishing.",
    "Use noisy or blocked sources to limit claims, not as article copy.",
    "Prefer reader usefulness and factual clarity over raising the heuristic score.",
    "Run content QA before treating the markdown as final.",
]


def build_writer_guidance(
    *,
    query: str,
    brief: ContentBrief,
    source_filtering: SourceFilteringResult,
    fetch_results: list[SourceFetchResult] | None = None,
    frontmatter_suggestions: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    optimization: dict[str, Any] | None = None,
    qa: dict[str, Any] | None = None,
    noisy_terms_rejected: list[str] | None = None,
) -> dict[str, Any]:
    fetch_results = fetch_results or []
    noisy_terms_rejected = noisy_terms_rejected or []
    used_urls = [result.url for result in fetch_results if result.used_in_analysis]
    failed_urls = [result.url for result in fetch_results if result.status == "failed"]
    do_not_confuse = [
        to_dict(decision)
        for decision in source_filtering.decisions
        if decision.category == "same_name_different_entity"
    ]

    guidance = {
        "query": query,
        "role": "SEO guidance for an AI or human writer; not publishable prose.",
        "likely_intent": brief.likely_intent,
        "target_word_count_range": list(brief.target_word_count_range),
        "source_summary": {
            "included_count": len(source_filtering.included),
            "skipped_count": len(source_filtering.excluded),
            "fetched_count": len([result for result in fetch_results if result.status == "fetched"]),
            "failed_count": len(failed_urls),
            "used_in_analysis_count": len(used_urls),
        },
        "included_urls": source_filtering.included,
        "skipped_urls": [to_dict(decision) for decision in source_filtering.excluded],
        "fetch_results": [to_dict(result) for result in fetch_results],
        "do_not_confuse_sources": do_not_confuse,
        "recommended_coverage": {
            "headings_to_consider": brief.suggested_outline,
            "questions_to_answer": brief.questions_to_answer,
            "concepts_to_cover": brief.recommended_concepts_entities[:20],
            "phrases_to_use_naturally": brief.phrases_to_use_naturally[:20],
        },
        "terms_to_avoid": sorted(set(noisy_terms_rejected)),
        "frontmatter_suggestions": frontmatter_suggestions or {},
        "editorial_checklist": EDITORIAL_CHECKLIST,
    }

    if analysis:
        guidance["draft_gaps"] = {
            "missing_topics": analysis.get("missing_topics", []),
            "overused_terms": analysis.get("overused_terms", []),
            "score_breakdown": analysis.get("score_breakdown", {}),
        }
    if optimization:
        guidance["optimization_summary"] = {
            "summary": optimization.get("summary", ""),
            "score_breakdown": optimization.get("score_breakdown", {}),
            "revision_notes": optimization.get("revision_notes", []),
        }
    if qa:
        guidance["content_qa"] = qa

    return guidance
