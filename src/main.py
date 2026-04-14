from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .analyze import analyze_competitors, analyze_draft
from .brief import (
    build_brief,
    curate_competitor_analysis_with_rejections,
    load_fetch_results,
    load_noisy_terms_rejected,
    load_saved_brief,
    load_source_filtering,
)
from .content_qa import qa_markdown_content
from .extract import extract_main_content
from .fetch import extract_basic_metadata, fetch_html
from .feedback import optimize_draft
from .guidance import build_writer_guidance
from .models import SEORequest, SourceFetchResult, SourceFilteringResult, to_dict
from .rewrite import rewrite_draft
from .score import score_draft
from .serp import collect_serp_urls
from .source_filter import filter_source_urls
from .browser_session import DEFAULT_CDP_PORT, DEFAULT_PROFILE_DIR, DEFAULT_START_URL, launch_chrome
from .draft import generate_draft_from_brief, load_brief
from .markdown_doc import (
    build_frontmatter_suggestions,
    h1_from_body,
    parse_markdown_document,
    render_markdown_document,
    title_from_document,
    update_hugo_seo_fields,
)
from .yourtextguru import scrape_positioned_sites
from .utils import JSON_CACHE, dump_json, ensure_dirs, load_text, normalize_url, slugify

app = typer.Typer(help="seo-writer-skill CLI")


def _split_urls(urls: Optional[str]) -> list[str]:
    return [url.strip() for url in urls.split(",") if url.strip()] if urls else []


def run_pipeline(
    req: SEORequest,
    *,
    allow_forums: bool = False,
    allow_pdfs: bool = False,
    allow_social: bool = False,
    allow_marketplaces: bool = False,
    allow_homepages: bool = False,
) -> tuple:
    collection_limit = max(req.top_n, len(req.urls)) if req.urls else req.top_n
    urls = collect_serp_urls(req.query, collection_limit, req.urls, req.geo, req.language)
    source_filtering = filter_source_urls(
        urls,
        req.query,
        req.top_n,
        allow_forums=allow_forums,
        allow_pdfs=allow_pdfs,
        allow_social=allow_social,
        allow_marketplaces=allow_marketplaces,
        allow_homepages=allow_homepages,
    )
    seen: set[str] = set()
    pages = []
    fetch_results: list[SourceFetchResult] = []
    for url in source_filtering.included:
        nurl = normalize_url(url)
        if nurl in seen:
            continue
        seen.add(nurl)
        try:
            html = fetch_html(url)
            page = extract_basic_metadata(url, html)
            page = extract_main_content(page, html)
            used = "thin_content" not in page.source_quality_flags
            fetch_results.append(SourceFetchResult(
                url=url,
                status="fetched",
                used_in_analysis=used,
                word_count=page.word_count,
                quality_flags=page.source_quality_flags,
            ))
            if used:
                pages.append(page)
        except Exception as exc:  # noqa: BLE001
            fetch_results.append(SourceFetchResult(url=url, status="failed", used_in_analysis=False, error=str(exc)))
            typer.echo(f"warn: failed to fetch {url}: {exc}", err=True)

    raw_comp = analyze_competitors(req.query, pages, source_urls=source_filtering.included)
    comp, noisy_terms_rejected = curate_competitor_analysis_with_rejections(req.query, raw_comp)
    brief = build_brief(req.query, comp)
    return pages, comp, brief, raw_comp, source_filtering, fetch_results, noisy_terms_rejected


def resolve_content_context(query: str, top_n: int, urls: Optional[str] = None,
                            brief_path: Optional[str] = None) -> tuple:
    if urls:
        req = SEORequest(query=query, urls=_split_urls(urls), top_n=top_n)
        _, comp, seo_brief, _, source_filtering, fetch_results, noisy_terms_rejected = run_pipeline(req)
        return comp, seo_brief, source_filtering, fetch_results, noisy_terms_rejected

    path = Path(brief_path) if brief_path else JSON_CACHE / f"brief-{slugify(query)}.json"
    if path.exists():
        comp, seo_brief = load_saved_brief(path)
        return comp, seo_brief, load_source_filtering(path), load_fetch_results(path), load_noisy_terms_rejected(path)

    req = SEORequest(query=query, urls=[], top_n=top_n)
    _, comp, seo_brief, _, source_filtering, fetch_results, noisy_terms_rejected = run_pipeline(req)
    return comp, seo_brief, source_filtering, fetch_results, noisy_terms_rejected


