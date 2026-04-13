from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ContentBrief


def load_brief(path: str | Path) -> ContentBrief:
    payload: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    brief_payload = payload.get("content_brief", payload)
    return ContentBrief(
        primary_query=brief_payload["primary_query"],
        likely_intent=brief_payload.get("likely_intent", "Mixed"),
        target_word_count_range=tuple(brief_payload.get("target_word_count_range", (700, 1200))),
        candidate_titles=brief_payload.get("candidate_titles", []),
        suggested_outline=brief_payload.get("suggested_outline", []),
        recommended_concepts_entities=brief_payload.get("recommended_concepts_entities", []),
        questions_to_answer=brief_payload.get("questions_to_answer", []),
        phrases_to_use_naturally=brief_payload.get("phrases_to_use_naturally", []),
        warnings=brief_payload.get("warnings", []),
    )


def _heading_text(markdown_heading: str) -> str:
    return markdown_heading.lstrip("#").strip()


def _paragraph_for_section(section: str, brief: ContentBrief) -> str:
    lower = section.lower()
    query_title = brief.primary_query.title()

    if "overview" in lower:
        return (
            f"{query_title} is a focused search topic with mixed intent: readers may want a quick explanation, "
            "release context, viewing options, and a sense of how the pickleball community is reacting. "
            "A useful page should answer those questions directly before moving into reviews or commentary."
        )
    if "release" in lower or "platform" in lower or "watch" in lower:
        return (
            "Cover the official movie listing first, then summarize where readers may be able to watch, stream, "
            "rent, or verify availability. Availability can change, so this section should be checked against "
            "current platform pages before publication."
        )
    if "synopsis" in lower or "trailer" in lower:
        return (
            "Give readers a short, original synopsis without copying platform descriptions. Mention the holiday "
            "movie framing, the pickleball-themed premise, and whether a trailer or first-look clip is available."
        )
    if "reaction" in lower or "reception" in lower or "review" in lower:
        return (
            "Separate formal review signals from community reaction. Rotten Tomatoes, Letterboxd, Reddit, Facebook, "
            "and pickleball media can each add context, but social posts and opinion pieces should be presented as "
            "commentary rather than verified facts."
        )
    if "pickleball" in lower:
        return (
            "Explain why this movie matters to pickleball audiences: it is a novelty holiday film built around the "
            "sport, and fans may care whether the play, culture, and terminology feel authentic."
        )
    if "faq" in lower:
        questions = brief.questions_to_answer[:5]
        if not questions:
            questions = [f"What should readers know about {brief.primary_query}?"]
        return "\n".join(f"**{q}**\nAnswer this clearly in one or two concise paragraphs." for q in questions)

    concepts = ", ".join(brief.recommended_concepts_entities[:6])
    return (
        f"Use this section to cover {section.lower()} in plain language. Work in relevant concepts naturally"
        f"{f', including {concepts}' if concepts else ''}, without stuffing repeated phrases."
    )


def generate_draft_from_brief(brief: ContentBrief) -> str:
    title = brief.candidate_titles[0] if brief.candidate_titles else brief.primary_query.title()
    lines = [f"# {title}", ""]

    if brief.warnings:
        lines.extend([
            "> Draft note: source confidence is limited. Verify release, streaming, cast, and review details before publishing.",
            "",
        ])

    outline = brief.suggested_outline or [
        "## Overview",
        "## Key Details",
        "## What Readers Should Know",
        "## FAQ",
    ]

    for heading in outline:
        section = _heading_text(heading)
        level = "##" if heading.startswith("##") else "##"
        lines.extend([f"{level} {section}", "", _paragraph_for_section(section, brief), ""])

    if brief.recommended_concepts_entities:
        lines.extend([
            "## Concepts To Include Naturally",
            "",
            ", ".join(brief.recommended_concepts_entities[:20]),
            "",
        ])

    if brief.phrases_to_use_naturally:
        lines.extend([
            "## Phrase Guidance",
            "",
            "Use these phrases only where they fit the reader's question: "
            + ", ".join(brief.phrases_to_use_naturally[:15])
            + ".",
            "",
        ])

    return "\n".join(lines).strip() + "\n"
