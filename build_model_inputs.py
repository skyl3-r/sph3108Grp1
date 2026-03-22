from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TEMP_FILES = [
    ROOT / "temp_data" / "raw_ave_temp_2024_dec.csv",
    ROOT / "temp_data" / "raw_ave_temp_2025_jan.csv",
    ROOT / "temp_data" / "raw_ave_temp_2025_feb.csv",
]

PRECIP_FILES = [
    ROOT / "precip_data" / "raw_precip_data_dec_2024.csv",
    ROOT / "precip_data" / "raw_precip_data_jan_2025.csv",
    ROOT / "precip_data" / "raw_precip_data_feb_2025.csv",
]

POP_GEO_FILE = ROOT / "US_pop_with_geo.csv"
VACCINATION_FILE = ROOT / "Influenza_Vaccination_Coverage_for_All_Ages_(6+_Months)_2024-25.csv"

WEATHER_OUTPUT = ROOT / "state_month_weather.csv"
VACCINATION_OUTPUT = ROOT / "state_month_vaccination.csv"

MONTH_LOOKUP = {"dec": 12, "jan": 1, "feb": 2}
EXPECTED_YEAR_MONTHS = {(2024, 12), (2025, 1), (2025, 2)}
EXCLUDED_FROM_WEATHER_MODELLING = {
    "Alaska",
    "Hawaii",
    "District of Columbia",
    "Puerto Rico",
}


def parse_weather_filename(path: Path) -> tuple[int, int]:
    parts = path.stem.split("_")
    year = next(int(part) for part in parts if part.isdigit())
    month = next(MONTH_LOOKUP[part] for part in parts if part in MONTH_LOOKUP)
    return year, month


