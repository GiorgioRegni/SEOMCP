# seo-writer-skill (prototype)

`seo-writer-skill` is a local, tool-assisted SEO writing prototype that:

1. Collects candidate competitor URLs (manual list in v1; pluggable provider abstraction).
2. Fetches and caches pages from the open web.
3. Extracts readable content and heading structure.
4. Builds a practical content brief from common patterns.
5. Analyzes a draft for coverage/structure/naturalness gaps.
6. Produces a revised draft and iterative optimization loop.
7. Exposes both a CLI and a thin MCP-compatible JSON interface.

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
- Generates a **content brief** and **rewrite guidance**.
- Runs multi-pass optimization and stores iteration logs as JSON.

## What it does **not** do

- It does **not** predict Google rankings.
- It does **not** use paid SEO APIs in v1.
- It does **not** guarantee factual correctness of source pages.
- It should **not** copy source text; it abstracts concepts.

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
- `src/fetch.py` – URL filtering, fetch, HTML metadata extraction, caching.
- `src/extract.py` – trafilatura-based readable content extraction with a BeautifulSoup fallback.
- `src/analyze.py` – competitor and draft analysis.
- `src/score.py` – transparent heuristic scoring.
- `src/brief.py` – content brief generation.
- `src/rewrite.py` – rewrite/gap-fill logic.
- `src/feedback.py` – iterative optimization loop.
- `src/mcp_server.py` – thin MCP-compatible JSON IO tool server.
- `src/browser_session.py` – optional Chrome DevTools profile launcher for authenticated browser-backed tools.
- `src/yourtextguru.py` – optional YourText.Guru scraper using the authenticated Chrome session.
- `src/models.py` – typed dataclasses.
- `src/utils.py` – helpers, cache paths, tokenization.
- `data/html`, `data/json` – local cache and reports.
- `examples/` – sample query/draft/report.

---

## CLI usage

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

### Rewrite a draft

```bash
python -m src.main rewrite --query "pickleball rules" --draft examples/draft.md --urls "https://usapickleball.org/what-is-pickleball/official-rules/"
```

### Generate a first draft from a saved brief

```bash
python3 -m src.main draft \
  --brief data/json/brief-a-pickleball-christmas.json \
  --output examples/a-pickleball-christmas-draft.md
```

### Optimize draft iteratively

```bash
python -m src.main optimize --query "pickleball rules" --draft examples/draft.md --iterations 3 --urls "https://usapickleball.org/what-is-pickleball/official-rules/"
```

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

Run server:

```bash
python -m src.mcp_server
```

Send JSON lines over stdin:

```json
{"tool":"build_seo_brief","input":{"query":"pickleball rules","urls":["https://usapickleball.org/what-is-pickleball/official-rules/"]}}
```

Authenticated browser-backed keyword service example:

```json
{"tool":"get_yourtextguru_positioned_sites","input":{"keyword":"a pickleball christmas","limit":10,"lang":"en_us","profile_dir":"data/chrome/yourtextguru"}}
```

Supported tools:

- `build_seo_brief`
- `analyze_seo_draft`
- `rewrite_seo_draft`
- `optimize_seo_draft`
- `launch_chrome_profile`
- `get_yourtextguru_positioned_sites`

All inputs/outputs are stable JSON dictionaries.

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
