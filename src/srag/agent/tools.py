"""The three fixed, read-only tools of the agent, and the executor that runs them.

The LLM that calls tools never sees news text: tool results are only counts and status lines.
The scope (UF) is fixed by the run, so the model cannot switch to another state.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from srag.agent.dependencies import AgentDependencies
from srag.agent.state import AgentState
from srag.charts.plots import daily_cases_chart, monthly_cases_chart
from srag.charts.series import build_daily_series, build_monthly_series
from srag.formatting import format_date
from srag.metrics.snapshot import compute_metrics
from srag.news.client import NewsSearchError
from srag.news.models import NewsItem
from srag.news.service import search_news

GET_METRICS = "get_metrics"
GET_CASE_SERIES = "get_case_series"
SEARCH_NEWS = "search_news"

DAILY_CHART_FILE = "daily_cases.png"
MONTHLY_CHART_FILE = "monthly_cases.png"

_NO_ARGUMENTS = {"type": "object", "properties": {}}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": GET_METRICS,
        "description": (
            "Calcula as métricas do relatório (variação de casos, mortalidade, proporção de "
            "UTI e de vacinação) para o escopo da execução. Retorna só um aviso de status."
        ),
        "input_schema": _NO_ARGUMENTS,
    },
    {
        "name": GET_CASE_SERIES,
        "description": (
            "Calcula as séries de casos (últimos 30 dias e últimos 12 meses) e gera os dois "
            "gráficos do relatório. Retorna só um aviso de status."
        ),
        "input_schema": _NO_ARGUMENTS,
    },
    {
        "name": SEARCH_NEWS,
        "description": (
            "Busca notícias recentes sobre SRAG em fontes permitidas. O escopo (Brasil ou "
            "estado) é acrescentado automaticamente. Retorna só contagens."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta curta em português, por exemplo 'SRAG casos UTI'.",
                }
            },
            "required": ["query"],
        },
    },
]


@dataclass(frozen=True)
class ToolOutcome:
    """What a tool returns to the LLM, what it changes in the state, and what is audited."""

    text: str
    updates: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def merge_news(
    existing: tuple[NewsItem, ...], new: tuple[NewsItem, ...], limit: int
) -> tuple[NewsItem, ...]:
    """Add new items after the existing ones, without repeated URLs, up to the limit."""
    merged = list(existing)
    seen = {item.url for item in existing}
    for item in new:
        if item.url not in seen:
            merged.append(item)
            seen.add(item.url)
    return tuple(merged[:limit])


class AgentTools:
    """Runs a tool by name against the shared dependencies."""

    def __init__(self, deps: AgentDependencies, uf: str | None) -> None:
        self._deps = deps
        self._uf = uf
        self._handlers: dict[str, Callable[[dict[str, Any], AgentState], ToolOutcome]] = {
            GET_METRICS: self._get_metrics,
            GET_CASE_SERIES: self._get_case_series,
            SEARCH_NEWS: self._search_news,
        }

    def run(self, name: str, args: dict[str, Any], state: AgentState) -> ToolOutcome:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolOutcome(
                f"Ferramenta desconhecida: {name}.", summary={"rejected": "unknown tool"}
            )
        return handler(args, state)

    def _get_metrics(self, args: dict[str, Any], state: AgentState) -> ToolOutcome:
        if "snapshot" in state:
            return ToolOutcome("As métricas já foram calculadas.")
        snapshot = compute_metrics(self._deps.repository, self._uf, self._deps.settings)
        reference = format_date(snapshot.reference_date)
        return ToolOutcome(
            f"Métricas calculadas ({len(snapshot.metrics)}). Data de referência: {reference}.",
            updates={"snapshot": snapshot},
            summary={"metrics": len(snapshot.metrics), "reference_date": snapshot.reference_date},
        )

    def _get_case_series(self, args: dict[str, Any], state: AgentState) -> ToolOutcome:
        if "daily_chart" in state:
            return ToolOutcome("Os gráficos já foram gerados.")
        settings, charts_dir = self._deps.settings, self._deps.charts_dir
        daily = build_daily_series(self._deps.repository, self._uf, settings)
        monthly = build_monthly_series(self._deps.repository, self._uf)
        daily_path = daily_cases_chart(daily, charts_dir / DAILY_CHART_FILE)
        monthly_path = monthly_cases_chart(monthly, charts_dir / MONTHLY_CHART_FILE)
        return ToolOutcome(
            "Séries calculadas e dois gráficos gerados (diário e mensal).",
            updates={"daily_chart": daily_path, "monthly_chart": monthly_path},
            summary={"charts": 2},
        )

    def _search_news(self, args: dict[str, Any], state: AgentState) -> ToolOutcome:
        settings = self._deps.settings
        done = state.get("searches_done", 0)
        if done >= settings.news_max_searches:
            return ToolOutcome(
                "Limite de buscas atingido. Não busque mais.", summary={"rejected": "search limit"}
            )
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return ToolOutcome("Consulta inválida: informe o parâmetro query.")
        try:
            result = search_news(query, self._uf, self._deps.searcher, settings, self._deps.today)
        except NewsSearchError as error:
            return ToolOutcome(
                "A busca de notícias falhou. Prossiga sem notícias.",
                updates={"searches_done": done + 1},
                summary={"query": query},
                error=str(error),
            )
        merged = merge_news(state.get("news_items", ()), result.items, settings.news_max_items)
        discarded = sum(result.discarded.values())
        remaining = settings.news_max_searches - done - 1
        return ToolOutcome(
            f"Busca concluída: {len(result.items)} notícias relevantes ({len(merged)} no total), "
            f"{discarded} descartadas. Buscas restantes: {remaining}.",
            updates={"news_items": merged, "searches_done": done + 1},
            summary={
                "query": result.query,
                "kept": len(result.items),
                "discarded": result.discarded,
                "sentences_removed": result.sentences_removed,
            },
        )
