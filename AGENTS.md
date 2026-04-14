# AGENTS.md

## Role

This repo is a local SEO guidance prototype for helping an AI or human writer produce Hugo-ready markdown articles from a target keyword. The Python CLI/MCP tools provide source filtering, briefs, scoring, QA, and writer guidance; Codex or another MCP-consuming AI is the actual content writer.

## Default Keyword-To-Hugo Workflow

1. Normalize the keyword into a slug with the project helper behavior, for example `a pickleball christmas` -> `a-pickleball-christmas`.
2. Look for an existing saved brief at `data/json/brief-<slug>.json`.
3. If no saved brief exists, build one:
   - Use user-provided URLs if available.
   - If URLs are not provided, use the configured SERP provider or `discover-serp`.
   - Prefer API-backed discovery (`brave`, `serper`, or `serpapi`) when keys are configured.
   - Use `google-chrome` only when explicitly selected or when the user accepts browser-backed Google SERP extraction.
   - Otherwise build the best available brief and clearly flag weak or missing source data.
4. Generate or update a Hugo markdown scaffold when useful:
   - Canonical final article path: `examples/<slug>.md`.
   - Working/scaffold path: `examples/working-<slug>.md`.
   - For `build-post`, pass `--working-output examples/working-<slug>.md` when overriding the default working path.
   - Do not leave rough generated scaffold as the canonical final file.
   - Use YAML front matter by default for new drafts.
5. Analyze the article:
   - `python3 -m src.main analyze --query "<keyword>" --draft examples/<slug>.md`
   - Do not repeat URLs if the saved brief exists; the CLI automatically reuses `data/json/brief-<slug>.json`.
6. Optimize when useful:
   - `python3 -m src.main optimize --query "<keyword>" --draft examples/<slug>.md --iterations 3 --output examples/working-<slug>.md`
   - Add `--update-frontmatter` only when the user wants SEO front matter suggestions applied.
7. Review the JSON outputs manually:
   - `data/json/analyze-<slug>.json`
   - `data/json/optimize-<slug>.json`
   - `data/json/guidance-<slug>.json`
   - `data/json/report-<slug>.json`
   - Treat scores as heuristic guidance, not ranking predictions.
8. Treat generated markdown as scaffolding unless it already reads like a publishable article. The tools are allowed to produce outlines, gap-filling notes, and rough revised drafts; Codex is responsible for turning that material into final copy.
9. Do an editorial synthesis pass before declaring the article finished:
   - Read the article markdown, saved brief, analyze JSON, optimize JSON, and source URL list.
   - Use the tool output as guidance, not as final prose.
   - Replace boilerplate, placeholders, and mechanical phrasing with specific, useful article copy.
   - Use weak, blocked, dynamic, or review-based source data to decide what not to overstate.
   - Write the finished Hugo-ready article to `examples/<slug>.md`.
10. If the generated `revised_draft` is weak or unchanged, edit the Hugo article directly using:
   - `score_breakdown`
   - `recommended_outline_changes`
   - `missing_topics`
   - `overused_terms`
   - `frontmatter_suggestions`
   - `source_urls`
11. When the user asks to build a post, the deliverable is the final edited Hugo markdown file, not merely the CLI-generated scaffold.
12. Run content QA before treating markdown as final:
   - `python3 -m src.main content-qa --query "<keyword>" --draft examples/<slug>.md`
   - Address scaffold text, internal metadata, noisy extracted terms, and front matter warnings before publishing.

## Stop Or Iterate Criteria

Use two gates: content QA and editorial/SEO guidance.

Content QA is the hard gate. Do not treat an article as final unless:

- `content-qa` passes.
- Hugo front matter parses.
- No scaffold phrases remain.
- No internal workflow metadata remains.
- No noisy extracted terms appear in publishable copy.
- `draft: true` is not present when the article is meant to publish.

Use scores as iteration guidance, not as a final quality grade.

Iterate again when:

- `content-qa` fails.
- Important `missing_topics`, `missing_entities`, or reader questions remain.
- The article does not satisfy the likely search intent.
- Headings miss useful sections from the guidance.
- Front matter is generic or misleading.
- Overused terms make the prose read repetitive.
- The latest optimization improves the overall score by roughly 3-5+ points without hurting prose.

Stop iterating when:

- `content-qa` passes.
- Missing topics are empty or only weak/noisy suggestions remain.
- The article answers the main reader intent directly.
- Front matter is publishable.
- The latest optimizer pass gives little or no score improvement.
- Manual reading says the article is useful, natural, and Hugo-ready.

If the score improves but the prose gets worse, reject the change. If the score is mediocre but the article is useful, accurate, and QA-clean, prefer editorial judgment over the score.

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
- Never leave instruction-like scaffold text in a final article, such as "use this section", "explain why", "add practical guidance", or generic concept lists.
- Do not include internal workflow metadata in final article copy. Failed fetches, filtered URLs, weak-source warnings, scores, optimization notes, and CLI/report details belong in JSON reports or the final response, not in the Hugo post.
- Avoid keyword stuffing.
- If a structure score is low, first check whether headings merely use different wording than the brief.
- If `recommended_outline_changes` are useful, align headings naturally instead of adding duplicate sections.
- If `overused_terms` flags a term, reduce repetition only when the prose actually reads repetitive.
- Keep the author’s voice unless there is a clear readability or intent issue.
- If results mix same-name entities, identify the target entity and keep mismatched entities only as "do not confuse with" context.

## SERP Discovery

- Manual URLs are still valid and should be used when the user supplies them.
- If URLs are missing, discover candidate sources before building the brief:
  - `python3 -m src.main discover-serp --query "<keyword>" --provider brave --top-n 10`
- Supported providers:
  - `brave` with `BRAVE_SEARCH_API_KEY`
  - `serper` with `SERPER_API_KEY`
  - `serpapi` with `SERPAPI_API_KEY`
  - `google-chrome` with a local Chrome DevTools profile
- The provider can also be selected with `SEO_WRITER_SERP_PROVIDER=brave|serper|serpapi|google-chrome`.
- If no provider is configured, ask the user for URLs or proceed with a weak-source warning.
- Chrome-backed Google extraction is a fallback, not the preferred default. It can hit consent pages, CAPTCHA, or unstable DOM changes.
- Browser profiles are local session data and must not be committed.

## Final Response Checklist

When completing a keyword-to-Hugo workflow, report:

- Brief path used or created.
- Article path edited or generated.
- Revised output path, if any.
- Final analyze/optimize score summary.
- Content QA pass/fail summary.
- Whether front matter changed.
- Any recommendations ignored and why.
- Commands run.