def year_month_string(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def load_state_abbreviations() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with POP_GEO_FILE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            state = row["name"].strip()
            abbrev = row["abbrev"].strip()
            if state in mapping and mapping[state] != abbrev:
                raise ValueError(f"Conflicting abbreviation for {state}")
            mapping[state] = abbrev
    return mapping


def read_weather_file(path: Path, value_field: str) -> list[dict[str, object]]:
    year, month = parse_weather_filename(path)
    with path.open(newline="", encoding="utf-8") as handle:
        for _ in range(3):
            next(handle)
        reader = csv.DictReader(handle)
        rows = []
        seen_states: set[str] = set()
        for row in reader:
            state = row["Name"].strip()
            if state in seen_states:
                raise ValueError(f"Duplicate state {state} in {path.name}")
            seen_states.add(state)
            rows.append(
                {
                    "state": state,
                    "year": year,
                    "month": month,
                    "year_month": year_month_string(year, month),
                    value_field: float(row["Value"]),
                }
            )

    if len(rows) != 48:
        raise ValueError(f"Expected 48 rows in {path.name}, found {len(rows)}")
    return rows


def build_weather_rows(state_abbrev: dict[str, str]) -> list[dict[str, object]]:
    temp_rows = [row for path in TEMP_FILES for row in read_weather_file(path, "avg_temp_f")]
    precip_rows = [row for path in PRECIP_FILES for row in read_weather_file(path, "precip_in")]

    temp_index = {
        (row["state"], row["year"], row["month"]): row
        for row in temp_rows
    }
    precip_index = {
        (row["state"], row["year"], row["month"]): row
        for row in precip_rows
    }

    if set(temp_index) != set(precip_index):
        temp_only = sorted(set(temp_index) - set(precip_index))
        precip_only = sorted(set(precip_index) - set(temp_index))
        raise ValueError(
            f"Temperature and precipitation keys do not match. "
            f"Temp-only: {temp_only[:5]}; Precip-only: {precip_only[:5]}"
        )

    rows: list[dict[str, object]] = []
    for key in sorted(temp_index, key=lambda item: (item[1], item[2], item[0])):
        state, year, month = key
        if state not in state_abbrev:
            raise ValueError(f"State {state} missing from {POP_GEO_FILE.name}")
        rows.append(
            {
                "state": state,
                "abbrev": state_abbrev[state],
                "year": year,
                "month": month,
                "year_month": year_month_string(year, month),
                "avg_temp_f": temp_index[key]["avg_temp_f"],
                "precip_in": precip_index[key]["precip_in"],
            }
        )

    observed_year_months = {(row["year"], row["month"]) for row in rows}
    if observed_year_months != EXPECTED_YEAR_MONTHS:
        raise ValueError(f"Unexpected weather year-months: {sorted(observed_year_months)}")

    return rows


def build_vaccination_rows(
    state_abbrev: dict[str, str], weather_states: set[str]
) -> list[dict[str, object]]:
    month_to_year = {12: 2024, 1: 2025, 2: 2025}
    rows: list[dict[str, object]] = []
    seen_keys: set[tuple[str, int, int]] = set()

    with VACCINATION_FILE.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row["Vaccine"] != "Seasonal Influenza":
                continue
            if row["Geography Type"] != "States/Local Areas":
                continue
            if row["Dimension Type"] != "Age":
                continue
            if row["Dimension"] != ">=6 Months":
                continue

            month = int(row["Month"])
            if month not in month_to_year:
                continue

            state = row["Geography"].strip()
            if state not in weather_states:
                continue
            if state not in state_abbrev:
                raise ValueError(f"Vaccination geography {state} missing from {POP_GEO_FILE.name}")

            estimate = row["Estimate (%)"].strip()
            if estimate in {"", "NA", "NR †"}:
                raise ValueError(f"Missing vaccination estimate for {state}, month {month}")

            year = month_to_year[month]
            key = (state, year, month)
            if key in seen_keys:
                raise ValueError(f"Duplicate vaccination row for {state}, {year}-{month:02d}")
            seen_keys.add(key)

            rows.append(
                {
                    "state": state,
                    "abbrev": state_abbrev[state],
                    "year": year,
                    "month": month,
                    "year_month": year_month_string(year, month),
                    "vaccination_pct": float(estimate),
                }
            )

    rows.sort(key=lambda item: (item["year"], item["month"], item["state"]))

    observed_year_months = {(row["year"], row["month"]) for row in rows}
    if observed_year_months != EXPECTED_YEAR_MONTHS:
        raise ValueError(f"Unexpected vaccination year-months: {sorted(observed_year_months)}")

    return rows


def validate_weather_rows(rows: list[dict[str, object]]) -> None:
    if len(rows) != 144:
        raise ValueError(f"Expected 144 weather rows, found {len(rows)}")

    keys = {(row["state"], row["year"], row["month"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("Weather output contains duplicate state-year-month rows")

    bad_states = sorted({row["state"] for row in rows} & EXCLUDED_FROM_WEATHER_MODELLING)
    if bad_states:
        raise ValueError(f"Excluded geographies present in weather output: {bad_states}")


def validate_vaccination_rows(rows: list[dict[str, object]], weather_rows: list[dict[str, object]]) -> None:
    if len(rows) != 144:
        raise ValueError(f"Expected 144 vaccination rows, found {len(rows)}")

    keys = {(row["state"], row["year"], row["month"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("Vaccination output contains duplicate state-year-month rows")

    weather_state_keys = {(row["state"], row["abbrev"]) for row in weather_rows}
    vaccination_state_keys = {(row["state"], row["abbrev"]) for row in rows}
    if weather_state_keys != vaccination_state_keys:
        raise ValueError("Weather and vaccination state/abbrev sets do not match")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    state_abbrev = load_state_abbreviations()
    weather_rows = build_weather_rows(state_abbrev)
    validate_weather_rows(weather_rows)

    weather_states = {row["state"] for row in weather_rows}
    vaccination_rows = build_vaccination_rows(state_abbrev, weather_states)
    validate_vaccination_rows(vaccination_rows, weather_rows)

    write_csv(
        WEATHER_OUTPUT,
        weather_rows,
        ["state", "abbrev", "year", "month", "year_month", "avg_temp_f", "precip_in"],
    )
    write_csv(
        VACCINATION_OUTPUT,
        vaccination_rows,
        ["state", "abbrev", "year", "month", "year_month", "vaccination_pct"],
    )

    print(f"Wrote {len(weather_rows)} rows to {WEATHER_OUTPUT.name}")
    print(f"Wrote {len(vaccination_rows)} rows to {VACCINATION_OUTPUT.name}")


if __name__ == "__main__":
    main()
