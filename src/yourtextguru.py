from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from .browser_session import DEFAULT_CDP_PORT, cdp_endpoint, ensure_chrome
from .models import PositionedSite, YourTextGuruPositioningResult, to_dict
from .utils import JSON_CACHE, dump_json, ensure_dirs, slugify


DEFAULT_YOURTEXTGURU_PROFILE_DIR = Path("data/chrome/yourtextguru")


def positioning_url(keyword: str, lang: str = "en_us") -> str:
    encoded = quote(keyword.strip(), safe="")
    return f"https://yourtext.guru/positioning/keywords/{encoded}?lang={lang}"


def _score_like(value: str) -> bool:
    return bool(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?%?", value.strip()))


def _site_from_row(row: dict, position: int) -> PositionedSite | None:
    url = row.get("url", "").strip()
    if not url:
        return None
    cells = [c.strip() for c in row.get("cells", []) if c.strip()]
    title = row.get("title", "").strip()
    if not title:
        candidates = [c for c in cells if url not in c and not _score_like(c)]
        title = max(candidates, key=len) if candidates else ""
    score = row.get("score", "").strip()
    if not score:
        numeric = [c for c in cells if _score_like(c)]
        score = numeric[0] if numeric else ""
    return PositionedSite(
        position=position,
        url=url,
        domain=row.get("domain", "").strip(),
        title=title,
        score=score,
        raw_cells=cells,
    )


def scrape_positioned_sites(
    keyword: str,
    limit: int = 10,
    lang: str = "en_us",
    profile_dir: str | Path = DEFAULT_YOURTEXTGURU_PROFILE_DIR,
    port: int | None = DEFAULT_CDP_PORT,
    launch_if_missing: bool = True,
    headless: bool = False,
    timeout_ms: int = 45000,
    save: bool = True,
) -> YourTextGuruPositioningResult:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Install Playwright with `python3 -m pip install -r requirements.txt`.") from exc

    ensure_dirs()
    url = positioning_url(keyword, lang=lang)
    browser_info = ensure_chrome(
        profile_dir=profile_dir,
        port=port,
        start_url=url,
        launch_if_missing=launch_if_missing,
        headless=headless,
    )
    active_port = int(browser_info["port"])

    warnings: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_endpoint(active_port))
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            warnings.append("Timed out waiting for network idle; scraping current DOM.")

        current_url = page.url.lower()
        title = page.title().lower()
        login_visible = page.locator("input[type='password']").count() > 0
        if "/login" in current_url or "connexion" in title or "login" in title or login_visible:
            raise RuntimeError(
                "YourText.Guru redirected to login. Launch Chrome with `launch-chrome-profile`, log in in that profile, "
                "then rerun this command."
            )

        page.wait_for_timeout(1500)
        rows = page.evaluate(
            """
            (limit) => {
              const host = location.hostname;
              const seen = new Set();
              const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
              const isExternal = (href) => {
                try {
                  const u = new URL(href, location.href);
                  return /^https?:$/.test(u.protocol) && u.hostname && !u.hostname.includes(host);
                } catch {
                  return false;
                }
              };
              const domainFrom = (href) => {
                try { return new URL(href, location.href).hostname.replace(/^www\\./, ''); }
                catch { return ''; }
              };
              const out = [];
              const pushCandidate = (href, cells, title, score) => {
                const absolute = new URL(href, location.href).href;
                if (seen.has(absolute)) return;
                seen.add(absolute);
                out.push({
                  url: absolute,
                  domain: domainFrom(absolute),
                  title: clean(title),
                  score: clean(score),
                  cells: cells.map(clean).filter(Boolean),
                });
              };

              for (const tr of Array.from(document.querySelectorAll('tr'))) {
                const cells = Array.from(tr.querySelectorAll('th,td')).map((el) => clean(el.innerText));
                const links = Array.from(tr.querySelectorAll('a[href]'))
                  .map((a) => a.href)
                  .filter(isExternal);
                if (!links.length) continue;
                const titleCell = cells.find((c) => c.length > 8 && !/^\\d+([,.]\\d+)?%?$/.test(c)) || '';
                const scoreCell = cells.find((c) => /^\\d+([,.]\\d+)?%?$/.test(c)) || '';
                pushCandidate(links[0], cells, titleCell, scoreCell);
                if (out.length >= limit) return out;
              }

              const anchors = Array.from(document.querySelectorAll('a[href]')).filter((a) => isExternal(a.href));
              for (const a of anchors) {
                const box = a.closest('tr, li, article, section, .card, .row, [class*=item], [class*=result]') || a;
                const cells = [clean(box.innerText)];
                pushCandidate(a.href, cells, clean(a.innerText), '');
                if (out.length >= limit) return out;
              }
              return out;
            }
            """,
            limit,
        )
        page.close()

    sites = []
    for row in rows:
        site = _site_from_row(row, len(sites) + 1)
        if site:
            sites.append(site)
        if len(sites) >= limit:
            break

    if not sites:
        warnings.append("No positioned sites found in the rendered page. The selector may need updating.")

    result = YourTextGuruPositioningResult(
        keyword=keyword,
        lang=lang,
        source_url=url,
        count=len(sites),
        sites=sites,
        warnings=warnings,
    )

    if save:
        out = JSON_CACHE / f"yourtextguru-positioning-{slugify(keyword)}.json"
        dump_json(out, to_dict(result))

    return result
