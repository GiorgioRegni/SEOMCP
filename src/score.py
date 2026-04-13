from __future__ import annotations

from .models import CompetitorAnalysis, DraftAnalysis, ScoreBreakdown


def score_draft(comp: CompetitorAnalysis, draft: DraftAnalysis) -> ScoreBreakdown:
    reasons: list[str] = []

    topical = max(0.0, 100.0 - (len(draft.missing_phrases) * 2.0 + len(draft.missing_entities) * 1.5))
    if draft.missing_phrases:
        reasons.append(f"Missing {len(draft.missing_phrases)} recommended phrases/concepts.")

    structure = min(100.0, draft.heading_coverage * 100.0)
    if structure < 50:
        reasons.append("Heading coverage is lower than top competitors.")

    target_mid = comp.median_word_count if comp.median_word_count > 0 else 900
    wc_diff_ratio = abs(draft.word_count - target_mid) / max(1, target_mid)
    intent = max(0.0, 100.0 - wc_diff_ratio * 100.0 - len(draft.missing_subtopics) * 2.0)
    if draft.missing_subtopics:
        reasons.append(f"Draft is missing {len(draft.missing_subtopics)} likely subtopics/questions.")

    naturalness_penalty = min(30.0, max(0.0, (0.35 - draft.lexical_diversity) * 80.0))
    redundancy_penalty = min(25.0, len(draft.overused_terms) * 2.5)
    if draft.overused_terms:
        reasons.append(f"Possible keyword repetition in terms: {', '.join(draft.overused_terms[:5])}.")

    title_meta = min(100.0, draft.title_h1_alignment * 100.0)
    if title_meta < 50:
        reasons.append("Title/H1 has weak alignment with primary query.")

    overall = (topical * 0.35 + structure * 0.2 + intent * 0.25 + title_meta * 0.2) - naturalness_penalty - redundancy_penalty
    overall = max(0.0, min(100.0, overall))

    reasons.append("Score is heuristic for content quality guidance, not a ranking predictor.")

    return ScoreBreakdown(
        topical_coverage=round(topical, 2),
        structure=round(structure, 2),
        intent_alignment=round(intent, 2),
        naturalness_penalty=round(naturalness_penalty, 2),
        redundancy_penalty=round(redundancy_penalty, 2),
        title_meta=round(title_meta, 2),
        overall=round(overall, 2),
        reasons=reasons,
    )
