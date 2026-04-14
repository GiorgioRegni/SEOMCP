from __future__ import annotations

from collections import Counter
from statistics import median

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from .models import CompetitorAnalysis, DraftAnalysis, PageData
from .utils import STOPWORDS, ngrams, tokenize


def _top_terms(pages: list[PageData], ngram_size: int, top_k: int) -> list[str]:
    counter: Counter[str] = Counter()
    for p in pages:
        tokens = [t for t in tokenize(p.text) if t not in STOPWORDS and len(t) > 2]
        grams = ngrams(tokens, ngram_size)
        counter.update(grams)
    return [term for term, _ in counter.most_common(top_k)]


def _entities_heuristic(text: str) -> list[str]:
    entities = set()
    for line in text.splitlines():
        words = line.strip().split()
        for i in range(len(words) - 1):
            if words[i][:1].isupper() and words[i + 1][:1].isupper():
                candidate = f"{words[i]} {words[i+1]}".strip(".,:;!?()[]{}\"")
                if len(candidate) > 3:
                    entities.add(candidate)
    return list(entities)


def analyze_competitors(query: str, pages: list[PageData], source_urls: list[str] | None = None) -> CompetitorAnalysis:
    word_counts = [p.word_count for p in pages if p.word_count > 0]
    source_urls = source_urls or [p.url for p in pages]
    if not word_counts:
        return CompetitorAnalysis(query, 0, 0, (0, 0), [], [], [], [], True, ["No usable pages found."], source_urls)

    headings = Counter()
    full_text = []
    warnings: list[str] = []
    for p in pages:
        full_text.append(p.text)
        headings.update([h.lower() for h in p.headings.get("h2", [])])
        if p.source_quality_flags:
            warnings.append(f"{p.url}: {', '.join(p.source_quality_flags)}")

    recommended_phrases = _top_terms(pages, 2, 20) + _top_terms(pages, 3, 10)
    entities = Counter()
    for txt in full_text:
        entities.update(_entities_heuristic(txt))

    vectorizer = TfidfVectorizer(stop_words="english", max_features=300)
    matrix = vectorizer.fit_transform(full_text)
    k = min(4, len(full_text))
    km = KMeans(n_clusters=k, n_init=5, random_state=7)
    km.fit(matrix)
    terms = vectorizer.get_feature_names_out()
    cluster_terms: list[str] = []
    for centroid in km.cluster_centers_:
        top_idx = centroid.argsort()[-5:][::-1]
        cluster_terms.extend(terms[i] for i in top_idx)

    subtopics = [h for h, _ in headings.most_common(10)]
    subtopics.extend(t for t in cluster_terms if t not in subtopics)

    weak = len(pages) < 3 or len(warnings) > len(pages) // 2
    if weak:
        warnings.append("Source set may be weak/noisy; recommendations have high uncertainty.")

    return CompetitorAnalysis(
        query=query,
        page_count=len(pages),
        median_word_count=int(median(word_counts)),
        word_count_range=(min(word_counts), max(word_counts)),
        common_headings=[h for h, _ in headings.most_common(12)],
        recommended_phrases=list(dict.fromkeys(recommended_phrases))[:25],
        recommended_entities=[e for e, _ in entities.most_common(20)],
        recommended_subtopics=list(dict.fromkeys(subtopics))[:20],
        weak_source_warning=weak,
        warnings=warnings,
        source_urls=source_urls,
    )


def _readability(text: str) -> dict[str, float]:
    tokens = tokenize(text)
    sentences = [s for s in text.split(".") if s.strip()]
    avg_sentence_len = len(tokens) / max(1, len(sentences))
    long_words = sum(1 for t in tokens if len(t) >= 7)
    return {
        "avg_sentence_len": round(avg_sentence_len, 2),
        "long_word_ratio": round(long_words / max(1, len(tokens)), 3),
    }


def _normalized_tokens(text: str) -> set[str]:
    expanded = text.replace("-", " ")
    return {_singularize(t) for t in tokenize(expanded) if len(t) > 2}


def _singularize(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _covered(needle: str, haystack: str, *, threshold: float = 0.65) -> bool:
    needle_tokens = _normalized_tokens(needle)
    if not needle_tokens:
        return True
    haystack_tokens = _normalized_tokens(haystack)
    return len(needle_tokens.intersection(haystack_tokens)) / len(needle_tokens) >= threshold


def _heading_covered(needle: str, headings: list[str]) -> bool:
    return any(_covered(needle, heading, threshold=0.6) for heading in headings)


def analyze_draft(draft_md: str, query: str, comp: CompetitorAnalysis, title: str | None = None,
                  h1: str | None = None) -> DraftAnalysis:
    tokens = tokenize(draft_md)
    token_set = set(tokens)
    missing_phrases = [p for p in comp.recommended_phrases if not _covered(p, draft_md, threshold=0.8)][:20]

    missing_entities = [e for e in comp.recommended_entities if not _covered(e, draft_md, threshold=0.75)][:15]
    missing_subtopics = [s for s in comp.recommended_subtopics if not _covered(s, draft_md, threshold=0.65)][:12]

    counts = Counter(tokens)
    overused = [w for w, c in counts.items() if c > max(8, len(tokens) * 0.03) and len(w) > 3][:12]

    headings = [line.strip("# ").lower() for line in draft_md.splitlines() if line.lstrip().startswith("#")]
    covered = [h for h in comp.common_headings if _heading_covered(h, headings)]
    heading_cov = len(covered) / max(1, len(comp.common_headings[:8]))

    lex_div = len(token_set) / max(1, len(tokens))

    alignment_base = (title or "") + " " + (h1 or "")
    query_tokens = tokenize(query)
    alignment_tokens = _normalized_tokens(alignment_base.lower())
    align = sum(1 for t in query_tokens if _singularize(t) in alignment_tokens) / max(1, len(query_tokens))

    return DraftAnalysis(
        word_count=len(tokens),
        heading_coverage=round(heading_cov, 3),
        missing_phrases=missing_phrases,
        missing_entities=missing_entities,
        missing_subtopics=missing_subtopics,
        overused_terms=overused,
        readability=_readability(draft_md),
        lexical_diversity=round(lex_div, 3),
        title_h1_alignment=round(align, 3),
    )
