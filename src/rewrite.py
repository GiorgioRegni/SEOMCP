from __future__ import annotations

from .models import ContentBrief, DraftAnalysis, RewriteResult


def _append_missing_sections(draft: str, analysis: DraftAnalysis, brief: ContentBrief) -> tuple[str, list[str]]:
    changes: list[str] = []
    revised = draft

    if analysis.missing_subtopics:
        revised += "\n\n## Added Coverage\n"
        for topic in analysis.missing_subtopics[:5]:
            revised += f"\n### {topic.title()}\n- Add practical guidance, definitions, and examples for {topic}.\n"
        changes.append(f"Added sections for {len(analysis.missing_subtopics[:5])} missing subtopics.")

    if analysis.missing_entities:
        revised += "\n\n## Key Concepts to Mention Naturally\n"
        revised += ", ".join(analysis.missing_entities[:10]) + "\n"
        changes.append("Added concept/entity reminder section.")

    if len(draft.split()) < brief.target_word_count_range[0]:
        revised += "\n\n## Practical Steps\n"
        revised += "1. Start with clear definitions.\n2. Explain key rules/concepts.\n3. Cover common mistakes and edge cases.\n"
        changes.append("Expanded body with practical steps to approach target length.")

    return revised, changes


def rewrite_draft(draft: str, brief: ContentBrief, analysis: DraftAnalysis) -> RewriteResult:
    revised, changes = _append_missing_sections(draft, analysis, brief)

    warnings: list[str] = []
    if analysis.overused_terms:
        warnings.append("Potential repetition detected; trim repeated terms in the next pass.")

    return RewriteResult(
        revised_draft=revised,
        change_log=changes,
        added_items=analysis.missing_subtopics[:5] + analysis.missing_entities[:8],
        removed_items=analysis.overused_terms[:8],
        warnings=warnings,
    )
