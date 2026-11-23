# Data handling

Source: Open DATASUS, SRAG hospitalized cases (SIVEP-Gripe). Files `INFLUD25` and `INFLUD26` (extracted 2026-11-16), 194 columns and about 585,000 rows together. Data dictionary: `docs/reference/dicionario-de-dados-2019-a-2025.pdf` (version of 25/05/2023; the codes used here were checked against it and against the real values). No separate dictionary for 2026 was found; the columns and codes used were also checked directly against the `INFLUD26` file, which uses the same layout.

Raw files are never committed (`data/` is git-ignored). Run `uv run python -m srag.data.prepare` to build `data/processed/srag.parquet` and `data/processed/quality_report.json`.

## Columns kept

| Raw column | Processed column | Why |
|---|---|---|
| `DT_SIN_PRI` | `case_date` | Case date for every metric and chart (see `METRICS.md`) |
| `SG_UF` | `uf` | State scope. Values outside the 27 official UFs become missing |
| `NU_IDADE_N` + `TP_IDADE` | `age_band` | Context. The exact age is discarded; only a band is kept (0-4, 5-11, 12-17, 18-39, 40-59, 60-79, 80+) |
| `UTI` | `icu` | ICU admission proxy (1 = yes, 2 = no) |
| `EVOLUCAO` | `outcome` | Mortality (1 = cure, 2 = death by SRAG, 3 = death by other cause) |
| `VACINA_COV` | `covid_vaccine` | COVID-19 vaccination proxy (1 = yes, 2 = no) |
| `VACINA` | `flu_vaccine` | Influenza vaccination, secondary (1 = yes, 2 = no) |
| `CLASSI_FIN` | `final_class` | Causing agent for context (1 influenza, 2 other virus, 3 other agent, 4 unspecified, 5 COVID-19) |

`NU_NOTIFIC` (notification number) is read only to remove repeated notifications and is never stored.

## Columns dropped (183 of 194)

- **Direct and indirect identifiers:** birth date, names, mother's name, CPF, address, ZIP code, municipality and health region codes, health unit codes.
- **Free text** fields.
- **Not used by any metric:** symptoms, risk factors, exams, sex, race, notification date, hospital admission date and every other column. Dropping what we do not need is data minimization (LGPD) and keeps the file small (about 2 MB).

## Cleaning rules

| Rule | Detail |
|---|---|
| Repeated notifications | Dropped by `NU_NOTIFIC` |
| Case date | Parsed from ISO timestamps. Invalid dates, dates before 2019-01-01 and future dates drop the row |
| Coded columns | Only valid codes are kept. `9` (ignored), blanks and unexpected values become missing and stay out of denominators |
| Age | Days count as under 1 year, months are converted to years. Negative or over 150 becomes missing |
| UF | Invalid value becomes missing; the row still counts for Brazil |

## Results on the real data (2026-11-21 run)

- 585,334 rows read and kept: no repeated notifications, no invalid or out-of-range dates.
- Case dates from 2024-12-29 to 2026-11-15.
- Missing after cleaning: ICU 10.7%, outcome 9.4%, COVID vaccine 1.1%, flu vaccine 7.2%, final class 4.5%. Dates, UF and age band are complete.
- **Reporting lag is visible:** in Brazil, the last days before the most recent date show 222, 146, 87, 30, 4 cases per day, against 300 to 450 before. This supports excluding the last `REPORT_LAG_DAYS` from the rate windows.
- The 2025 file covers 2024-12-29 to 2026-01-03 and the 2026 file starts on 2026-01-04 (they split by epidemiological year), so both are needed for the 12-month chart.
