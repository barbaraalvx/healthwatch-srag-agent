# Decision log

Lightweight Architecture Decision Records. Add a new entry for every decision with real trade-offs (including prompt version changes). Never edit an accepted decision; supersede it with a new one.

Template:

```
## D-NNN — Title
- Date: YYYY-MM-DD
- Status: Accepted | Superseded by D-NNN
- Context: why a decision was needed
- Decision: what we chose
- Alternatives: what else was considered and why not
- Consequences: what this implies (good and bad)
```

---

## D-001 — Orchestration with LangGraph (tool-calling agent + deterministic guardrail nodes)
- Date: 2026-11-21
- Status: Accepted
- Context: The brief requires an orchestrator agent that uses tools (database, news) and an LLM. Evaluation weights governance and guardrails heavily.
- Decision: A LangGraph `StateGraph` where an orchestrator node (LLM with bound tools) decides which tools to call and with which arguments (e.g. refining news queries), wrapped by deterministic nodes: input validation, required-tools check, writer, output validation, rendering.
- Alternatives: (a) A pure ReAct agent: flexible but hard to audit and can skip steps. (b) A fully deterministic pipeline with one LLM call: easy to audit but does not demonstrate an agent. (c) Multi-agent supervisor: overkill for 3 tools.
- Consequences: Explicit, inspectable graph (good for the diagram and audit); agent autonomy is bounded; slightly more code than a single ReAct call.

## D-002 — LLM: Claude Haiku (paid), model configurable
- Date: 2026-11-21
- Status: Accepted
- Context: Need a reliable tool-calling model at low cost. Free tiers may use submitted data for training and have rate limits.
- Decision: `claude-haiku-5-5` via `langchain-anthropic` (no temperature: Haiku 5.5 rejects it, see D-016). Model name comes from `LLM_MODEL` so it can be swapped.
- Alternatives: Gemini free tier (zero cost, but data may be used to improve products and rate limits are opaque); GPT mini (similar price).
- Consequences: Paid usage, estimated at a fraction of a US cent per report. A spend limit is set in the Anthropic Console and `MAX_COST_USD_PER_RUN` caps each run.

## D-003 — News search: Tavily with domain allowlist
- Date: 2026-11-21
- Status: Accepted
- Context: Need real-time SRAG news at no/low cost with results usable by an LLM.
- Decision: Tavily (free plan: 1,000 credits/month), `include_domains` restricted to an allowlist of official and major news sources, filtered by recency.
- Alternatives: Serper (Google scraping, more fragile), Brave (no free plan), RSS-only (more parsing work, kept as possible extension).
- Consequences: Low cost; quality depends on allowlist; all content treated as untrusted and sanitized.

## D-004 — Storage: Parquet + DuckDB (read-only)
- Date: 2026-11-21
- Status: Accepted
- Context: The raw CSV is large, messy and slow to parse repeatedly. The brief asks the agent to "query the database".
- Decision: A one-off preparation step cleans the CSV(s) into `data/processed/srag.parquet`; tools query it through DuckDB with `read_only=True` and parameterized queries.
- Alternatives: pandas only (re-parses CSV, no "database"), SQLite (slower analytics, needs a load step), Postgres (needs a server).
- Consequences: Fast, zero-infrastructure, safe (no writes, no free SQL from the LLM).

## D-005 — PDF generation: Playwright (Chromium) instead of WeasyPrint
- Date: 2026-11-21
- Status: Accepted
- Context: Development happens on Windows, and evaluators may use any OS. WeasyPrint requires native GTK/Pango libraries, which are error-prone to install on Windows.
- Decision: Render HTML with Jinja2 and print to PDF with Playwright's headless Chromium.
- Alternatives: WeasyPrint (lighter, but native deps on Windows); ReportLab/fpdf2 (draw PDF by hand, much more code).
- Consequences: One extra setup command (`playwright install chromium`, ~150 MB download); identical rendering across OSes; HTML and PDF share one template.

