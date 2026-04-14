# seo-writer-skill (prototype)

`seo-writer-skill` is a local, tool-assisted SEO guidance prototype that:

1. Collects candidate competitor URLs (manual list in v1; pluggable provider abstraction).
2. Fetches and caches pages from the open web.
3. Extracts readable content and heading structure.
4. Builds a practical content brief from common patterns.
5. Analyzes a draft for coverage/structure/naturalness gaps.
6. Produces scaffold revisions, writer guidance, and iterative optimization signals.
7. Exposes both a CLI and a thin MCP-compatible JSON interface.

The Python tools are not the final writer. They provide guidance, stats, source context, and QA for Codex or another MCP-consuming AI to write the actual publishable Hugo article.

---

## What it does

- Creates **recommendation sets**:
  - Recommended phrases
  - Recommended entities/concepts
  - Recommended subtopics/questions
- Scores drafts using a **transparent heuristic score** with reasons:
  - Topical coverage
  - Structure
  - Intent alignment
  - Naturalness penalty
  - Redundancy penalty
  - Title/meta alignment
- Generates a **content brief**, **writer guidance**, and **rewrite guidance**.
- Runs multi-pass optimization and stores iteration logs as JSON.
- Runs final-content QA checks for scaffold text, internal metadata, noisy terms, and Hugo front matter.

## What it does **not** do

- It does **not** predict Google rankings.
- It does **not** use paid SEO APIs in v1.
- It does **not** guarantee factual correctness of source pages.
- It should **not** copy source text; it abstracts concepts.
- It does **not** author final publishable prose by itself; generated markdown may be scaffold output for an AI writer loop.

---

## Safety/quality rules in v1

- Never copy large spans from competitor pages.
- Use abstraction, not duplication.
- Avoid keyword stuffing.
- Prefer semantic coverage + useful structure.
- Flag weak/noisy source sets.
- Surface uncertainty via warnings.

---

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Project layout

- `src/main.py` – CLI entrypoint and pipeline orchestration.
- `src/serp.py` – SERP provider abstraction (manual + placeholder provider).
- `src/source_filter.py` – conservative source URL classification before fetch.
- `src/fetch.py` – fetch, HTML metadata extraction, caching.
- `src/extract.py` – trafilatura-based readable content extraction with a BeautifulSoup fallback.
- `src/analyze.py` – competitor and draft analysis.
- `src/score.py` – transparent heuristic scoring.
- `src/brief.py` – content brief generation.
- `src/rewrite.py` – rewrite/gap-fill logic.
- `src/feedback.py` – iterative optimization loop.
- `src/guidance.py` – writer-facing guidance JSON for AI/MCP content loops.
- `src/content_qa.py` – final markdown QA checks.
- `src/mcp_stdio_server.py` – MCP stdio server for MCP clients.
- `src/mcp_server.py` – legacy JSON-lines tool server for direct smoke tests.
- `src/browser_session.py` – optional Chrome DevTools profile launcher for authenticated browser-backed tools.
- `src/yourtextguru.py` – optional YourText.Guru scraper using the authenticated Chrome session.
- `src/models.py` – typed dataclasses.
- `src/utils.py` – helpers, cache paths, tokenization.
- `data/html`, `data/json` – local cache and reports.
- `examples/` – sample query/draft/report.

---

## CLI usage

### Build a Hugo guidance bundle

```bash
python3 -m src.main build-post \
  --query "pickleball brackets" \
  --urls "https://example.com/page-one,https://example.com/page-two" \
  --output examples/pickleball-brackets.md \
  --working-output examples/working-pickleball-brackets.md \
  --iterations 3
```

`build-post` filters noisy URLs, builds or reuses `data/json/brief-<query>.json`, creates a working markdown scaffold when the final article does not exist, runs analysis/optimization, writes `data/json/guidance-<query>.json`, runs content QA, and stores `data/json/report-<query>.json`.

