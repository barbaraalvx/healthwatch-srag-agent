"""Template-only report text, used when the LLM text cannot be trusted or the run was stopped."""

from srag.config import MEDICAL_DISCLAIMER

REASON_VALIDATION_FAILED = "validation_failed"
REASON_LLM_ERROR = "llm_error"

_REASON_TEXT = {
    REASON_VALIDATION_FAILED: "o texto gerado não passou nas verificações de qualidade",
    REASON_LLM_ERROR: "o serviço do modelo de linguagem não respondeu",
    "max_iterations_exceeded": "o limite de etapas do agente foi atingido",
    "max_cost_exceeded": "o limite de custo da execução foi atingido",
    "run_timeout_exceeded": "o tempo máximo da execução foi atingido",
}
_UNKNOWN_REASON = "motivo não especificado"


def fallback_text(reason: str) -> str:
    """Report text with no LLM content and no numbers, followed by the medical disclaimer."""
    cause = _REASON_TEXT.get(reason, _UNKNOWN_REASON)
    return (
        "## Resumo executivo\n"
        "A análise escrita automaticamente não foi gerada nesta execução. "
        "As métricas e os gráficos deste relatório foram calculados diretamente dos dados "
        "e continuam válidos.\n\n"
        "## Análise do cenário\n"
        f"Não há texto explicativo porque {cause}. "
        "Consulte as métricas, os gráficos e as notas metodológicas.\n\n"
        f"{MEDICAL_DISCLAIMER}\n"
    )
