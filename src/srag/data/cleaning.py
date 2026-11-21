"""Pure functions that turn the raw SRAG table into the cleaned, de-identified table."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from srag.config import VALID_UFS
from srag.data import schema

DROPPED_DUPLICATE = "duplicate_notification"
DROPPED_INVALID_DATE = "invalid_case_date"
DROPPED_DATE_OUT_OF_RANGE = "case_date_out_of_range"


@dataclass(frozen=True)
class CleaningResult:
    cases: pd.DataFrame
    rows_read: int
    dropped: dict[str, int]


def parse_case_dates(raw: pd.Series) -> pd.Series:
    """Parse ISO timestamps to midnight dates; unparseable values become missing."""
    parsed = pd.to_datetime(raw, errors="coerce", utc=True)
    return parsed.dt.tz_localize(None).dt.normalize()


def to_known_code(raw: pd.Series, valid_codes: tuple[int, ...]) -> pd.Series:
    """Keep only valid codes; ignored (9), blank and unexpected values become missing."""
    numeric = pd.to_numeric(raw, errors="coerce")
    return numeric.where(numeric.isin(valid_codes)).astype("Int8")


def validate_uf(raw: pd.Series) -> pd.Series:
    """Keep only the 27 official UF codes."""
    return raw.where(raw.isin(VALID_UFS))


def to_age_band(value: pd.Series, unit: pd.Series) -> pd.Series:
    """Convert age (days, months or years) into an age band; the exact age is discarded."""
    age = pd.to_numeric(value, errors="coerce")
    age_unit = pd.to_numeric(unit, errors="coerce")
    years = age.where(age_unit == schema.AGE_UNIT_YEARS)
    years = years.mask(age_unit == schema.AGE_UNIT_MONTHS, age // schema.MONTHS_PER_YEAR)
    years = years.mask(age_unit == schema.AGE_UNIT_DAYS, 0)
    years = years.where(years.between(0, schema.MAX_VALID_AGE_YEARS))
    bands = pd.cut(
        years,
        bins=list(schema.AGE_BAND_EDGES),
        labels=list(schema.AGE_BAND_LABELS),
        right=False,
    )
    return bands.astype("string")


def clean(raw: pd.DataFrame, today: date) -> CleaningResult:
    """Drop repeated notifications and invalid dates, then keep only de-identified columns."""
    unique = raw.drop_duplicates(schema.NOTIFICATION_ID_COLUMN)
    dates = parse_case_dates(unique[schema.RAW_CASE_DATE])
    in_range = dates.between(pd.Timestamp(schema.EARLIEST_VALID_CASE_DATE), pd.Timestamp(today))
    kept = unique.loc[in_range]
    dropped = {
        DROPPED_DUPLICATE: len(raw) - len(unique),
        DROPPED_INVALID_DATE: int(dates.isna().sum()),
        DROPPED_DATE_OUT_OF_RANGE: int((~in_range & dates.notna()).sum()),
    }
    return CleaningResult(_build_cases(kept, dates[in_range]), len(raw), dropped)


def _build_cases(kept: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    coded = {
        new: to_known_code(kept[raw], schema.VALID_CODES[new])
        for raw, new in schema.CODED_COLUMNS.items()
    }
    cases = pd.DataFrame(
        {
            schema.CASE_DATE: dates,
            schema.UF: validate_uf(kept[schema.RAW_UF]),
            schema.AGE_BAND: to_age_band(kept[schema.RAW_AGE_VALUE], kept[schema.RAW_AGE_UNIT]),
            **coded,
        }
    )
    return cases.reset_index(drop=True)