The canonical final Hugo article should live at `examples/<slug>.md`. Rough generated output should live at `examples/working-<slug>.md` or another clearly named working path. Review the guidance JSON and let Codex or another writer synthesize the final Hugo article into the canonical file. `--revised-output` is still accepted as a backward-compatible alias for `--working-output`.

Source filtering is conservative by default. It excludes malformed URLs, social/profile pages, PDFs, forums, broad homepages, and marketplace/product listings unless you pass an explicit allow flag such as `--allow-forums`, `--allow-pdfs`, `--allow-social`, `--allow-marketplaces`, or `--allow-homepages`.

### Build brief

```bash
python3 -m src.main brief \
  --query "pickleball rules" \
  --urls "https://usapickleball.org/rules/,https://www.pickleballengland.org/rules/,https://picklehaus.com/the-ultimate-guide-to-pickleball-rules-tips-and-techniques/,https://recsports.msu.edu/activity-rules/pickleball-rules,https://www.bigapplerecsports.com/pages/pickleball-rules,https://theburrowmn.com/pickleballrules,https://santamonicapickleballclub.org/official-usapa-rules,https://usapickleball.org/docs/rules/USAP-Official-Rulebook.pdf,https://www.zogsports.com/rules/pickleball-rules/,https://www.reddit.com/r/Pickleball/comments/1ef6k90/really_great_animated_guide_to_the_pickleball/"
```

### Analyze a draft

```bash
python -m src.main analyze --query "pickleball rules" --draft examples/draft.md --urls "https://usapickleball.org/what-is-pickleball/official-rules/"
```

Drafts may include Hugo YAML (`---`) or TOML (`+++`) front matter. Analysis excludes front matter from scoring and uses front matter `title` as title context when `--title` is omitted.

When `--urls` is omitted, `analyze`, `rewrite`, and `optimize` automatically reuse `data/json/brief-<query>.json` if it exists. You can also pass a specific saved brief with `--brief path/to/brief.json`.

### Rewrite a draft

```bash
python -m src.main rewrite --query "pickleball rules" --draft examples/draft.md --urls "https://usapickleball.org/what-is-pickleball/official-rules/"
```

By default, rewrite and optimize preserve existing Hugo front matter and rewrite only the body. Output should be treated as scaffold/gap-fill guidance unless an editor has reviewed it. Pass `--update-frontmatter` to update managed SEO fields: `title`, `description`, `tags`, and `draft`.

Pass `--output examples/working-article.md` to also write the revised markdown to a working file for diffing/review. After editorial synthesis, put the publishable version in the canonical article file.

### Generate a first draft from a saved brief

```bash
python3 -m src.main draft \
  --brief data/json/brief-a-pickleball-christmas.json \
  --output examples/a-pickleball-christmas-draft.md
```

New drafts emit YAML front matter by default. Use `--frontmatter-format toml` for TOML or `--frontmatter-format none` for body-only markdown.

### Optimize draft iteratively

```bash
python -m src.main optimize --query "pickleball rules" --draft examples/draft.md --iterations 3 --urls "https://usapickleball.org/what-is-pickleball/official-rules/"
```

### QA final markdown before publishing

```bash
python3 -m src.main content-qa \
  --query "pickleball rules" \
  --draft examples/pickleball-rules.md
```

The QA command checks for scaffold phrases, internal workflow metadata, noisy extracted terms, suspicious repetition, and Hugo front matter issues. It writes `data/json/qa-<query>.json`.

### Authenticated YourText.Guru keyword service

Some keyword services are behind a login and cannot be fetched with plain `requests`. For those, the prototype can launch a normal Chrome instance with a persistent local profile and a Chrome DevTools endpoint. Log in once in that profile, then reuse the session from CLI or MCP tools.

First launch Chrome and log in:

```bash
python3 -m src.main launch-chrome-profile \
  --profile-dir data/chrome/yourtextguru \
  --start-url "https://yourtext.guru/login"
```

