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
            f"{query_title} is a focused search topic with mixed intent. Readers may want a quick explanation, "
            "where it fits in the pickleball landscape, practical details, and what to verify before they act. "
            "A useful page should answer those questions directly before moving into broader context."
        )
    if "release" in lower or "platform" in lower or "watch" in lower or "where" in lower:
        return (
            "Start with the official source, then summarize the practical next step for readers. If availability, "
            "hours, schedules, booking, or event details can change, tell readers to verify the current page before "
            "making plans."
        )
    if "synopsis" in lower or "trailer" in lower:
        return (
            "Give readers a short, original summary without copying source descriptions. Focus on the facts that "
            "help them understand the topic quickly and decide what to check next."
        )
    if "reaction" in lower or "reception" in lower or "review" in lower:
        return (
            "Separate verified source details from community reaction. Reviews, social posts, and local listings can "
            "add useful context, but present them as commentary unless the claim is backed by an official source."
        )
    if "what to know" in lower or "how to use" in lower or "options" in lower:
        return (
            f"Explain {section.lower()} in plain language. Cover what the reader can do with the information, "
            "what details may change, and which official source should be checked before relying on it."
        )
    if "pickleball" in lower:
        return (
            "Explain why this topic matters to pickleball players or fans. Focus on practical details, location or "
            "program context, and what readers should verify before visiting, booking, buying, or sharing the page."
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
            "> Draft note: source confidence is limited. Verify names, locations, schedules, prices, availability, and claims against official sources before publishing.",
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
