"""Static PNG charts (matplotlib) built from the case series."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from matplotlib import rc_context
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from srag.charts.series import CaseSeries, SeriesPoint
from srag.config import DAILY_CHART_DAYS, MONTHLY_CHART_MONTHS

COLOR_COMPLETE = "#2f3e52"
COLOR_INCOMPLETE = "#c9a45c"
COLOR_SURFACE = "#fbf8f2"
COLOR_TEXT_PRIMARY = "#2f3e52"
COLOR_TEXT_SECONDARY = "#6b6359"
COLOR_TEXT_MUTED = "#6b6359"
COLOR_GRID = "#e6d8c6"
COLOR_BASELINE = "#c9bfae"

FONT_FAMILY = ["Segoe UI", "DejaVu Sans"]
TITLE_FONT_FAMILY = ["Georgia", "DejaVu Serif"]
FIGURE_SIZE = (8.0, 3.8)
DPI = 150
BAR_WIDTH = 0.72
DAILY_LABEL_EVERY = 5
MONTH_ABBREVIATIONS = (
    "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez",
)  # fmt: skip


@dataclass(frozen=True)
class ChartSpec:
    title: str
    incomplete_label: str
    tick_label: Callable[[SeriesPoint], str]
    label_every: int


def scope_label(uf: str | None) -> str:
    """Human-readable scope used in titles."""
    return "Brasil" if uf is None else f"UF {uf}"


def daily_cases_chart(series: CaseSeries, output_path: Path) -> Path:
    """Column chart of daily cases over the last 30 days."""
    spec = ChartSpec(
        title=f"Casos diários de SRAG nos últimos {DAILY_CHART_DAYS} dias",
        incomplete_label="Dados incompletos (atraso de notificação)",
        tick_label=lambda point: point.period_start.strftime("%d/%m"),
        label_every=DAILY_LABEL_EVERY,
    )
    return _render(series, spec, output_path)


def monthly_cases_chart(series: CaseSeries, output_path: Path) -> Path:
    """Column chart of monthly cases over the last 12 months."""
    spec = ChartSpec(
        title=f"Casos mensais de SRAG nos últimos {MONTHLY_CHART_MONTHS} meses",
        incomplete_label="Mês em andamento (dados parciais)",
        tick_label=lambda point: _month_label(point.period_start),
        label_every=1,
    )
    return _render(series, spec, output_path)


def _month_label(month_start: date) -> str:
    return f"{MONTH_ABBREVIATIONS[month_start.month - 1]}/{month_start:%y}"


def _render(series: CaseSeries, spec: ChartSpec, output_path: Path) -> Path:
    with rc_context({"font.family": "sans-serif", "font.sans-serif": FONT_FAMILY}):
        figure = Figure(figsize=FIGURE_SIZE, dpi=DPI, facecolor=COLOR_SURFACE)
        axes = figure.add_axes((0.09, 0.14, 0.89, 0.60), facecolor=COLOR_SURFACE)
        _draw_columns(axes, series.points, spec)
        _style_axes(axes)
        _add_header(figure, series, spec)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output_path, facecolor=COLOR_SURFACE)
    return output_path


def _draw_columns(axes: Axes, points: tuple[SeriesPoint, ...], spec: ChartSpec) -> None:
    positions = range(len(points))
    colors = [COLOR_INCOMPLETE if point.incomplete else COLOR_COMPLETE for point in points]
    axes.bar(positions, [point.cases for point in points], width=BAR_WIDTH, color=colors)
    ticks = [
        index for index in positions if index % spec.label_every == 0 or index == len(points) - 1
    ]
    axes.set_xticks(ticks, [spec.tick_label(points[index]) for index in ticks])
    _label_peak(axes, points)


def _label_peak(axes: Axes, points: tuple[SeriesPoint, ...]) -> None:
    peak = max(range(len(points)), key=lambda index: points[index].cases)
    axes.set_ylim(0, max(points[peak].cases * 1.15, 1))
    axes.annotate(
        _format_number(points[peak].cases),
        (peak, points[peak].cases),
        xytext=(0, 4),
        textcoords="offset points",
        ha="center",
        fontsize=8,
        color=COLOR_TEXT_PRIMARY,
    )


def _style_axes(axes: Axes) -> None:
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(COLOR_BASELINE)
    axes.yaxis.grid(True, color=COLOR_GRID, linewidth=1)
    axes.set_axisbelow(True)
    axes.tick_params(axis="both", length=0, labelsize=8, labelcolor=COLOR_TEXT_MUTED)
    axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _format_number(int(value))))


def _add_header(figure: Figure, series: CaseSeries, spec: ChartSpec) -> None:
    subtitle = f"{scope_label(series.uf)} · data de referência: {series.reference_date:%d/%m/%Y}"
    figure.text(0.02, 0.93, spec.title, fontsize=13, va="top", family=TITLE_FONT_FAMILY,
                color=COLOR_TEXT_PRIMARY)  # fmt: skip
    figure.text(0.02, 0.86, subtitle, fontsize=9, va="top", color=COLOR_TEXT_SECONDARY)
    if any(point.incomplete for point in series.points):
        handles = [Patch(color=COLOR_COMPLETE, label="Dados completos"),
                   Patch(color=COLOR_INCOMPLETE, label=spec.incomplete_label)]  # fmt: skip
        figure.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.98, 0.93),
                      frameon=False, fontsize=8, labelcolor=COLOR_TEXT_SECONDARY)  # fmt: skip


def _format_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")
