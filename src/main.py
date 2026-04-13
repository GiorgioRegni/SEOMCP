from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .analyze import analyze_competitors, analyze_draft
from .brief import build_brief
from .extract import extract_main_content
from .fetch import extract_basic_metadata, fetch_html, is_junk_url
from .feedback import optimize_draft
from .models import SEORequest, to_dict
from .rewrite import rewrite_draft
from .score import score_draft
from .serp import collect_serp_urls
from .browser_session import DEFAULT_CDP_PORT, DEFAULT_PROFILE_DIR, DEFAULT_START_URL, launch_chrome
from .draft import generate_draft_from_brief, load_brief
from .yourtextguru import scrape_positioned_sites
from .utils import JSON_CACHE, dump_json, ensure_dirs, load_text, normalize_url, slugify

app = typer.Typer(help="seo-writer-skill CLI")


def run_pipeline(req: SEORequest) -> tuple:
    urls = collect_serp_urls(req.query, req.top_n, req.urls, req.geo, req.language)
    seen: set[str] = set()
    pages = []
    for url in urls:
        nurl = normalize_url(url)
        if nurl in seen or is_junk_url(nurl):
            continue
        seen.add(nurl)
        try:
            html = fetch_html(url)
            page = extract_basic_metadata(url, html)
            page = extract_main_content(page, html)
            if "thin_content" not in page.source_quality_flags:
                pages.append(page)
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"warn: failed to fetch {url}: {exc}", err=True)

    comp = analyze_competitors(req.query, pages)
    brief = build_brief(req.query, comp)
    return pages, comp, brief


@app.command()
def brief(
    query: str = typer.Option(...),
    urls: Optional[str] = typer.Option(None, help="Comma-separated URLs"),
    top_n: int = 8,
    geo: Optional[str] = None,
    language: str = "en",
) -> None:
    ensure_dirs()
    req = SEORequest(query=query, geo=geo, language=language, urls=(urls.split(",") if urls else []), top_n=top_n)
    _, comp, seo_brief = run_pipeline(req)
    payload = {"competitor_analysis": to_dict(comp), "content_brief": to_dict(seo_brief)}
    out = JSON_CACHE / f"brief-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def analyze(
    query: str = typer.Option(...),
    draft: str = typer.Option(..., help="Path to markdown draft"),
    urls: Optional[str] = typer.Option(None),
    title: Optional[str] = None,
    h1: Optional[str] = None,
    top_n: int = 8,
) -> None:
    ensure_dirs()
    req = SEORequest(query=query, title=title, h1=h1, urls=(urls.split(",") if urls else []), top_n=top_n)
    _, comp, seo_brief = run_pipeline(req)
    draft_md = load_text(draft)
    draft_analysis = analyze_draft(draft_md, query, comp, title=title, h1=h1)
    score = score_draft(comp, draft_analysis)
    payload = {
        "summary": "Draft analyzed against competitor-derived recommendations.",
        "score_breakdown": to_dict(score),
        "missing_topics": draft_analysis.missing_subtopics,
        "overused_terms": draft_analysis.overused_terms,
        "recommended_outline_changes": seo_brief.suggested_outline,
        "suggested_title_meta": seo_brief.candidate_titles,
    }
    out = JSON_CACHE / f"analyze-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def rewrite(
    query: str = typer.Option(...),
    draft: str = typer.Option(...),
    urls: Optional[str] = typer.Option(None),
    title: Optional[str] = None,
    h1: Optional[str] = None,
    top_n: int = 8,
) -> None:
    req = SEORequest(query=query, title=title, h1=h1, urls=(urls.split(",") if urls else []), top_n=top_n)
    _, comp, seo_brief = run_pipeline(req)
    draft_md = load_text(draft)
    draft_analysis = analyze_draft(draft_md, query, comp, title=title, h1=h1)
    result = rewrite_draft(draft_md, seo_brief, draft_analysis)
    payload = {
        "summary": "Draft rewritten from SEO brief and gap analysis.",
        "revised_draft": result.revised_draft,
        "change_log": result.change_log,
        "what_was_added": result.added_items,
        "what_was_removed": result.removed_items,
        "warnings": result.warnings,
    }
    out = JSON_CACHE / f"rewrite-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def optimize(
    query: str = typer.Option(...),
    draft: str = typer.Option(...),
    urls: Optional[str] = typer.Option(None),
    iterations: int = 3,
    title: Optional[str] = None,
    h1: Optional[str] = None,
    top_n: int = 8,
) -> None:
    req = SEORequest(query=query, title=title, h1=h1, urls=(urls.split(",") if urls else []), top_n=top_n)
    _, comp, seo_brief = run_pipeline(req)
    draft_md = load_text(draft)
    result = optimize_draft(query, draft_md, comp, seo_brief, iterations=iterations, title=title, h1=h1)
    payload = {
        "summary": result.summary,
        "score_breakdown": {"initial": to_dict(result.initial_score), "final": to_dict(result.final_score)},
        "iterations": [to_dict(i) for i in result.iterations],
        "revised_draft": result.final_draft,
        "recommended_outline_changes": seo_brief.suggested_outline,
        "suggested_title_meta": seo_brief.candidate_titles,
    }
    out = JSON_CACHE / f"optimize-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def launch_chrome_profile(
    profile_dir: str = typer.Option(str(DEFAULT_PROFILE_DIR), help="Persistent Chrome profile directory."),
    port: Optional[int] = typer.Option(DEFAULT_CDP_PORT, help="Chrome DevTools remote debugging port. Omit to allocate a free port."),
    start_url: str = typer.Option(DEFAULT_START_URL, help="Page to open when launching Chrome."),
    headless: bool = typer.Option(False, help="Run Chrome headless. Use false for first login."),
) -> None:
    try:
        payload = launch_chrome(profile_dir=profile_dir, port=port, start_url=start_url, headless=headless)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def yourtextguru_positioned_sites(
    keyword: str = typer.Option(..., help="Keyword to inspect in YourText.Guru positioning."),
    limit: int = typer.Option(10, help="Number of positioned sites to return."),
    lang: str = typer.Option("en_us", help="YourText.Guru language code."),
    profile_dir: str = typer.Option(str(DEFAULT_PROFILE_DIR), help="Chrome profile directory with YourText.Guru auth."),
    port: Optional[int] = typer.Option(DEFAULT_CDP_PORT, help="Chrome DevTools remote debugging port. Omit to reuse the profile port or allocate a free one."),
    launch: bool = typer.Option(True, help="Launch Chrome if the DevTools endpoint is not already running."),
    headless: bool = typer.Option(False, help="Run Chrome headless if launched by this command."),
) -> None:
    try:
        result = scrape_positioned_sites(
            keyword=keyword,
            limit=limit,
            lang=lang,
            profile_dir=profile_dir,
            port=port,
            launch_if_missing=launch,
            headless=headless,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(json.dumps(to_dict(result), indent=2))


@app.command()
def draft(
    brief_path: str = typer.Option(..., "--brief", help="Path to a saved brief JSON file."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional markdown output path."),
) -> None:
    brief_obj = load_brief(brief_path)
    draft_md = generate_draft_from_brief(brief_obj)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(draft_md, encoding="utf-8")
    typer.echo(draft_md)


if __name__ == "__main__":
    app()
