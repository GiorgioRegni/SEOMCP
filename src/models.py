from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class SEORequest:
    query: str
    geo: str | None = None
    language: str | None = "en"
    title: str | None = None
    h1: str | None = None
    draft_markdown: str | None = None
    desired_word_count: int | None = None
    tone_notes: str | None = None
    urls: list[str] = field(default_factory=list)
    top_n: int = 8


@dataclass
class PageData:
    url: str
    normalized_url: str
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    headings: dict[str, list[str]] = field(default_factory=lambda: {"h1": [], "h2": [], "h3": []})
    text: str = ""
    markdownish: str = ""
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    source_quality_flags: list[str] = field(default_factory=list)


@dataclass
class SourceUrlDecision:
    url: str
    normalized_url: str
    category: str
    included: bool
    reason: str = ""


@dataclass
class SourceFilteringResult:
    included: list[str] = field(default_factory=list)
    excluded: list[SourceUrlDecision] = field(default_factory=list)
    decisions: list[SourceUrlDecision] = field(default_factory=list)


@dataclass
class CompetitorAnalysis:
    query: str
    page_count: int
    median_word_count: int
    word_count_range: tuple[int, int]
    common_headings: list[str]
    recommended_phrases: list[str]
    recommended_entities: list[str]
    recommended_subtopics: list[str]
    weak_source_warning: bool = False
    warnings: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)


@dataclass
class DraftAnalysis:
    word_count: int
    heading_coverage: float
    missing_phrases: list[str]
    missing_entities: list[str]
    missing_subtopics: list[str]
    overused_terms: list[str]
    readability: dict[str, float]
    lexical_diversity: float
    title_h1_alignment: float


@dataclass
class ScoreBreakdown:
    topical_coverage: float
    structure: float
    intent_alignment: float
    naturalness_penalty: float
    redundancy_penalty: float
    title_meta: float
    overall: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class ContentBrief:
    primary_query: str
    likely_intent: str
    target_word_count_range: tuple[int, int]
    candidate_titles: list[str]
    suggested_outline: list[str]
    recommended_concepts_entities: list[str]
    questions_to_answer: list[str]
    phrases_to_use_naturally: list[str]
    warnings: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)


@dataclass
class RewriteResult:
    revised_draft: str
    change_log: list[str]
    added_items: list[str]
    removed_items: list[str]
    warnings: list[str] = field(default_factory=list)
    revision_notes: list[str] = field(default_factory=list)


@dataclass
class IterationRecord:
    iteration: int
    score_before: float
    score_after: float
    delta: float
    analysis_summary: dict[str, Any]


@dataclass
class OptimizeResult:
    summary: str
    initial_score: ScoreBreakdown
    final_score: ScoreBreakdown
    iterations: list[IterationRecord]
    final_draft: str
    revision_notes: list[str] = field(default_factory=list)


@dataclass
class PositionedSite:
    position: int
    url: str
    domain: str
    title: str = ""
    score: str = ""
    raw_cells: list[str] = field(default_factory=list)


@dataclass
class YourTextGuruPositioningResult:
    keyword: str
    lang: str
    source_url: str
    count: int
    sites: list[PositionedSite]
    warnings: list[str] = field(default_factory=list)


@dataclass
class MarkdownDocument:
    frontmatter_format: str | None
    frontmatter: dict[str, Any] = field(default_factory=dict)
    raw_frontmatter: str = ""
    body: str = ""



def to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj
