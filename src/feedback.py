from __future__ import annotations

from .analyze import analyze_draft
from .models import CompetitorAnalysis, ContentBrief, IterationRecord, OptimizeResult
from .rewrite import rewrite_draft
from .score import score_draft


def optimize_draft(query: str, draft: str, comp: CompetitorAnalysis, brief: ContentBrief,
                   iterations: int = 3, title: str | None = None, h1: str | None = None) -> OptimizeResult:
    history: list[IterationRecord] = []
    revision_notes: list[str] = []

    current = draft
    first_analysis = analyze_draft(current, query, comp, title=title, h1=h1)
    first_score = score_draft(comp, first_analysis, brief=brief)
    best_score = first_score

    for i in range(1, iterations + 1):
        analysis_before = analyze_draft(current, query, comp, title=title, h1=h1)
        score_before = score_draft(comp, analysis_before, brief=brief)

        rewritten = rewrite_draft(current, brief, analysis_before)
        current = rewritten.revised_draft
        revision_notes.extend(rewritten.revision_notes)

        analysis_after = analyze_draft(current, query, comp, title=title, h1=h1)
        score_after = score_draft(comp, analysis_after, brief=brief)

        delta = score_after.overall - score_before.overall
        history.append(IterationRecord(
            iteration=i,
            score_before=score_before.overall,
            score_after=score_after.overall,
            delta=round(delta, 2),
            analysis_summary={
                "missing_topics_after": len(analysis_after.missing_subtopics),
                "overused_terms_after": analysis_after.overused_terms,
            },
        ))

        if score_after.overall > best_score.overall:
            best_score = score_after

        if delta < 1.0:
            break

    final_analysis = analyze_draft(current, query, comp, title=title, h1=h1)
    final_score = score_draft(comp, final_analysis, brief=brief)

    summary = (
        f"Optimized in {len(history)} iteration(s). "
        f"Score moved from {first_score.overall:.1f} to {final_score.overall:.1f}."
    )

    return OptimizeResult(
        summary=summary,
        initial_score=first_score,
        final_score=final_score,
        iterations=history,
        final_draft=current,
        revision_notes=list(dict.fromkeys(revision_notes)),
    )