Then scrape the best positioned pages for a keyword:

```bash
python3 -m src.main yourtextguru-positioned-sites \
  --keyword "a pickleball christmas" \
  --limit 10 \
  --lang en_us \
  --profile-dir data/chrome/yourtextguru
```

The command navigates the authenticated browser to:

```text
https://yourtext.guru/positioning/keywords/a%20pickleball%20christmas?lang=en_us
```

and writes a JSON cache file under `data/json/yourtextguru-positioning-<keyword>.json`.

Notes:

- The Chrome profile is ignored by git because it contains local cookies/session data.
- If `--port` is omitted, the launcher allocates a free localhost port and stores it in the profile metadata for reuse.
- If the page redirects to login, complete login in the launched browser and rerun the scrape command.
- This is intentionally separate from the open-web SERP/fetch pipeline because it depends on a user-controlled authenticated session.

---

## MCP-compatible interface

### Recommended MCP stdio server

Use this entrypoint for MCP clients:

```bash
python3 -m src.mcp_stdio_server
```

The server exposes these tools:

- `get_seo_writer_instructions`
- `build_seo_brief`
- `analyze_seo_draft`
- `rewrite_seo_draft`
- `optimize_seo_draft`
- `qa_seo_content`
- `launch_chrome_profile`
- `get_yourtextguru_positioned_sites`

Inputs and outputs are JSON-compatible dictionaries. Draft inputs may contain Hugo YAML or TOML front matter. Rewrite/optimize output is still scaffold guidance unless an editor turns it into final copy.

An MCP-consuming AI should call `get_seo_writer_instructions` at the start of a content workflow. That tool returns the canonical file layout, recommended loop, stop/iterate criteria, front matter rules, and final article rules. The brief/analyze/optimize tools also return `writer_guidance`, but `get_seo_writer_instructions` is the stable orientation payload for how to use the system.

Some MCP tools need network access:

- `build_seo_brief` fetches public web pages when building a new brief.
- `analyze_seo_draft`, `rewrite_seo_draft`, and `optimize_seo_draft` can work offline when a saved `data/json/brief-<slug>.json` exists, but may fetch pages if URLs are provided or no saved brief exists.
- `launch_chrome_profile` and `get_yourtextguru_positioned_sites` require local browser support and network access to the authenticated service.
- `get_seo_writer_instructions` and `qa_seo_content` are offline-safe.

In restricted environments, reuse saved briefs under `data/json/brief-<slug>.json` and treat `fetch_results` / `source_filtering` as confidence guidance. Do not include failed fetches, blocked URLs, or network errors in final article copy.

### Local clone MCP setup

For a local clone, install dependencies first:

