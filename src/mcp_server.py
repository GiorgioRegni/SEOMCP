from __future__ import annotations

import json
import sys

from .analyze import analyze_draft
from .content_qa import qa_markdown_content
from .guidance import build_writer_guidance
from .main import resolve_content_context, run_pipeline
from .models import SEORequest, to_dict
from .rewrite import rewrite_draft
from .feedback import optimize_draft
from .score import score_draft
from .serp import discover_serp_urls
from .yourtextguru import scrape_positioned_sites
from .browser_session import launch_chrome
from .markdown_doc import (
    build_frontmatter_suggestions,
    h1_from_body,
    parse_markdown_document,
    render_markdown_document,
    title_from_document,
    update_hugo_seo_fields,
)
from .utils import JSON_CACHE, slugify


"""
Minimal MCP-compatible JSON IO server.
Protocol shape:
{"tool": "build_seo_brief", "input": {...}}
Responds with: {"ok": true, "result": {...}} or {"ok": false, "error": "..."}
"""


def get_seo_writer_instructions(payload: dict | None = None) -> dict:
    return {
        "role": (
            "The Python tools are a guidance/statistics engine. Codex or another "
            "MCP-consuming AI is responsible for writing the final Hugo article."
        ),
        "canonical_paths": {
            "final_article": "examples/<slug>.md",
            "working_scaffold": "examples/working-<slug>.md",
            "brief": "data/json/brief-<slug>.json",
            "guidance": "data/json/guidance-<slug>.json",
            "analysis": "data/json/analyze-<slug>.json",
            "optimization": "data/json/optimize-<slug>.json",
            "qa": "data/json/qa-<slug>.json",
            "report": "data/json/report-<slug>.json",
        },
        "recommended_loop": [
            "Build or reuse a brief for the keyword.",
            "Draft or inspect the canonical Hugo article.",
            "Analyze the article body against the brief.",
            "Use writer_guidance, missing topics, score reasons, and source filtering as guidance.",
            "Edit the canonical Hugo article directly; do not treat scaffold output as final prose.",
            "Run content QA.",
            "Iterate only when QA fails, important gaps remain, or a rewrite improves the article without hurting prose.",
        ],
        "network_requirements": {
            "offline_safe": [
                "get_seo_writer_instructions",
                "qa_seo_content",
            ],
            "uses_network_when_context_is_missing": [
                "analyze_seo_draft",
                "rewrite_seo_draft",
                "optimize_seo_draft",
            ],
            "requires_network_for_new_briefs": [
                "build_seo_brief",
                "discover_serp_urls",
            ],
            "requires_browser": [
                "launch_chrome_profile",
                "discover_serp_urls when serp_provider is google-chrome",
            ],
            "serp_provider_env": {
                "provider_selector": "SEO_WRITER_SERP_PROVIDER=brave|serper|serpapi|google-chrome",
                "default_resolution_order": [
                    "Use user-provided urls first.",
                    "If urls are omitted, use SEO_WRITER_SERP_PROVIDER when set.",
                    "If no provider is selected, auto-select the first configured API key: Brave, then Serper, then SerpAPI.",
                    "If no provider or API key is configured, return no URLs with a warning instead of guessing.",
                    "Use google-chrome only when explicitly selected.",
                ],
                "brave": "BRAVE_SEARCH_API_KEY or SEO_WRITER_BRAVE_API_KEY",
                "serper": "SERPER_API_KEY or SEO_WRITER_SERPER_API_KEY",
                "serpapi": "SERPAPI_API_KEY or SEO_WRITER_SERPAPI_API_KEY",
                "google_chrome": "No API key; uses Chrome DevTools and may hit consent/CAPTCHA pages.",
                "google_chrome_options": {
                    "profile": "SEO_WRITER_GOOGLE_CHROME_PROFILE",
                    "port": "SEO_WRITER_GOOGLE_CHROME_PORT",
                    "headless": "SEO_WRITER_GOOGLE_CHROME_HEADLESS",
                },
            },
            "offline_strategy": [
                "Prefer saved brief files such as data/json/brief-<slug>.json when available.",
                "If network access is unavailable, analyze against the saved brief rather than fetching URLs again.",
                "If a tool reports fetch failures, use fetch_results/source_filtering as confidence guidance.",
                "Do not mention failed fetches, blocked URLs, or network errors in final article copy.",
            ],
        },
        "stop_or_iterate": {
            "hard_gate": "content-qa must pass before an article is final.",
            "iterate_when": [
                "content-qa fails",
                "important missing_topics, missing_entities, or reader questions remain",
                "the article does not satisfy likely search intent",
                "headings miss useful sections from the guidance",
                "front matter is generic or misleading",
                "overused terms make the prose read repetitive",
                "optimization improves the overall score by roughly 3-5+ points without hurting prose",
            ],
            "stop_when": [
                "content-qa passes",
                "missing topics are empty or only weak/noisy suggestions remain",
                "the article answers the main reader intent directly",
                "front matter is publishable",
                "the latest optimizer pass gives little or no score improvement",
                "manual reading says the article is useful, natural, and Hugo-ready",
            ],
            "judgment_rule": (
                "If the score improves but the prose gets worse, reject the change. "
                "If the score is mediocre but the article is useful, accurate, and QA-clean, "
                "prefer editorial judgment over the score."
            ),
        },
        "final_article_rules": [
            "Preserve Hugo front matter and custom fields unless explicitly updating SEO fields.",
            "Never leave scaffold phrases in final content.",
            "Never include internal workflow metadata, failed fetch notes, scores, or CLI process details in the article.",
            "Use source pages for abstraction, not copying.",
            "Avoid keyword stuffing.",
            "Write the finished publishable article to examples/<slug>.md.",
        ],
        "frontmatter_rules": [
            "Supported formats: YAML --- and TOML +++.",
            "Only manage title, description, tags, and draft when front matter updates are requested.",
            "Do not set draft: true when the article is intended to publish.",
        ],
        "useful_tools": [
            "discover_serp_urls",
            "build_seo_brief",
            "analyze_seo_draft",
            "rewrite_seo_draft",
            "optimize_seo_draft",
            "qa_seo_content",
        ],
    }


