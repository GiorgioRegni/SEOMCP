from __future__ import annotations

from .models import ContentBrief, DraftAnalysis, RewriteResult


def _append_missing_sections(draft: str, analysis: DraftAnalysis, brief: ContentBrief) -> tuple[str, list[str], list[str]]:
    changes: list[str] = []
    notes: list[str] = []
    revised = draft.rstrip()

    topics = [t for t in analysis.missing_subtopics[:4] if t.strip()]
    if topics:
        revised += "\n\n## Additional details readers may need\n"
        for topic in topics:
            revised += f"\n### {_title(topic)}\n\n{_paragraph_for_topic(topic, brief)}\n"
        changes.append(f"Added publishable coverage for {len(topics)} missing subtopic(s).")

    if len(draft.split()) < brief.target_word_count_range[0] and "## Practical takeaways" not in draft:
        revised += (
            "\n\n## Practical takeaways\n\n"
            f"If you only remember one thing about {brief.primary_query}, make it this: start with the reader's "
            "immediate decision, explain the terms they are likely to see, and give them a simple next step. "
            "That keeps the page useful without turning it into a glossary or stuffing repeated keywords.\n"
        )
        changes.append("Expanded the draft with practical takeaways to better match the target length.")

    if analysis.missing_entities:
        concepts = ", ".join(analysis.missing_entities[:8])
        notes.append(f"Consider weaving these concepts into existing sections where natural: {concepts}.")

    return revised + "\n", changes, notes


def rewrite_draft(draft: str, brief: ContentBrief, analysis: DraftAnalysis) -> RewriteResult:
    revised, changes, notes = _append_missing_sections(draft, analysis, brief)

    warnings: list[str] = []
    if analysis.overused_terms:
        warnings.append("Potential repetition detected; trim repeated terms in the next pass.")

    if not changes:
        revised = draft
        notes.append("No safe automatic body rewrite was needed; use the analysis JSON for manual editorial judgment.")

    return RewriteResult(
        revised_draft=revised,
        change_log=changes,
        added_items=analysis.missing_subtopics[:4],
        removed_items=analysis.overused_terms[:8],
        warnings=warnings,
        revision_notes=notes,
    )


def _paragraph_for_topic(topic: str, brief: ContentBrief) -> str:
    cleaned = topic.strip().rstrip(".")
    query = brief.primary_query
    return (
        f"{cleaned.capitalize()} matters because it changes how readers understand {query}. "
        "In practice, the right choice usually depends on the reader's level, goal, budget, location, or timeline. "
        "When the details are unclear, check the official source first and treat third-party summaries as helpful context."
    )


def _title(value: str) -> str:
    return " ".join(word.capitalize() if len(word) > 3 else word for word in value.split())
