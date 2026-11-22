"""Streamlit interface: choose a scope, generate the report, read it, download it, audit it."""

import streamlit as st

from srag import service
from srag.config import VALID_UFS
from srag.formatting import scope_name
from srag.guardrails.input import InvalidRequestError
from srag.news.client import NewsSearchError
from srag.report.context import MetricCard
from srag.service import DataNotPreparedError, ReportResult
from srag.ui.audit_view import load_audit_table, load_manifest

RESULT_KEY = "report_result"
PRIMARY_CARDS_PER_ROW = 4
UNEXPECTED_ERROR = "A geração falhou ({kind}). Veja a trilha de auditoria da execução."
DATA_NOT_PREPARED = (
    "Os dados ainda não foram preparados. "
    "Rode `uv run python -m srag.data.prepare` e tente de novo."
)


def scope_options() -> dict[str, str | None]:
    """Label shown in the selector -> UF code (None means all of Brazil)."""
    return {scope_name(None): None, **{scope_name(uf): uf for uf in VALID_UFS}}


def generate(uf: str | None) -> None:
    """Run the report and keep the result in the session, or show a clear error."""
    try:
        with st.spinner("Gerando o relatório. Isso pode levar um minuto..."):
            st.session_state[RESULT_KEY] = service.generate_report(uf)
    except DataNotPreparedError:
        st.error(DATA_NOT_PREPARED)
    except (InvalidRequestError, NewsSearchError) as error:
        st.error(str(error))
    except Exception as error:  # the UI must never show a stack trace
        st.error(UNEXPECTED_ERROR.format(kind=type(error).__name__))


def show_metric(card: MetricCard) -> None:
    st.metric(card.title, card.value, help=card.note)
    st.caption(card.basis)
    if card.completeness:
        st.caption(f"Completude: {card.completeness}")
    if card.unstable:
        st.warning("Amostra pequena: resultado instável")


def show_report(result: ReportResult) -> None:
    report = result.report
    st.subheader(f"{report.scope}: dados até {report.reference_date}")
    if report.notice:
        st.warning(report.notice)
    st.markdown("#### Resumo executivo")
    st.markdown(report.summary_markdown)
    st.markdown("#### Métricas")
    primary = [card for card in report.cards if card.primary]
    for column, card in zip(st.columns(PRIMARY_CARDS_PER_ROW), primary, strict=False):
        with column:
            show_metric(card)
    for card in (card for card in report.cards if not card.primary):
        show_metric(card)
    st.markdown("#### Gráficos")
    st.image(str(result.daily_chart))
    st.image(str(result.monthly_chart))
    st.markdown("#### Análise do cenário")
    st.markdown(report.analysis_markdown)
    show_sources(report)
    st.caption(report.disclaimer)
    show_downloads(result)
    show_audit(result)


def show_sources(report) -> None:
    st.markdown("#### Fontes")
    if not report.sources:
        st.write("Nenhuma notícia confiável foi encontrada para esta execução.")
    for source in report.sources:
        st.markdown(f"- [{source.title}]({source.url}) ({source.source}, {source.published})")


def show_downloads(result: ReportResult) -> None:
    html_column, pdf_column = st.columns(2)
    html_column.download_button(
        "Baixar HTML", result.html_path.read_bytes(), "report.html", "text/html"
    )
    if result.pdf_path:
        pdf_column.download_button(
            "Baixar PDF", result.pdf_path.read_bytes(), "report.pdf", "application/pdf"
        )
    else:
        pdf_column.caption("O PDF não foi gerado nesta execução.")


def show_audit(result: ReportResult) -> None:
    with st.expander("Auditoria desta execução"):
        totals = load_manifest(result.manifest_path)["totals"]
        st.caption(
            f"Execução {result.run_id} · situação: {result.status} · "
            f"{totals['events']} eventos · {totals['tokens_in']} tokens de entrada · "
            f"{totals['tokens_out']} de saída · custo estimado US$ {totals['cost_usd']}"
        )
        st.dataframe(load_audit_table(result.audit_path), hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Relatório SRAG", layout="wide")
    st.title("Relatório de SRAG")
    options = scope_options()
    scope = st.selectbox("Escopo", list(options))
    if st.button("Gerar relatório", type="primary"):
        generate(options[scope])
    result = st.session_state.get(RESULT_KEY)
    if result:
        show_report(result)


main()