```bash
git clone https://github.com/GiorgioRegni/SEOMCP.git
cd SEOMCP
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then configure your MCP client to launch the stdio server from that clone.

Generic JSON-style MCP config:

```json
{
  "mcpServers": {
    "seo-writer-skill": {
      "command": "/absolute/path/to/SEOMCP/.venv/bin/python",
      "args": ["-m", "src.mcp_stdio_server"],
      "cwd": "/absolute/path/to/SEOMCP"
    }
  }
}
```

Codex-style TOML config:

```toml
[mcp_servers.seo-writer-skill]
command = "/absolute/path/to/SEOMCP/.venv/bin/python"
args = ["-m", "src.mcp_stdio_server"]
cwd = "/absolute/path/to/SEOMCP"
```

Use a local clone when you want persistent `data/` caches, generated reports, and Hugo markdown files in the repo.

### Run from public GitHub with uvx

The repo includes `pyproject.toml` with a `seo-writer-mcp` console script, so MCP clients that can run `uvx` can install from a public GitHub URL:

```json
{
  "mcpServers": {
    "seo-writer-skill": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/GiorgioRegni/SEOMCP.git",
        "seo-writer-mcp"
      ]
    }
  }
}
```

This is convenient for tool-only use. For content workflows that should write `examples/` and `data/json/` into your project, prefer a local clone and set `cwd` to the repo root.

### Natural prompt example

With the MCP server configured, you should be able to give the client AI a short request:

```text
Generate an SEO article for "hulk hogan" using these URLs:
- https://en.wikipedia.org/wiki/Hulk_Hogan
- https://www.imdb.com/name/nm0001356/
- https://www.wwe.com/superstars/hulkhogan
- https://abcnews.go.com/GMA/Culture/wwe-star-hulk-hogan-cause-death-revealed/story?id=124249036
```

The MCP-consuming AI should call `get_seo_writer_instructions`, build or reuse the brief, write the final Hugo article to `examples/<slug>.md`, keep rough scaffold output in `examples/working-<slug>.md`, run `qa_seo_content`, and iterate only when QA fails or important gaps remain.

### MCP tool call examples

Build a brief:

```json
{"tool":"get_seo_writer_instructions","input":{}}
```

Then build a brief:

```json
{"tool":"build_seo_brief","input":{"query":"pickleball rules","urls":["https://usapickleball.org/what-is-pickleball/official-rules/"]}}
```

Analyze a Hugo draft:

```json
{
  "tool": "analyze_seo_draft",
  "input": {
    "query": "object storage",
    "draft_markdown": "---\ntitle: Object Storage\ndraft: false\n---\n\n## Overview\n\nObject storage stores data as objects."
  }
}
```

QA final content:

```json
{
  "tool": "qa_seo_content",
  "input": {
    "query": "object storage",
    "draft_markdown": "---\ntitle: Object Storage\ndraft: false\n---\n\n## Overview\n\nObject storage stores data as objects."
  }
}
```

Authenticated browser-backed keyword service example:

```json
{"tool":"get_yourtextguru_positioned_sites","input":{"keyword":"a pickleball christmas","limit":10,"lang":"en_us","profile_dir":"data/chrome/yourtextguru"}}
```

For `rewrite_seo_draft` and `optimize_seo_draft`, pass `"update_frontmatter": true` to update Hugo SEO fields. Otherwise front matter is preserved and only the markdown body is revised.

### Legacy JSON-lines smoke server

For direct shell smoke tests without an MCP client, the older JSON-lines wrapper is still available:

```bash
printf '%s\n' '{"tool":"qa_seo_content","input":{"query":"object storage","draft_markdown":"## Object Storage\n\nObject storage stores data as objects."}}' \
  | python3 -m src.mcp_server
```

That legacy wrapper is useful for debugging, but MCP clients should use `python3 -m src.mcp_stdio_server` or the `seo-writer-mcp` console script.

---

## How scoring works (heuristic)

Overall score combines:

- Coverage and missing recommended concepts.
- Heading/outline coverage vs competitor patterns.
- Intent alignment (word-count and missing subtopics proxy).
- Penalties for low lexical diversity and repeated terms.
- Title/H1 query alignment.

Each score includes human-readable reasons and explicitly states this is **guidance**, not ranking truth.

---

## Extending the system

### Swap SERP providers

Implement `SERPProvider.search()` in `src/serp.py`, then replace `PlaceholderSearchProvider` with a provider (SerpAPI, Brave, etc.).

### Improve extraction/scoring

- Replace entity heuristic with spaCy NER.
- Add better readability metrics.
- Add embeddings-based semantic clustering upgrades.

### Extend MCP tools

Keep `src/mcp_server.py` thin: add tools that call core functions and return JSON-serializable dataclasses.

---

## v1 success criteria mapping

- Accept query + draft ✅
- Inspect ranking pages from provided URLs ✅
- Produce content brief ✅
- Score draft with explainable breakdown ✅
- Generate revised draft ✅
- Improve score after at least one rewrite pass in sample flow ✅
