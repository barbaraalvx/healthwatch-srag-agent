"""The single entry point used by the CLI and the UI: generate_report(uf) -> ReportResult."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from srag.agent.dependencies import AgentDependencies
from srag.agent.graph import AgentResult, run_agent
from srag.agent.llm import build_chat_model
from srag.audit.events import EventDetails, EventType
from srag.audit.logger import AuditLogger
from srag.audit.manifest import ManifestInfo
from srag.config import ORCHESTRATOR_PROMPT, WRITER_PROMPT, Settings, get_settings
from srag.data.repository import CaseRepository
from srag.guardrails.input import validate_request
from srag.guardrails.limits import RunLimits
from srag.news.client import NewsSearcher, TavilyNewsSearcher
from srag.report.context import ReportContext, RunDetails, build_report_context
from srag.report.pdf import PdfGenerationError, html_to_pdf
from srag.report.renderer import render_report

logger = logging.getLogger(__name__)

HTML_FILENAME = "report.html"
PDF_FILENAME = "report.pdf"
STATUS_ERROR = "error"
SERVICE_NODE = "service"
PROMPT_VERSIONS = {"orchestrator": ORCHESTRATOR_PROMPT, "writer": WRITER_PROMPT}


class DataNotPreparedError(FileNotFoundError):
    """Raised when the processed data file does not exist yet."""


@dataclass(frozen=True)
class ReportResult:
    """Where the report of one run was written and how the run ended."""

    run_id: str
    run_dir: Path
    html_path: Path
    pdf_path: Path | None
    audit_path: Path
    manifest_path: Path
    daily_chart: Path
    monthly_chart: Path
    report: ReportContext
    status: str
    stop_reason: str | None


def generate_report(
    uf: str | None = None,
    *,
    settings: Settings | None = None,
    with_pdf: bool = True,
    llm: BaseChatModel | None = None,
    searcher: NewsSearcher | None = None,
) -> ReportResult:
    """Validate the request, run the agent and write report.html, report.pdf and the manifest.

    The model and the news searcher can be passed in (tests use fakes); by default the real
    ones are built from the settings.
    """
    request = validate_request(uf)
    settings = settings or get_settings()
    _require_prepared_data(settings)
    audit = AuditLogger.create(settings.reports_dir, secrets=_secrets(settings))
    try:
        result = _run_agent(request.uf, settings, audit, llm, searcher)
    except Exception as error:
        audit.log_event(EventType.ERROR, SERVICE_NODE, EventDetails(reason=type(error).__name__))
        audit.write_manifest(_manifest_info(request.uf, settings), STATUS_ERROR)
        raise
    generated_at = datetime.now(UTC)
    context = _build_context(result, audit, settings, generated_at)
    html_path = _write_html(context, audit.run_dir)
    pdf_path = _write_pdf(html_path, audit) if with_pdf else None
    manifest_path = audit.write_manifest(
        _manifest_info(request.uf, settings, result.snapshot.reference_date), result.status
    )
    return ReportResult(
        run_id=audit.run_id,
        run_dir=audit.run_dir,
        html_path=html_path,
        pdf_path=pdf_path,
        audit_path=audit.audit_path,
        manifest_path=manifest_path,
        daily_chart=result.daily_chart,
        monthly_chart=result.monthly_chart,
        report=context,
        status=result.status,
        stop_reason=result.stop_reason,
    )


def _run_agent(
    uf: str | None,
    settings: Settings,
    audit: AuditLogger,
    llm: BaseChatModel | None,
    searcher: NewsSearcher | None,
) -> AgentResult:
    with CaseRepository(settings.data_processed_path) as repository:
        deps = AgentDependencies(
            settings=settings,
            repository=repository,
            searcher=searcher or TavilyNewsSearcher(settings),
            llm=llm or build_chat_model(settings),
            audit=audit,
            limits=RunLimits(settings),
            charts_dir=audit.run_dir / "charts",
            today=date.today(),
        )
        return run_agent(deps, uf)


def _build_context(
    result: AgentResult, audit: AuditLogger, settings: Settings, generated_at: datetime
) -> ReportContext:
    run = RunDetails(
        run_id=audit.run_id,
        generated_at=generated_at,
        model=settings.llm_model,
        effort=settings.llm_effort,
        prompt_versions=PROMPT_VERSIONS,
    )
    return build_report_context(result, run)


def _write_html(context: ReportContext, run_dir: Path) -> Path:
    html_path = run_dir / HTML_FILENAME
    html_path.write_text(render_report(context), encoding="utf-8")
    return html_path


def _write_pdf(html_path: Path, audit: AuditLogger) -> Path | None:
    """The PDF is optional: if it fails, the HTML report is still delivered and the error logged."""
    try:
        return html_to_pdf(html_path, html_path.with_name(PDF_FILENAME))
    except PdfGenerationError as error:
        logger.error("%s", error)
        audit.log_event(EventType.ERROR, "pdf", EventDetails(reason=str(error)))
        return None


def _manifest_info(
    uf: str | None, settings: Settings, data_max_date: date | None = None
) -> ManifestInfo:
    data_file = settings.data_processed_path
    return ManifestInfo(
        uf=uf,
        model=settings.llm_model,
        effort=settings.llm_effort,
        prompt_versions=PROMPT_VERSIONS,
        data_file=data_file if data_file.exists() else None,
        data_max_date=data_max_date,
    )


def _require_prepared_data(settings: Settings) -> None:
    if not settings.data_processed_path.exists():
        raise DataNotPreparedError(
            f"Processed data not found at {settings.data_processed_path}. "
            "Run: uv run python -m srag.data.prepare"
        )


def _secrets(settings: Settings) -> list[str]:
    return [
        settings.anthropic_api_key.get_secret_value(),
        settings.tavily_api_key.get_secret_value(),
    ]