## D-006 — Environment management: uv
- Date: 2026-11-21
- Status: Accepted
- Decision: `uv` with `pyproject.toml` and a committed `uv.lock` for reproducible installs.
- Alternatives: pip + venv (no lockfile by default), Poetry (slower).

## D-007 — Interfaces: CLI and Streamlit over one service function
- Date: 2026-11-21
- Status: Accepted
- Decision: `srag.service.generate_report(uf)` holds all logic; `python -m srag` and the Streamlit app are thin adapters.
- Consequences: No duplicated logic; tests target the service; the Streamlit app also exposes the audit trail for transparency.

## D-008 — Scope: Brazil and per state
- Date: 2026-11-21
- Status: Accepted
- Decision: Optional `uf` parameter (state of residence, `SG_UF`). `None` = Brazil. Only the 27 valid UF codes are accepted.
- Consequences: Small states may have unstable rates; flagged via `MIN_DENOMINATOR`. News queries include the state name when `uf` is set.

## D-009 — Time windows: 30 vs previous 30 days, anchored on the data's latest date, with reporting lag
- Date: 2026-11-21
- Status: Accepted
- Context: The public dataset is published with a delay, and the most recent days are under-reported.
- Decision: Anchor on the latest `DT_SIN_PRI` in the data (D); exclude the last `REPORT_LAG_DAYS` (default 7) from rate windows; mark them as incomplete in charts. See `docs/METRICS.md`.
- Consequences: Rates are less biased toward false declines; the report states the reference date explicitly.

## D-010 — ICU and vaccination metrics as documented proxies
- Date: 2026-11-21
- Status: Accepted
- Context: The dataset has no ICU bed capacity and no population denominator.
- Decision: Report ICU admission proportion among SRAG cases and vaccination proportion among SRAG cases, clearly labelled as proxies in the report and README.
- Alternatives: Join external sources (CNES beds, vaccination coverage APIs): more accurate but out of PoC scope; listed as future work.

## D-011 — Data minimization: nine columns kept, ignored codes become missing, dedupe by notification number
- Date: 2026-11-21
- Status: Accepted
- Context: The raw files have 194 columns (about 585,000 rows for 2025 + 2026), most of them identifying or unused. Real data has ignored codes (9), blanks and invalid values.
- Decision: Keep only `DT_SIN_PRI`, `SG_UF`, age (turned into an age band), `UTI`, `EVOLUCAO`, `VACINA_COV`, `VACINA` and `CLASSI_FIN`. `NU_NOTIFIC` is read only to drop repeated notifications and is never stored. Code 9, blanks and unexpected values become missing, so they stay out of denominators (completeness is reported, see `docs/METRICS.md`). Dates outside 2019-01-01 .. run date are dropped. Details in `docs/DATA.md`.
- Alternatives: Keep `DT_NOTIFIC`, `CS_SEXO`, `HOSPITAL` as the plan suggested (not used by any metric, so dropping them is safer). De-duplicate on whole rows (wrongly removes different patients that look alike: about 700 look-alike rows were found in an exploration with 18 columns, while `NU_NOTIFIC` has zero repeats).
- Consequences: Smaller, safer file (about 2 MB). Adding a new metric that needs another column requires changing `data/schema.py` and re-running the preparation.

## D-012 — DuckDB: in-memory table with file access disabled and locked configuration (refines D-004)
- Date: 2026-11-21
- Status: Accepted
- Context: D-004 planned `read_only=True`, but that option only applies to `.duckdb` database files, and our source is a Parquet file.
- Decision: Load the Parquet into an in-memory table, then run `SET enable_external_access = false` and `SET lock_configuration = true`. Queries are fixed and parameterized.
- Alternatives: Write a `.duckdb` file in the preparation step and open it with `read_only=True` (one more artifact to keep in sync).
- Consequences: The connection cannot read or write any file nor change its own settings (covered by a test). The whole table (about 600,000 rows, 2 MB) lives in memory, which is fine for this size.