def brief_payload(
    comp,
    seo_brief,
    raw_comp=None,
    source_filtering: SourceFilteringResult | None = None,
    fetch_results: list[SourceFetchResult] | None = None,
    noisy_terms_rejected: list[str] | None = None,
) -> dict:
    return {
        "source_urls": seo_brief.source_urls,
        "source_filtering": to_dict(source_filtering or SourceFilteringResult(included=seo_brief.source_urls)),
        "fetch_results": [to_dict(result) for result in (fetch_results or [])],
        "noisy_terms_rejected": noisy_terms_rejected or [],
        "raw_competitor_analysis": to_dict(raw_comp or comp),
        "competitor_analysis": to_dict(comp),
        "content_brief": to_dict(seo_brief),
    }


def analyze_payload(query: str, draft_path: str, comp, seo_brief, source_filtering: SourceFilteringResult,
                    title: str | None = None, h1: str | None = None,
                    fetch_results: list[SourceFetchResult] | None = None,
                    noisy_terms_rejected: list[str] | None = None) -> dict:
    draft_doc = parse_markdown_document(load_text(draft_path))
    effective_title = title or title_from_document(draft_doc)
    effective_h1 = h1 or h1_from_body(draft_doc.body)
    draft_analysis = analyze_draft(draft_doc.body, query, comp, title=effective_title, h1=effective_h1)
    score = score_draft(comp, draft_analysis, brief=seo_brief)
    payload = {
        "summary": "Draft analyzed against competitor-derived recommendations.",
        "score_breakdown": to_dict(score),
        "frontmatter_suggestions": build_frontmatter_suggestions(seo_brief, draft_doc),
        "source_urls": seo_brief.source_urls,
        "source_filtering": to_dict(source_filtering),
        "fetch_results": [to_dict(result) for result in (fetch_results or [])],
        "missing_topics": draft_analysis.missing_subtopics,
        "overused_terms": draft_analysis.overused_terms,
        "recommended_outline_changes": seo_brief.suggested_outline,
        "suggested_title_meta": seo_brief.candidate_titles,
    }
    payload["writer_guidance"] = build_writer_guidance(
        query=query,
        brief=seo_brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=payload["frontmatter_suggestions"],
        analysis=payload,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    return payload


def optimize_payload(query: str, draft_path: str, comp, seo_brief, source_filtering: SourceFilteringResult,
                     iterations: int, title: str | None = None, h1: str | None = None,
                     update_frontmatter: bool = False, output: str | None = None,
                     fetch_results: list[SourceFetchResult] | None = None,
                     noisy_terms_rejected: list[str] | None = None) -> dict:
    draft_doc = parse_markdown_document(load_text(draft_path))
    effective_title = title or title_from_document(draft_doc)
    effective_h1 = h1 or h1_from_body(draft_doc.body)
    result = optimize_draft(query, draft_doc.body, comp, seo_brief, iterations=iterations, title=effective_title, h1=effective_h1)
    draft_doc.body = result.final_draft
    if update_frontmatter:
        draft_doc = update_hugo_seo_fields(draft_doc, seo_brief, overwrite=True)
    revised_draft = render_markdown_document(draft_doc)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(revised_draft, encoding="utf-8")
    payload = {
        "summary": result.summary,
        "score_breakdown": {"initial": to_dict(result.initial_score), "final": to_dict(result.final_score)},
        "iterations": [to_dict(i) for i in result.iterations],
        "revised_draft": revised_draft,
        "revision_notes": result.revision_notes,
        "frontmatter_suggestions": build_frontmatter_suggestions(seo_brief, draft_doc),
        "source_urls": seo_brief.source_urls,
        "source_filtering": to_dict(source_filtering),
        "fetch_results": [to_dict(result) for result in (fetch_results or [])],
        "recommended_outline_changes": seo_brief.suggested_outline,
        "suggested_title_meta": seo_brief.candidate_titles,
    }
    payload["writer_guidance"] = build_writer_guidance(
        query=query,
        brief=seo_brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=payload["frontmatter_suggestions"],
        optimization=payload,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    return payload


def _ignored_recommendations(analysis: dict, source_filtering: SourceFilteringResult) -> list[str]:
    ignored = [
        f"Skipped {decision.url}: {decision.reason or decision.category}"
        for decision in source_filtering.excluded
    ]
    suggestion = analysis.get("frontmatter_suggestions", {})
    if suggestion.get("draft") is True:
        ignored.append("Did not apply draft: true automatically; front matter updates require --update-frontmatter.")
    return ignored


@app.command()
def brief(
    query: str = typer.Option(...),
    urls: Optional[str] = typer.Option(None, help="Comma-separated URLs"),
    top_n: int = 8,
    geo: Optional[str] = None,
    language: str = "en",
    allow_forums: bool = typer.Option(False, help="Allow forum/community URLs."),
    allow_pdfs: bool = typer.Option(False, help="Allow PDF URLs."),
    allow_social: bool = typer.Option(False, help="Allow social/profile URLs."),
    allow_marketplaces: bool = typer.Option(False, help="Allow marketplace/product listing URLs."),
    allow_homepages: bool = typer.Option(False, help="Allow generic homepage URLs."),
) -> None:
    ensure_dirs()
    req = SEORequest(query=query, geo=geo, language=language, urls=_split_urls(urls), top_n=top_n)
    _, comp, seo_brief, raw_comp, source_filtering, fetch_results, noisy_terms_rejected = run_pipeline(
        req,
        allow_forums=allow_forums,
        allow_pdfs=allow_pdfs,
        allow_social=allow_social,
        allow_marketplaces=allow_marketplaces,
        allow_homepages=allow_homepages,
    )
    frontmatter_suggestions = build_frontmatter_suggestions(seo_brief)
    payload = brief_payload(
        comp,
        seo_brief,
        raw_comp=raw_comp,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    payload["writer_guidance"] = build_writer_guidance(
        query=query,
        brief=seo_brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=frontmatter_suggestions,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    out = JSON_CACHE / f"brief-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def analyze(
    query: str = typer.Option(...),
    draft: str = typer.Option(..., help="Path to markdown draft"),
    urls: Optional[str] = typer.Option(None),
    brief_path: Optional[str] = typer.Option(None, "--brief", help="Saved brief JSON. Defaults to data/json/brief-<query>.json when URLs are omitted."),
    title: Optional[str] = None,
    h1: Optional[str] = None,
    top_n: int = 8,
) -> None:
    ensure_dirs()
    comp, seo_brief, source_filtering, fetch_results, noisy_terms_rejected = resolve_content_context(query, top_n, urls=urls, brief_path=brief_path)
    payload = analyze_payload(
        query,
        draft,
        comp,
        seo_brief,
        source_filtering,
        title=title,
        h1=h1,
        fetch_results=fetch_results,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    out = JSON_CACHE / f"analyze-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def rewrite(
    query: str = typer.Option(...),
    draft: str = typer.Option(...),
    urls: Optional[str] = typer.Option(None),
    brief_path: Optional[str] = typer.Option(None, "--brief", help="Saved brief JSON. Defaults to data/json/brief-<query>.json when URLs are omitted."),
    title: Optional[str] = None,
    h1: Optional[str] = None,
    top_n: int = 8,
    update_frontmatter: bool = typer.Option(False, help="Update Hugo SEO fields in front matter."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional path for revised markdown."),
) -> None:
    comp, seo_brief, source_filtering, fetch_results, noisy_terms_rejected = resolve_content_context(query, top_n, urls=urls, brief_path=brief_path)
    draft_doc = parse_markdown_document(load_text(draft))
    effective_title = title or title_from_document(draft_doc)
    effective_h1 = h1 or h1_from_body(draft_doc.body)
    draft_analysis = analyze_draft(draft_doc.body, query, comp, title=effective_title, h1=effective_h1)
    result = rewrite_draft(draft_doc.body, seo_brief, draft_analysis)
    draft_doc.body = result.revised_draft
    if update_frontmatter:
        draft_doc = update_hugo_seo_fields(draft_doc, seo_brief, overwrite=True)
    revised_draft = render_markdown_document(draft_doc)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(revised_draft, encoding="utf-8")
    payload = {
        "summary": "Draft rewritten from SEO brief and gap analysis.",
        "revised_draft": revised_draft,
        "change_log": result.change_log,
        "what_was_added": result.added_items,
        "what_was_removed": result.removed_items,
        "warnings": result.warnings,
        "revision_notes": result.revision_notes,
        "frontmatter_suggestions": build_frontmatter_suggestions(seo_brief, draft_doc),
        "source_urls": seo_brief.source_urls,
        "source_filtering": to_dict(source_filtering),
        "fetch_results": [to_dict(result) for result in fetch_results],
    }
    payload["writer_guidance"] = build_writer_guidance(
        query=query,
        brief=seo_brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=payload["frontmatter_suggestions"],
        analysis={"missing_topics": draft_analysis.missing_subtopics, "overused_terms": draft_analysis.overused_terms},
        noisy_terms_rejected=noisy_terms_rejected,
    )
    out = JSON_CACHE / f"rewrite-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def optimize(
    query: str = typer.Option(...),
    draft: str = typer.Option(...),
    urls: Optional[str] = typer.Option(None),
    brief_path: Optional[str] = typer.Option(None, "--brief", help="Saved brief JSON. Defaults to data/json/brief-<query>.json when URLs are omitted."),
    iterations: int = 3,
    title: Optional[str] = None,
    h1: Optional[str] = None,
    top_n: int = 8,
    update_frontmatter: bool = typer.Option(False, help="Update Hugo SEO fields in front matter."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional path for revised markdown."),
) -> None:
    comp, seo_brief, source_filtering, fetch_results, noisy_terms_rejected = resolve_content_context(query, top_n, urls=urls, brief_path=brief_path)
    payload = optimize_payload(
        query,
        draft,
        comp,
        seo_brief,
        source_filtering,
        iterations=iterations,
        title=title,
        h1=h1,
        update_frontmatter=update_frontmatter,
        output=output,
        fetch_results=fetch_results,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    out = JSON_CACHE / f"optimize-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command("build-post")
def build_post(
    query: str = typer.Option(...),
    urls: Optional[str] = typer.Option(None, help="Comma-separated URLs"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Canonical final article markdown path."),
    revised_output: Optional[str] = typer.Option(
        None,
        "--working-output",
        "--revised-output",
        help="Working/scaffold markdown path.",
    ),
    brief_path: Optional[str] = typer.Option(None, "--brief", help="Saved brief path. Defaults to data/json/brief-<query>.json."),
    top_n: int = 8,
    iterations: int = 3,
    update_frontmatter: bool = typer.Option(False, help="Update Hugo SEO fields in working output."),
    frontmatter_format: str = typer.Option("yaml", help="Front matter format when creating a new article."),
    allow_forums: bool = typer.Option(False, help="Allow forum/community URLs."),
    allow_pdfs: bool = typer.Option(False, help="Allow PDF URLs."),
    allow_social: bool = typer.Option(False, help="Allow social/profile URLs."),
    allow_marketplaces: bool = typer.Option(False, help="Allow marketplace/product listing URLs."),
    allow_homepages: bool = typer.Option(False, help="Allow generic homepage URLs."),
) -> None:
    ensure_dirs()
    slug = slugify(query)
    article_path = Path(output or f"examples/{slug}.md")
    working_path = Path(revised_output or f"examples/working-{slug}.md")
    saved_brief_path = Path(brief_path) if brief_path else JSON_CACHE / f"brief-{slug}.json"

    commands_run = [
        f"python3 -m src.main build-post --query {json.dumps(query)}",
    ]

    if urls or not saved_brief_path.exists():
        req = SEORequest(query=query, urls=_split_urls(urls), top_n=top_n)
        _, comp, seo_brief, raw_comp, source_filtering, fetch_results, noisy_terms_rejected = run_pipeline(
            req,
            allow_forums=allow_forums,
            allow_pdfs=allow_pdfs,
            allow_social=allow_social,
            allow_marketplaces=allow_marketplaces,
            allow_homepages=allow_homepages,
        )
        brief_data = brief_payload(
            comp,
            seo_brief,
            raw_comp=raw_comp,
            source_filtering=source_filtering,
            fetch_results=fetch_results,
            noisy_terms_rejected=noisy_terms_rejected,
        )
        dump_json(saved_brief_path, brief_data)
    else:
        comp, seo_brief = load_saved_brief(saved_brief_path)
        source_filtering = load_source_filtering(saved_brief_path)
        fetch_results = load_fetch_results(saved_brief_path)
        noisy_terms_rejected = load_noisy_terms_rejected(saved_brief_path)
        brief_data = brief_payload(
            comp,
            seo_brief,
            source_filtering=source_filtering,
            fetch_results=fetch_results,
            noisy_terms_rejected=noisy_terms_rejected,
        )

    final_article_exists = article_path.exists()
    draft_path = article_path if final_article_exists else working_path

    if not final_article_exists:
        working_path.parent.mkdir(parents=True, exist_ok=True)
        working_path.write_text(
            generate_draft_from_brief(seo_brief, frontmatter_format=frontmatter_format),
            encoding="utf-8",
        )

    analysis = analyze_payload(
        query,
        str(draft_path),
        comp,
        seo_brief,
        source_filtering,
        fetch_results=fetch_results,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    analyze_path = JSON_CACHE / f"analyze-{slug}.json"
    dump_json(analyze_path, analysis)

    optimized = optimize_payload(
        query,
        str(draft_path),
        comp,
        seo_brief,
        source_filtering,
        iterations=iterations,
        update_frontmatter=update_frontmatter,
        output=str(working_path),
        fetch_results=fetch_results,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    optimize_path = JSON_CACHE / f"optimize-{slug}.json"
    dump_json(optimize_path, optimized)

    qa_path = article_path if final_article_exists else working_path
    qa = qa_markdown_content(query, qa_path.read_text(encoding="utf-8"), noisy_terms_rejected)
    guidance = build_writer_guidance(
        query=query,
        brief=seo_brief,
        source_filtering=source_filtering,
        fetch_results=fetch_results,
        frontmatter_suggestions=analysis.get("frontmatter_suggestions", {}),
        analysis=analysis,
        optimization=optimized,
        qa=qa,
        noisy_terms_rejected=noisy_terms_rejected,
    )
    guidance_path = JSON_CACHE / f"guidance-{slug}.json"
    dump_json(guidance_path, guidance)

    report = {
        "summary": "Guidance workflow completed. Markdown outputs may be scaffolds until an AI or editor completes the final pass.",
        "query": query,
        "brief_path": str(saved_brief_path),
        "article_path": str(article_path),
        "revised_path": str(working_path),
        "scaffold_path": str(working_path),
        "revised_scaffold_path": str(working_path),
        "writer_guidance_path": str(guidance_path),
        "final_article_path": str(article_path) if final_article_exists and qa.get("passed") else None,
        "content_qa_path": str(qa_path),
        "analyze_path": str(analyze_path),
        "analysis_path": str(analyze_path),
        "optimize_path": str(optimize_path),
        "optimization_path": str(optimize_path),
        "source_urls": seo_brief.source_urls,
        "source_filtering": to_dict(source_filtering),
        "fetch_results": [to_dict(result) for result in fetch_results],
        "content_qa": qa,
        "noisy_terms_rejected": noisy_terms_rejected,
        "score_breakdown": optimized["score_breakdown"],
        "frontmatter_changed": update_frontmatter,
        "ignored_recommendations": _ignored_recommendations(analysis, source_filtering),
        "commands_run": commands_run,
    }
    report_path = JSON_CACHE / f"report-{slug}.json"
    dump_json(report_path, report)

    payload = {
        "brief": brief_data,
        "analysis": analysis,
        "optimization": optimized,
        "writer_guidance": guidance,
        "report": report,
    }
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


@app.command("content-qa")
def content_qa(
    query: str = typer.Option(...),
    draft: str = typer.Option(..., help="Path to Hugo/markdown content to QA."),
    brief_path: Optional[str] = typer.Option(None, "--brief", help="Saved brief JSON for noisy-term context."),
) -> None:
    noisy_terms: list[str] = []
    path = Path(brief_path) if brief_path else JSON_CACHE / f"brief-{slugify(query)}.json"
    if path.exists():
        noisy_terms = load_noisy_terms_rejected(path)
    payload = qa_markdown_content(query, load_text(draft), noisy_terms)
    out = JSON_CACHE / f"qa-{slugify(query)}.json"
    dump_json(out, payload)
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def draft(
    brief_path: str = typer.Option(..., "--brief", help="Path to a saved brief JSON file."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional markdown output path."),
    frontmatter_format: str = typer.Option("yaml", help="Front matter format: yaml, toml, or none."),
) -> None:
    brief_obj = load_brief(brief_path)
    draft_md = generate_draft_from_brief(brief_obj, frontmatter_format=frontmatter_format)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(draft_md, encoding="utf-8")
    typer.echo(draft_md)


if __name__ == "__main__":
    app()
