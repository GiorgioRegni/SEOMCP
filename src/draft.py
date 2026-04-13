from __future__ import annotations

from pathlib import Path

from .brief import load_saved_brief
from .markdown_doc import build_hugo_document
from .models import ContentBrief


def load_brief(path: str | Path) -> ContentBrief:
    _, brief = load_saved_brief(path)
    return brief


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


def generate_draft_body_from_brief(brief: ContentBrief) -> str:
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


def generate_draft_from_brief(brief: ContentBrief, frontmatter_format: str = "yaml") -> str:
    body = generate_draft_body_from_brief(brief)
    return build_hugo_document(brief, body, frontmatter_format)
