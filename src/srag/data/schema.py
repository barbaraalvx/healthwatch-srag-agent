"""Columns kept from the raw SRAG files, valid code values and age bands.

Everything not listed here is dropped at ingestion (data minimization, LGPD).
Codes follow the SIVEP-Gripe data dictionary stored in docs/reference/.
"""

from datetime import date

CSV_SEPARATOR = ";"
CSV_ENCODING = "utf-8"

# Used only to drop repeated notifications; never written to the processed file.
NOTIFICATION_ID_COLUMN = "NU_NOTIFIC"

RAW_CASE_DATE = "DT_SIN_PRI"
RAW_UF = "SG_UF"
RAW_AGE_VALUE = "NU_IDADE_N"
RAW_AGE_UNIT = "TP_IDADE"

CASE_DATE = "case_date"
UF = "uf"
AGE_BAND = "age_band"
ICU = "icu"
OUTCOME = "outcome"
COVID_VACCINE = "covid_vaccine"
FLU_VACCINE = "flu_vaccine"
FINAL_CLASS = "final_class"

CODED_COLUMNS: dict[str, str] = {
    "UTI": ICU,
    "EVOLUCAO": OUTCOME,
    "VACINA_COV": COVID_VACCINE,
    "VACINA": FLU_VACCINE,
    "CLASSI_FIN": FINAL_CLASS,
}

# Any other value (including 9 = ignored and blanks) becomes missing.
VALID_CODES: dict[str, tuple[int, ...]] = {
    ICU: (1, 2),
    OUTCOME: (1, 2, 3),
    COVID_VACCINE: (1, 2),
    FLU_VACCINE: (1, 2),
    FINAL_CLASS: (1, 2, 3, 4, 5),
}

RAW_COLUMNS: tuple[str, ...] = (
    NOTIFICATION_ID_COLUMN,
    RAW_CASE_DATE,
    RAW_UF,
    RAW_AGE_VALUE,
    RAW_AGE_UNIT,
    *CODED_COLUMNS,
)

PROCESSED_COLUMNS: tuple[str, ...] = (CASE_DATE, UF, AGE_BAND, *CODED_COLUMNS.values())

AGE_UNIT_DAYS = 1
AGE_UNIT_MONTHS = 2
AGE_UNIT_YEARS = 3
MONTHS_PER_YEAR = 12
MAX_VALID_AGE_YEARS = 150

AGE_BAND_EDGES: tuple[float, ...] = (0, 5, 12, 18, 40, 60, 80, float("inf"))
AGE_BAND_LABELS: tuple[str, ...] = ("0-4", "5-11", "12-17", "18-39", "40-59", "60-79", "80+")

EARLIEST_VALID_CASE_DATE = date(2019, 1, 1)
QUALITY_REPORT_FILENAME = "quality_report.json"
