from __future__ import annotations

import json
import sys

from .analyze import analyze_draft
from .brief import build_brief
from .main import run_pipeline
from .models import SEORequest, to_dict
from .rewrite import rewrite_draft
from .feedback import optimize_draft
from .yourtextguru import scrape_positioned_sites
from .browser_session import launch_chrome


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
    return {"competitor_analysis": to_dict(comp), "content_brief": to_dict(brief)}


def analyze_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    _, comp, brief = run_pipeline(req)
    draft = payload.get("draft_markdown", "")
    analysis = analyze_draft(draft, req.query, comp, payload.get("title"), payload.get("h1"))
    return {
        "summary": "Draft analyzed.",
        "draft_analysis": to_dict(analysis),
        "brief": to_dict(brief),
    }


def rewrite_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    _, comp, brief = run_pipeline(req)
    draft = payload.get("draft_markdown", "")
    analysis = analyze_draft(draft, req.query, comp, payload.get("title"), payload.get("h1"))
    rewritten = rewrite_draft(draft, brief, analysis)
    return to_dict(rewritten)


def optimize_seo_draft(payload: dict) -> dict:
    req = SEORequest(query=payload["query"], urls=payload.get("urls", []), top_n=payload.get("top_n", 8))
    _, comp, brief = run_pipeline(req)
    result = optimize_draft(
        req.query,
        payload.get("draft_markdown", ""),
        comp,
        brief,
        iterations=payload.get("iterations", 3),
        title=payload.get("title"),
        h1=payload.get("h1"),
    )
    return to_dict(result)


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