## D-013 — News: cheapest Tavily search, strict sanitization, dated results only
- Date: 2026-11-21
- Status: Accepted (search topic, date rule and result counts superseded by D-014)
- Context: News is third-party text that goes to an LLM, and every Tavily search spends credits (free plan: 1,000 per month). Cost and prompt injection are the two main risks.
- Decision: One `basic` search (1 credit) with `topic=news`, `days=NEWS_DAYS`, `max_results=NEWS_MAX_RESULTS`, only allowlisted domains, with no generated answer, raw content or images. The sanitizer re-checks everything the provider returns: the host must be an allowed domain or one of its subdomains (look-alikes such as `evilgov.br` are rejected), the URL must be plain http(s), the publication date must be readable and inside the window (results without a date are discarded, because the report must state when each source was published), markup and control characters are removed, text is truncated, and sentences that look like instructions to the model are removed (a title that looks like one discards the whole result). Results are shown to the LLM inside an `<untrusted_news>` block; since tags are stripped from the text, content cannot close the block early.
- Relevance (added after the first real search): the manual test returned five BBC items, none about SRAG (a burial, Brazilian politics, bird flu in Northern Ireland, a Kennedy lawsuit), because the allowlist and the news topic limit what the provider can return and the provider does not guarantee relevance. A deterministic filter now requires a respiratory-disease term in the title or snippet, and international sources (`bbc.com`, `paho.org`, `who.int`) must also mention Brazil or the selected state. National sources are assumed Brazilian.
- Alternatives: `advanced` depth (more relevant snippets, higher cost per search); keeping results with no date (cannot cite when it was published); asking an LLM to detect injection (extra cost and the detector can itself be tricked).
- Consequences: Predictable cost (1 credit per search). The injection filter is a list of patterns, so it is a heuristic and will miss new wordings. It is one layer among several: the system prompt says to ignore instructions found in news, the model has no tool that can act on them, and the output guardrail checks that cited URLs and numbers come from retrieved data. If nothing trustworthy is found, the tool returns an empty list and the report says so.

## D-014 — News: general topic, undated results accepted, 10 fetched and 5 sent to the LLM
- Date: 2026-11-21
- Status: Accepted
- Context: Two real searches (1 credit each, same query) compared the Tavily topics. `news` returned 5 items, all from `bbc.com` and none about SRAG, but with publication dates. `general` returned 10 items from the sources we want (Fiocruz InfoGripe bulletins, Agência Brasil, CNN Brasil, gov.br, a city health department) and all about SRAG, but with no publication date at all.
- Decision: Search with `topic=general` and `time_range` derived from `NEWS_DAYS` (day, week, month or year), still `basic` depth and allowlisted domains only. Results without a readable date are kept with `published_at = None` and shown as "data não informada" (the report says the search was limited to the recent period). A date that is present is still checked against the window. Fetch `NEWS_MAX_RESULTS` (default 10) and send at most `NEWS_MAX_ITEMS` (default 5) relevant items to the LLM, so a larger pool improves the chance of relevant news without raising the model cost.
- Alternatives: Keep `news` and require dates (returned no usable news); try to read dates from URLs or page text (fragile, and one more thing to trust); fetch full pages to find dates (costs more credits and sends more third-party text through the system).
- Consequences: Better sources and relevance. The recency of an undated item rests on the provider's period filter, which we cannot verify, so the report must not describe undated items as "published on" a date. The relevance filter from D-013 stays essential. The user's `.env` must set `NEWS_MAX_RESULTS=10` if it still has the old value.

