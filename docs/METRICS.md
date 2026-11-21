# Metric definitions

All metrics are computed by deterministic Python code (`src/srag/metrics/calculations.py`) from the cleaned Open DATASUS SRAG data. The LLM receives the results and only explains them.

> **Verify column names and codes against the official data dictionary** of the year file you download. The codes below follow the SRAG data dictionary used by Open DATASUS; adjust `src/srag/data/schema.py` if the dictionary differs.

## Common definitions

| Term | Definition |
|---|---|
| **Case** | One SRAG notification record with a valid symptom-onset date (`DT_SIN_PRI`). |
| **Case date** | `DT_SIN_PRI` (date of first symptoms). This is the reference date used in Brazilian epidemiological bulletins and is less affected by notification delays than `DT_NOTIFIC`. |
| **Geography** | `SG_UF` (state of residence). `uf = None` means all of Brazil. |
| **Reference date (D)** | The most recent `DT_SIN_PRI` present in the data for the selected scope. Windows are anchored on D, **not** on today's date, because the public dataset is published with a delay. |
| **Reporting lag** | Recent cases are entered into the system with a delay, so the last days are artificially low. `REPORT_LAG_DAYS` (default 7) days are excluded from the rate windows, and shown as "incomplete" in the daily chart. |
| **Current window** | 30 days ending at `D − REPORT_LAG_DAYS`. |
| **Previous window** | The 30 days immediately before the current window. |
| **Known values only** | "Ignored" (`9`) and blank values are excluded from denominators. Each rate is reported together with its **completeness** (% of records in the window with a known value). |
| **Instability flag** | If a denominator is below `MIN_DENOMINATOR` (default 30), the metric is shown with a "statistically unstable" warning. |

## 1. Case growth rate (taxa de aumento de casos)

```
growth_rate = (cases_current_window − cases_previous_window) / cases_previous_window × 100
```

- If `cases_previous_window == 0`, the rate is **undefined** (shown as "n/a", never as infinity).
- Unit: %. Positive = increase.

## 2. Mortality rate (taxa de mortalidade)

Case fatality among cases with a closed outcome, in the current window.

```
mortality_rate = deaths_by_srag / cases_with_closed_outcome × 100
deaths_by_srag            = EVOLUCAO == 2
cases_with_closed_outcome = EVOLUCAO in {1 (cure), 2 (death by SRAG), 3 (death by other causes)}
```

- Cases still open (no `EVOLUCAO`) or ignored (`9`) are excluded and reflected in completeness.
- Limitation: recent cases often have no outcome yet, so completeness may be low for the latest window.

## 3. ICU occupancy rate (taxa de ocupação de UTI) — proxy

The SRAG dataset has **no information on ICU bed capacity**, so true occupancy (occupied beds / available beds) cannot be computed from it. We report:

```
icu_admission_rate = cases_with_UTI == 1 / cases_with_UTI in {1 (yes), 2 (no)} × 100
```

Label in the report: **"Proporção de internações por SRAG que necessitaram de UTI"**, with a note explaining that it is a proxy for ICU pressure, not bed occupancy.

Possible extension (out of PoC scope): join with CNES bed data to estimate real occupancy.

## 4. Vaccination rate (taxa de vacinação) — proxy

The dataset only contains people who were hospitalized/notified with SRAG, not the whole population, so population coverage cannot be computed from it. We report:

```
covid_vaccination_rate = VACINA_COV == 1 / VACINA_COV in {1 (yes), 2 (no)} × 100
flu_vaccination_rate   = VACINA == 1     / VACINA in {1 (yes), 2 (no)}     × 100   (secondary)
```

Label in the report: **"Proporção de casos de SRAG vacinados contra COVID-19"** (and influenza), with a note explaining that this is vaccination status among cases, not population coverage.

## 5. Charts

| Chart | Definition |
|---|---|
| **Daily cases, last 30 days** | Count of cases per `DT_SIN_PRI` for the 30 days ending at D (missing days filled with 0). The last `REPORT_LAG_DAYS` days are visually marked as incomplete. |
| **Monthly cases, last 12 months** | Count of cases per calendar month for the 12 months ending in the month of D. The month of D is marked as partial if D is not the last day of the month. |

## 6. Output contract

Each metric is returned as:

```python
@dataclass(frozen=True)
class MetricResult:
    name: str              # e.g. "mortality_rate"
    value: float | None    # None when undefined
    numerator: int
    denominator: int
    completeness: float    # 0–1
    window_start: date
    window_end: date
    unstable: bool
    note: str | None       # limitation text shown in the report
```
