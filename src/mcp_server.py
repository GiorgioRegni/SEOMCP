from __future__ import annotations

import json
import sys

from .analyze import analyze_draft
from .brief import build_brief
from .main import resolve_content_context, run_pipeline
from .models import SEORequest, to_dict
from .rewrite import rewrite_draft
from .feedback import optimize_draft
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


"""
Minimal MCP-compatible JSON IO server.
Protocol shape:
{"tool": "build_seo_brief", "input": {...}}
Responds with: {"ok": true, "result": {...}} or {"ok": false, "error": "..."}
"""


def build_seo_brief(payload: dict) -> dict:
    req = SEORequest(
        query=payload["query"],
        geo=payload.get("geo"),
        language=payload.get("language", "en"),
        urls=payload.get("urls", []),
        top_n=payload.get("top_n", 8),
    )
    _, comp, brief = run_pipeline(req)
    return {"source_urls": brief.source_urls, "competitor_analysis": to_dict(comp), "content_brief": to_dict(brief)}


def analyze_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    urls = ",".join(req.urls) if req.urls else None
    comp, brief = resolve_content_context(req.query, req.top_n, urls=urls, brief_path=payload.get("brief"))
    draft_doc = parse_markdown_document(payload.get("draft_markdown", ""))
    title = payload.get("title") or title_from_document(draft_doc)
    h1 = payload.get("h1") or h1_from_body(draft_doc.body)
    analysis = analyze_draft(draft_doc.body, req.query, comp, title, h1)
    return {
        "summary": "Draft analyzed.",
        "draft_analysis": to_dict(analysis),
        "brief": to_dict(brief),
        "frontmatter_suggestions": build_frontmatter_suggestions(brief),
        "source_urls": brief.source_urls,
    }


def rewrite_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    urls = ",".join(req.urls) if req.urls else None
    comp, brief = resolve_content_context(req.query, req.top_n, urls=urls, brief_path=payload.get("brief"))
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
    result["frontmatter_suggestions"] = build_frontmatter_suggestions(brief)
    result["source_urls"] = brief.source_urls
    return result


def optimize_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    urls = ",".join(req.urls) if req.urls else None
    comp, brief = resolve_content_context(req.query, req.top_n, urls=urls, brief_path=payload.get("brief"))
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
    response["frontmatter_suggestions"] = build_frontmatter_suggestions(brief)
    response["source_urls"] = brief.source_urls
    return response


def launch_chrome_profile(payload: dict) -> dict:
    return launch_chrome(
        profile_dir=payload.get("profile_dir", "data/chrome/yourtextguru"),
        port=payload.get("port"),
        start_url=payload.get("start_url", "https://yourtext.guru/login"),
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
    "build_seo_brief": build_seo_brief,
    "analyze_seo_draft": analyze_seo_draft,
    "rewrite_seo_draft": rewrite_seo_draft,
    "optimize_seo_draft": optimize_seo_draft,
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
