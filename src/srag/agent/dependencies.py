"""Everything the agent needs from the outside world, passed in so tests can fake it."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from srag.audit.logger import AuditLogger
from srag.config import Settings
from srag.data.repository import CaseRepository
from srag.guardrails.limits import RunLimits
from srag.news.client import NewsSearcher


@dataclass(frozen=True)
class AgentDependencies:
    settings: Settings
    repository: CaseRepository
    searcher: NewsSearcher
    llm: BaseChatModel
    audit: AuditLogger
    limits: RunLimits
    charts_dir: Path
    today: date