## D-015 — Audit trail and output guardrail: what is checked, and what is not
- Date: 2026-11-21
- Status: Accepted
- Context: Governance and guardrails are evaluation criteria, and they must exist before the agent so it is audited from its first run.
- Decision: Each run has a UUID4 `run_id` and a folder `reports/<UTC timestamp>_<run_id>/` with `audit.jsonl` (one sanitized JSON event per line) and `manifest.json` (scope, model, prompt versions, SHA-256 of the data file, latest case date, git commit, final status, token and cost totals). Everything written passes a sanitizer that removes the configured API keys, key-shaped strings and fields named like secrets, and truncates long text and lists. Run limits (iterations, cost, wall-clock time) raise `LimitExceededError` with a reason that the caller records. The output guardrail checks the LLM text for: numbers (percentages and counts must match a computed value within `NUMBER_TOLERANCE` = 0.1 points, or appear exactly in the retrieved news), cited URLs (must be retrieved URLs), required sections, the medical disclaimer, and CPF, e-mail and phone patterns. Numbers inside dates, URLs, codes such as COVID-19, list markers and citation markers are not checked. A text number may drop the sign (a decrease can be written "queda de 14,4%").
- Not checked (known limits): dates written in the text are not verified against the data windows; the direction of a change (up or down) is not verified; medical advice written in free text is not detected; a number that coincidentally equals another computed value passes. The writer prompt must ask for pt-BR format with one decimal place, because rounding to an integer can fall outside the tolerance. The disclaimer is fixed text appended by code before validation, so this check guards against removing it, not against the model forgetting it.
- Alternatives: Asking an LLM to judge the text (extra cost, and the judge can be wrong); exact number matching (rejects normal rounding); logging raw inputs for debugging (risks secrets and sensitive data in logs).
- Consequences: Deterministic checks that cost nothing per run and are fully unit tested (including deliberate-breakage checks). The 0.1 tolerance may reject some correct but loosely rounded texts, which triggers the single retry with feedback described in `CLAUDE.md`.

## D-016 - Agent design: fixed scope, tool-calling model never sees news text, cost-first routing
- Date: 2026-11-21
- Status: Accepted (supersedes the temperature part of D-002)
- Context: Phase 7 connects the LLM to the tools. The risks are prompt injection through news, the model changing the scope, runaway loops and cost.
- Decision:
  - Graph: `orchestrator <-> tools -> required_tools_check -> writer -> output_guardrail`, with one retry of the writer (feedback = the guardrail errors) and a template-only `fallback` after the second failure. A run stopped by a limit (iterations, cost, time) or by a model-provider error skips to the same fallback and is marked `stopped` with the reason. Metrics and charts are always produced by code, so even a stopped run returns them.
  - The scope (UF) is fixed by the run. Tool schemas have no `uf` field, and any `uf` the model sends is ignored.
  - The model that calls tools only receives counts and status lines. News text goes only to the writer, which has no tools, inside the `<untrusted_news>` block.
  - If metrics, charts and news are all collected after the first tool round, the second orchestrator call is skipped (one LLM call less). If no news was found, the orchestrator may refine the query, within `NEWS_MAX_SEARCHES` (default 2, one Tavily credit each).
  - The writer receives only aggregated values already formatted in pt-BR (one decimal, comma), the windows, the limitation notes and the news block. The medical disclaimer is appended by code before validation.
  - Claude Haiku 5.5 rejects non-default sampling parameters, so the temperature setting was removed. Reasoning effort is configurable (`LLM_EFFORT`, default `low`) and recorded in the manifest. Thinking tokens are billed as output, so the cost is computed from the output token count reported by the API. No tool choice is forced (also not accepted by the newer models).
  - Prompts are versioned files (`orchestrator_v1.md`, `writer_v1.md`); their names are recorded in each `llm_call` audit event.
- Alternatives: A plain ReAct loop with the model choosing everything (harder to audit, can skip required steps); giving the orchestrator the news titles to judge relevance (a larger injection surface for the model that has tools); letting the model pick the UF (can drift to another state); always running a second orchestrator turn (one more paid call in the common case).
- Consequences: A typical run costs two model calls (orchestrator and writer) and one news search. A refinement or a writer retry adds one call. The fixed scope means a question about two states needs two runs. The writer output is only as good as its prompt: the tolerance of 0.1 points in the output guardrail means it must copy the numbers as given, which the prompt demands. In the first real run a draft hit the 2,000-token cap in the middle of a link (reasoning tokens count as output). A draft that stopped because of the token limit is now rejected with an explicit reason and rewritten shorter, and the default cap is 4,000 tokens.

