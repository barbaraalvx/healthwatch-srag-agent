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
- Decision: `claude-haiku-5-5` via `langchain-anthropic`, `temperature=0`. Model name comes from `LLM_MODEL` so it can be swapped.
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
