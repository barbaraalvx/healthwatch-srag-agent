# healthwatch-srag-agent

Agentic AI that generates automated SRAG (Severe Acute Respiratory Syndrome) outbreak reports from Brazil's Open DATASUS data, combining key metrics, charts and real-time news context. Built with LangGraph, with audit logging and guardrails.

> Proof of Concept for Indicium HealthCare Inc. The report is informational and **does not replace medical or public-health guidance**.

<!-- TODO (Phase 11): add a screenshot of a generated report here -->

## Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Metrics](#metrics)
4. [Quickstart](#quickstart)
5. [Usage](#usage)
6. [Governance and transparency](#governance-and-transparency)
7. [Guardrails](#guardrails)
8. [Sensitive data handling](#sensitive-data-handling)
9. [Project structure](#project-structure)
10. [Testing and code quality](#testing-and-code-quality)
11. [Limitations and future work](#limitations-and-future-work)
12. [Decisions](#decisions)

## Overview

Given a scope (all of Brazil or one state), the agent:

1. Computes four metrics from the Open DATASUS SRAG dataset: case growth rate, mortality rate, ICU admission proportion (ICU occupancy proxy) and vaccination proportion among cases (vaccination proxy).
2. Builds two charts: daily cases (last 30 days) and monthly cases (last 12 months).
3. Searches recent SRAG news from trusted sources.
4. Uses an LLM to explain the scenario, grounded only on the computed metrics and the retrieved news, with citations.
5. Produces `report.html` and `report.pdf`, plus a full audit trail of the run.

## Architecture

<!-- TODO (Phase 10): embed a PNG export of the diagram here (GitHub does not render PDFs inline) -->

- Conceptual diagram: [`docs/architecture.pdf`](docs/architecture.pdf) (source: [`docs/architecture.mmd`](docs/architecture.mmd))
- <!-- TODO (Phase 11): short description of each component and the graph flow -->

## Metrics

Formulas, windows and limitations: [`docs/METRICS.md`](docs/METRICS.md).

| Metric | Definition (short) |
|---|---|
| Case growth rate | Cases in the last 30 days vs the previous 30 days (excluding the reporting-lag days) |
| Mortality rate | SRAG deaths / cases with a closed outcome |
| ICU occupancy (proxy) | Share of SRAG cases admitted to ICU (the dataset has no bed capacity) |
| Vaccination (proxy) | Share of SRAG cases vaccinated (the dataset has no population denominator) |

## Quickstart

<!-- TODO (Phase 11): verify every command on a clean machine -->

Requirements: Python 3.12 (installed by uv), [uv](https://docs.astral.sh/uv/), an Anthropic API key and a Tavily API key.

```bash
git clone https://github.com/<your-user>/healthwatch-srag-agent.git
cd healthwatch-srag-agent
uv sync
uv run playwright install chromium
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
# edit .env and fill ANTHROPIC_API_KEY and TAVILY_API_KEY
```

Data: download the SRAG CSV file(s) from [Open DATASUS](https://opendatasus.saude.gov.br/dataset/srag-2021-a-2024) into `data/raw/`, then:

```bash
uv run python -m srag.data.prepare
```

## Usage

```bash
uv run python -m srag              # Brazil
uv run python -m srag --uf SP      # one state
uv run streamlit run src/srag/ui/streamlit_app.py
```

Outputs are written to `reports/<timestamp>_<run_id>/`. A sample is in [`docs/sample_report/`](docs/sample_report/).

## Governance and transparency

<!-- TODO (Phase 6/11): describe audit.jsonl events, manifest.json fields, and how to inspect a run -->

## Guardrails

<!-- TODO (Phase 6/11): table of guardrails (input, tools, news, agent limits, output) and what happens on failure -->

## Sensitive data handling

<!-- TODO (Phase 2/11): columns kept vs dropped and why; aggregates-only policy; secrets; LGPD -->

## Project structure

<!-- TODO (Phase 11): final tree -->

## Testing and code quality

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests use synthetic fixtures and fake LLM/news clients, so they run without the dataset or API keys. CI runs on every push.

## Limitations and future work

- ICU and vaccination metrics are proxies (see [`docs/METRICS.md`](docs/METRICS.md)).
- The public dataset is published with a delay; the report states its reference date.
- <!-- TODO: add limitations found during development -->

## Decisions

All architecture and design decisions are recorded in [`docs/DECISIONS.md`](docs/DECISIONS.md).