## D-017 - Report rendering: safe Markdown, standalone HTML, optional PDF
- Date: 2026-11-22
- Status: Accepted
- Context: Phase 8 turns the agent result into HTML and PDF. The LLM text and the news titles are untrusted, and an evaluator must be able to open the report on its own.
- Decision:
  - The writer text stays Markdown. It is split by its `##` headings and converted with `markdown-it-py` with raw HTML disabled (so `<script>` is escaped and `javascript:` links are refused). Everything else in the Jinja2 template is auto-escaped.
  - The medical disclaimer is removed from the text body and shown once, in the footer, from the same constant the guardrail checks.
  - Charts are embedded as base64, so `report.html` works alone. The PDF is made from that HTML with headless Chromium (Playwright), A4.
  - The PDF is optional: if Chromium is missing or fails, the HTML report is still delivered, the error is written to the audit log and `pdf_path` is `None`.
  - `generate_report(uf)` creates the run folder only after the request is validated. If the run fails, the error is audited and the manifest is written with status `error` before the exception is re-raised.
  - A fallback or stopped run still produces the full report (metrics, charts, notes, sources) with a visible notice that the automatic text is unavailable.
  - The methodology notes are fixed text (a summary of `docs/METRICS.md`), not written by the model.
- Alternatives: A hand-written Markdown converter (more code and easier to get wrong); letting the model write HTML (injection risk and harder to validate); WeasyPrint for the PDF (needs system libraries that are hard to install on Windows).
- Consequences: Chromium (about 120 MB) must be installed once with `uv run playwright install chromium`; CI installs it too. The report page is the only place with the full text, so the Streamlit UI (Phase 9) will reuse the same `ReportResult`.
- Design (2026-11-22): the page is a cream "paper" panel floating over an inline SVG woodblock-style scene (moon, cherry branches, pagoda, waves, carp); the scene is hidden when printing. Palette of muted earth tones (navy `#2F3E52`, gold `#C9A45C`, sand, blue-grey, rose), serif titles and sans-serif body. The dashboard layout of the brief was adapted to a report: sidebar = section index, period box = analysis window, four KPI cards (the last one inverted, with the secondary flu proxy inside it), the two charts, a metrics table with stable/small-sample tags, and quick links to the PDF, the audit trail and the manifest. The charts use the same palette. Fonts are system stacks (no network), so the page works offline.

## D-018 - Interfaces: CLI and Streamlit as thin layers over one service function
- Date: 2026-11-22
- Status: Accepted
- Context: Phase 9 adds a command line and a web UI. Both must behave the same and neither may hold business logic.
- Decision:
  - Both call only `service.generate_report(uf)`. The result (`ReportResult`) carries the file paths, the chart files and the `ReportContext` (formatted metrics, text, sources), so the UI never parses the HTML.
  - CLI (`python -m srag --uf SP --no-pdf --output-dir DIR`): expected problems (invalid UF, data not prepared, no cases, news search error) print one `error:` line with exit code 2 (invalid request) or 1, never a stack trace. Any other failure prints one line with the exception type only (the details stay in the audit log or at `LOG_LEVEL=DEBUG`), so internal messages do not leak.
  - A missing `data/processed/srag.parquet` is detected before the run folder is created (`DataNotPreparedError`, with the command to fix it).
  - Streamlit: scope selector (Brazil and 27 UFs), a button that runs the report only on click (the model and news are paid calls), metrics with `st.metric`, charts, text, sources, HTML and PDF downloads, and an expander "Auditoria desta execucao" with the `audit.jsonl` events as a table plus the manifest totals. The text is shown with `st.markdown` (no unsafe HTML). The server listens on `localhost` only (`.streamlit/config.toml`), so the PoC is not exposed to the network by default.
  - The CLI messages are in English (developer tool); the UI is in pt-BR.
- Alternatives: Business logic inside the UI (not testable, drifts from the CLI); the UI reading `report.html` (fragile); running the report on every Streamlit rerun (would spend money on each widget click).
- Consequences: The UI keeps the last result in the session, so download buttons do not trigger a new run. The UI is tested with Streamlit's `AppTest` and the same fake model and searcher as the service.