def build_seo_brief(payload: dict) -> dict:
    req = SEORequest(
        query=payload["query"],
        geo=payload.get("geo"),
        language=payload.get("language", "en"),
        urls=payload.get("urls", []),
        top_n=payload.get("top_n", 8),
    )
    _, comp, brief, raw_comp, source_filtering, fetch_results, noisy_terms_rejected = run_pipeline(
        req,
        serp_provider=payload.get("serp_provider"),
    )
    frontmatter_suggestions = build_frontmatter_suggestions(brief)
    result = {
        "serp_path": str(JSON_CACHE / f"serp-{slugify(req.query)}.json") if (JSON_CACHE / f"serp-{slugify(req.query)}.json").exists() else "",
        "source_urls": brief.source_urls,
        "source_filtering": to_dict(source_filtering),
        "fetch_results": [to_dict(item) for item in fetch_results],
        "noisy_terms_rejected": noisy_terms_rejected,
        "raw_competitor_analysis": to_dict(raw_comp),
        "competitor_analysis": to_dict(comp),
        "content_brief": to_dict(brief),
    }
    result["writer_guidance"] = build_writer_guidance(
        query=req.query,
        brief=brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=frontmatter_suggestions,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    return result


def discover_serp(payload: dict) -> dict:
    result = discover_serp_urls(
        query=payload["query"],
        top_n=payload.get("top_n", 10),
        provider_name=payload.get("serp_provider") or payload.get("provider"),
        geo=payload.get("geo"),
        language=payload.get("language", "en"),
        manual_urls=payload.get("urls") or None,
    )
    return to_dict(result)


def analyze_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    urls = ",".join(req.urls) if req.urls else None
    comp, brief, source_filtering, fetch_results, noisy_terms_rejected = resolve_content_context(
        req.query,
        req.top_n,
        urls=urls,
        brief_path=payload.get("brief"),
        serp_provider=payload.get("serp_provider"),
    )
    draft_doc = parse_markdown_document(payload.get("draft_markdown", ""))
    title = payload.get("title") or title_from_document(draft_doc)
    h1 = payload.get("h1") or h1_from_body(draft_doc.body)
    analysis = analyze_draft(draft_doc.body, req.query, comp, title, h1)
    score = score_draft(comp, analysis, brief=brief)
    result = {
        "summary": "Draft analyzed.",
        "draft_analysis": to_dict(analysis),
        "score_breakdown": to_dict(score),
        "brief": to_dict(brief),
        "frontmatter_suggestions": build_frontmatter_suggestions(brief, draft_doc),
        "source_urls": brief.source_urls,
        "source_filtering": to_dict(source_filtering),
        "fetch_results": [to_dict(item) for item in fetch_results],
    }
    result["writer_guidance"] = build_writer_guidance(
        query=req.query,
        brief=brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=result["frontmatter_suggestions"],
        analysis={
            "missing_topics": analysis.missing_subtopics,
            "overused_terms": analysis.overused_terms,
            "score_breakdown": result["score_breakdown"],
        },
        noisy_terms_rejected=noisy_terms_rejected,
    )
    return result


def rewrite_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    urls = ",".join(req.urls) if req.urls else None
    comp, brief, source_filtering, fetch_results, noisy_terms_rejected = resolve_content_context(
        req.query,
        req.top_n,
        urls=urls,
        brief_path=payload.get("brief"),
        serp_provider=payload.get("serp_provider"),
    )
    draft_doc = parse_markdown_document(payload.get("draft_markdown", ""))
    title = payload.get("title") or title_from_document(draft_doc)
    h1 = payload.get("h1") or h1_from_body(draft_doc.body)
    analysis = analyze_draft(draft_doc.body, req.query, comp, title, h1)
    rewritten = rewrite_draft(draft_doc.body, brief, analysis)
    draft_doc.body = rewritten.revised_draft
    if payload.get("update_frontmatter", False):
        draft_doc = update_hugo_seo_fields(draft_doc, brief, overwrite=True)
    result = to_dict(rewritten)
    result["revised_draft"] = render_markdown_document(draft_doc)
    result["frontmatter_suggestions"] = build_frontmatter_suggestions(brief, draft_doc)
    result["source_urls"] = brief.source_urls
    result["source_filtering"] = to_dict(source_filtering)
    result["fetch_results"] = [to_dict(item) for item in fetch_results]
    result["writer_guidance"] = build_writer_guidance(
        query=req.query,
        brief=brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=result["frontmatter_suggestions"],
        analysis={"missing_topics": analysis.missing_subtopics, "overused_terms": analysis.overused_terms},
        noisy_terms_rejected=noisy_terms_rejected,
    )
    return result


def optimize_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    urls = ",".join(req.urls) if req.urls else None
    comp, brief, source_filtering, fetch_results, noisy_terms_rejected = resolve_content_context(
        req.query,
        req.top_n,
        urls=urls,
        brief_path=payload.get("brief"),
        serp_provider=payload.get("serp_provider"),
    )
    draft_doc = parse_markdown_document(payload.get("draft_markdown", ""))
    title = payload.get("title") or title_from_document(draft_doc)
    h1 = payload.get("h1") or h1_from_body(draft_doc.body)
    result = optimize_draft(
        req.query,
        draft_doc.body,
        comp,
        brief,
        iterations=payload.get("iterations", 3),
        title=title,
        h1=h1,
    )
    draft_doc.body = result.final_draft
    if payload.get("update_frontmatter", False):
        draft_doc = update_hugo_seo_fields(draft_doc, brief, overwrite=True)
    response = to_dict(result)
    response["final_draft"] = render_markdown_document(draft_doc)
    response["frontmatter_suggestions"] = build_frontmatter_suggestions(brief, draft_doc)
    response["source_urls"] = brief.source_urls
    response["source_filtering"] = to_dict(source_filtering)
    response["fetch_results"] = [to_dict(item) for item in fetch_results]
    response["writer_guidance"] = build_writer_guidance(
        query=req.query,
        brief=brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=response["frontmatter_suggestions"],
        optimization=response,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    return response


def qa_seo_content(payload: dict) -> dict:
    return qa_markdown_content(
        payload["query"],
        payload.get("draft_markdown", ""),
        payload.get("noisy_terms", []),
    )


def launch_chrome_profile(payload: dict) -> dict:
    return launch_chrome(
        profile_dir=payload.get("profile_dir", "data/chrome/seo-writer"),
        port=payload.get("port"),
        start_url=payload.get("start_url", "about:blank"),
        headless=payload.get("headless", False),
    )


def get_yourtextguru_positioned_sites(payload: dict) -> dict:
    result = scrape_positioned_sites(
        keyword=payload["keyword"],
        limit=payload.get("limit", 10),
        lang=payload.get("lang", "en_us"),
        profile_dir=payload.get("profile_dir", "data/chrome/yourtextguru"),
        port=payload.get("port"),
        launch_if_missing=payload.get("launch", True),
        headless=payload.get("headless", False),
    )
    return to_dict(result)


TOOLS = {
    "get_seo_writer_instructions": get_seo_writer_instructions,
    "discover_serp_urls": discover_serp,
    "build_seo_brief": build_seo_brief,
    "analyze_seo_draft": analyze_seo_draft,
    "rewrite_seo_draft": rewrite_seo_draft,
    "optimize_seo_draft": optimize_seo_draft,
    "qa_seo_content": qa_seo_content,
    "launch_chrome_profile": launch_chrome_profile,
    "get_yourtextguru_positioned_sites": get_yourtextguru_positioned_sites,
}


def serve() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            tool = req.get("tool")
            payload = req.get("input", {})
            if tool not in TOOLS:
                raise ValueError(f"Unknown tool: {tool}")
            result = TOOLS[tool](payload)
            print(json.dumps({"ok": True, "result": result}))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}))
        sys.stdout.flush()


if __name__ == "__main__":
    serve()
