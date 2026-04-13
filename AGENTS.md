# AGENTS.md

## Role

This repo is a local SEO writing prototype for producing Hugo-ready markdown articles from a target keyword. When the user gives a keyword and asks for a post, guide, draft, optimization, or review, run the full SEO writing workflow unless they explicitly ask for only one step.

## Default Keyword-To-Hugo Workflow

1. Normalize the keyword into a slug with the project helper behavior, for example `a pickleball christmas` -> `a-pickleball-christmas`.
2. Look for an existing saved brief at `data/json/brief-<slug>.json`.
3. If no saved brief exists, build one:
   - Use user-provided URLs if available.
   - If URLs are not provided and a browser-authenticated keyword source is relevant, use the Chrome/YourText.Guru workflow documented in `README.md`.
   - Otherwise build the best available brief and clearly flag weak or missing source data.
4. Generate or update a Hugo markdown draft:
   - Default article path: `examples/<slug>.md`.
   - If preserving an original article for review, write revised output to `examples/revised-<slug>.md`.
   - Use YAML front matter by default for new drafts.
5. Analyze the article:
   - `python3 -m src.main analyze --query "<keyword>" --draft examples/<slug>.md`
   - Do not repeat URLs if the saved brief exists; the CLI automatically reuses `data/json/brief-<slug>.json`.
6. Optimize when useful:
   - `python3 -m src.main optimize --query "<keyword>" --draft examples/<slug>.md --iterations 3 --output examples/revised-<slug>.md`
   - Add `--update-frontmatter` only when the user wants SEO front matter suggestions applied.
7. Review the JSON outputs manually:
   - `data/json/analyze-<slug>.json`
   - `data/json/optimize-<slug>.json`
   - Treat scores as heuristic guidance, not ranking predictions.
8. If the generated `revised_draft` is weak or unchanged, edit the Hugo article directly using:
   - `score_breakdown`
   - `recommended_outline_changes`
   - `missing_topics`
   - `overused_terms`
   - `frontmatter_suggestions`
   - `source_urls`

## Hugo Front Matter Rules

- Preserve Hugo front matter and custom fields by default.
- YAML (`---`) and TOML (`+++`) front matter are supported.
- Analysis, rewrite, and optimize should operate on markdown body content, not front matter text.
- Only update these fields when explicitly requested or clearly useful:
  - `title`
  - `description`
  - `tags`
  - `draft`
- Never remove or rewrite unrelated Hugo fields such as:
  - `slug`
  - `date`
  - `lastmod`
  - `categories`
  - `faqs`
  - `aliases`
  - `type`
  - `layout`
  - custom params
- Do not set `draft: true` on an article that appears intended for publication unless the user explicitly asks.

## Editorial Rules

- Use competitor/source pages for abstraction, not copying.
- Do not paste large spans from source pages.
- Prefer reader usefulness over chasing the score.
- Avoid keyword stuffing.
- If a structure score is low, first check whether headings merely use different wording than the brief.
- If `recommended_outline_changes` are useful, align headings naturally instead of adding duplicate sections.
- If `overused_terms` flags a term, reduce repetition only when the prose actually reads repetitive.
- Keep the author’s voice unless there is a clear readability or intent issue.

## Browser-Backed Keyword Sources

- Use browser-backed scraping only for authenticated tools such as YourText.Guru.
- Launch Chrome with a persistent local profile:
  - `python3 -m src.main launch-chrome-profile --profile-dir data/chrome/yourtextguru --start-url "https://yourtext.guru/login"`
- After login, scrape positioned sites:
  - `python3 -m src.main yourtextguru-positioned-sites --keyword "<keyword>" --limit 10 --lang en_us --profile-dir data/chrome/yourtextguru`
- The Chrome profile is local session data and must not be committed.
- Do not bypass login or authentication controls.

## Final Response Checklist

When completing a keyword-to-Hugo workflow, report:

- Brief path used or created.
- Article path edited or generated.
- Revised output path, if any.
- Final analyze/optimize score summary.
- Whether front matter changed.
- Any recommendations ignored and why.
- Commands run.
