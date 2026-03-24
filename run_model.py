from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from pathlib import Path

from US_plot import generate_infection_maps


ROOT = Path(__file__).resolve().parent
SEED_STATE = "LA"
BETA = 15000000
RANDOM_SEED = 3780
MONTHS = ["2024-12", "2025-01", "2025-02"]
OUTPUT_DIR = ROOT / "outputs"

POPULATION_FILE = ROOT / "US_pop_with_geo.csv"
WEATHER_FILE = ROOT / "state_month_weather.csv"
VACCINATION_FILE = ROOT / "state_month_vaccination.csv"
FLIGHT_FILE = ROOT / "flight_data" / "state_flight_freq_final.csv"

EXCLUDED_ABBREVS = {"AK", "HI", "DC", "PR"}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a_value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(min(1.0, math.sqrt(a_value)))


def load_population_rows() -> dict[str, dict[str, object]]:
    rows = read_csv_rows(POPULATION_FILE)
    population_rows: dict[str, dict[str, object]] = {}
    for row in rows:
        abbrev = row["abbrev"]
        population_rows[abbrev] = {
            "state": row["name"],
            "abbrev": abbrev,
            "population": int(row["population"]),
            "population_normalized": float(row["population_normalized"]),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
        }
    return population_rows


def load_monthly_covariates() -> tuple[dict[tuple[str, str], dict[str, object]], dict[tuple[str, str], dict[str, object]]]:
    weather_rows = {}
    for row in read_csv_rows(WEATHER_FILE):
        key = (row["abbrev"], row["year_month"])
        weather_rows[key] = {
            "state": row["state"],
            "abbrev": row["abbrev"],
            "year_month": row["year_month"],
            "avg_temp_f": float(row["avg_temp_f"]),
            "precip_in": float(row["precip_in"]),
        }

    vaccination_rows = {}
    for row in read_csv_rows(VACCINATION_FILE):
        key = (row["abbrev"], row["year_month"])
        vaccination_rows[key] = {
            "state": row["state"],
            "abbrev": row["abbrev"],
            "year_month": row["year_month"],
            "vaccination_pct": float(row["vaccination_pct"]),
        }

    return weather_rows, vaccination_rows


def build_model_states(
    population_rows: dict[str, dict[str, object]],
    weather_rows: dict[tuple[str, str], dict[str, object]],
    vaccination_rows: dict[tuple[str, str], dict[str, object]],
) -> list[str]:
    required_months = set(MONTHS)
    weather_months_by_state: dict[str, set[str]] = defaultdict(set)
    vaccination_months_by_state: dict[str, set[str]] = defaultdict(set)

    for abbrev, year_month in weather_rows:
        weather_months_by_state[abbrev].add(year_month)
    for abbrev, year_month in vaccination_rows:
        vaccination_months_by_state[abbrev].add(year_month)

    model_states = sorted(
        abbrev
        for abbrev in weather_months_by_state
        if abbrev not in EXCLUDED_ABBREVS
        and abbrev in population_rows
        and weather_months_by_state[abbrev] == required_months
        and vaccination_months_by_state.get(abbrev) == required_months
    )

    if len(model_states) != 48:
        raise ValueError(f"Expected 48 contiguous model states, found {len(model_states)}")

    return model_states


def build_distance_lookup(
    model_states: list[str],
    population_rows: dict[str, dict[str, object]],
) -> dict[tuple[str, str], float]:
    distance_lookup: dict[tuple[str, str], float] = {}
    for origin_abbrev in model_states:
        origin = population_rows[origin_abbrev]
        for dest_abbrev in model_states:
            if origin_abbrev == dest_abbrev:
                continue
            dest = population_rows[dest_abbrev]
            distance_lookup[(origin_abbrev, dest_abbrev)] = haversine_km(
                origin["latitude"],
                origin["longitude"],
                dest["latitude"],
                dest["longitude"],
            )
    return distance_lookup


def build_monthly_flights(model_states: list[str]) -> dict[str, list[dict[str, object]]]:
    flights_by_month: dict[str, list[dict[str, object]]] = {year_month: [] for year_month in MONTHS}
    rows = read_csv_rows(FLIGHT_FILE)

    raw_flights: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        year_month = f"{int(row['YEAR']):04d}-{int(row['MONTH']):02d}"
        origin_abbrev = row["ORIGIN_STATE_ABR"]
        dest_abbrev = row["DEST_STATE_ABR"]
        if year_month not in flights_by_month:
            continue
        if origin_abbrev not in model_states or dest_abbrev not in model_states:
            continue
        if origin_abbrev == dest_abbrev:
            continue

        raw_flights[year_month].append(
            {
                "origin_abbrev": origin_abbrev,
                "dest_abbrev": dest_abbrev,
                "departures_performed": float(row["DEPARTURES_PERFORMED"]),
            }
        )

    for year_month in MONTHS:
        monthly_rows = raw_flights[year_month]
        if not monthly_rows:
            raise ValueError(f"No flight data found for {year_month}")

        max_departures = max(row["departures_performed"] for row in monthly_rows)
        if max_departures <= 0:
            raise ValueError(f"Invalid max departures for {year_month}: {max_departures}")

        normalized_rows = []
        for row in monthly_rows:
            normalized_rows.append(
                {
                    "origin_abbrev": row["origin_abbrev"],
                    "dest_abbrev": row["dest_abbrev"],
                    "flight_normalized": row["departures_performed"] / max_departures,
                }
            )

        normalized_rows.sort(key=lambda row: (row["origin_abbrev"], row["dest_abbrev"]))
        flights_by_month[year_month] = normalized_rows

    return flights_by_month


def simulate_spread(
    model_states: list[str],
    population_rows: dict[str, dict[str, object]],
    weather_rows: dict[tuple[str, str], dict[str, object]],
    vaccination_rows: dict[tuple[str, str], dict[str, object]],
    distance_lookup: dict[tuple[str, str], float],
    flights_by_month: dict[str, list[dict[str, object]]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if SEED_STATE not in model_states:
        raise ValueError(f"Seed state {SEED_STATE} is not available in the 48-state cohort")

    infected_states = {SEED_STATE}
    rng = random.Random(RANDOM_SEED)

    state_rows: list[dict[str, object]] = []
    edge_rows: list[dict[str, object]] = []

    for month_index, year_month in enumerate(MONTHS):
        infected_at_start = set(infected_states)
        newly_infected: set[str] = set()
        infection_source_by_state: dict[str, str] = {}

        for edge in flights_by_month[year_month]:
            origin_abbrev = edge["origin_abbrev"]
            dest_abbrev = edge["dest_abbrev"]

            distance_km = distance_lookup[(origin_abbrev, dest_abbrev)]
            weather = weather_rows[(dest_abbrev, year_month)]
            vaccination = vaccination_rows[(dest_abbrev, year_month)]
            origin_population = population_rows[origin_abbrev]["population_normalized"]
            dest_population = population_rows[dest_abbrev]["population_normalized"]

            raw_score = (
                edge["flight_normalized"]
                * origin_population
                * dest_population
                * (1 / distance_km)
                * (1 / vaccination["vaccination_pct"])
                * (1 / weather["avg_temp_f"])
                * (1 / weather["precip_in"])
            )

            is_eligible = (
                origin_abbrev in infected_at_start
                and dest_abbrev not in infected_at_start
                and dest_abbrev not in newly_infected
            )
            infection_probability = min(1.0, BETA * raw_score) if is_eligible else 0.0
            transmission_event = 0

            if is_eligible and rng.random() < infection_probability:
                newly_infected.add(dest_abbrev)
                infection_source_by_state[dest_abbrev] = origin_abbrev
                transmission_event = 1

            edge_rows.append(
                {
                    "year_month": year_month,
                    "origin_abbrev": origin_abbrev,
                    "dest_abbrev": dest_abbrev,
                    "flight_normalized": edge["flight_normalized"],
                    "population_origin_normalized": origin_population,
                    "population_dest_normalized": dest_population,
                    "distance_km": distance_km,
                    "vaccination_pct": vaccination["vaccination_pct"],
                    "avg_temp_f": weather["avg_temp_f"],
                    "precip_in": weather["precip_in"],
                    "raw_score": raw_score,
                    "infection_probability": infection_probability,
                    "transmission_event": transmission_event,
                }
            )

        infected_states.update(newly_infected)

        for abbrev in model_states:
            is_seed_row = month_index == 0 and abbrev == SEED_STATE
            state_rows.append(
                {
                    "year_month": year_month,
                    "state": population_rows[abbrev]["state"],
                    "abbrev": abbrev,
                    "infected": 1 if abbrev in infected_states else 0,
                    "newly_infected": 1 if abbrev in newly_infected or is_seed_row else 0,
                    "seed_state": SEED_STATE,
                    "infection_source": "seed" if is_seed_row else infection_source_by_state.get(abbrev, ""),
                    "beta": BETA,
                    "random_seed": RANDOM_SEED,
                }
            )

    return state_rows, edge_rows


def validate_outputs(
    model_states: list[str],
    state_rows: list[dict[str, object]],
    edge_rows: list[dict[str, object]],
) -> None:
    if len(model_states) != 48:
        raise ValueError(f"Model state count mismatch: {len(model_states)}")

    expected_state_rows = len(model_states) * len(MONTHS)
    if len(state_rows) != expected_state_rows:
        raise ValueError(f"Expected {expected_state_rows} state rows, found {len(state_rows)}")

    state_lookup: dict[str, list[int]] = defaultdict(list)
    for row in state_rows:
        state_lookup[row["abbrev"]].append(int(row["infected"]))

    for abbrev, infection_series in state_lookup.items():
        for earlier, later in zip(infection_series, infection_series[1:]):
            if later < earlier:
                raise ValueError(f"Infection status regressed for {abbrev}")

    if any(row["origin_abbrev"] == row["dest_abbrev"] for row in edge_rows):
        raise ValueError("Self-loop edge found in stored edge output")

    if any(float(row["distance_km"]) <= 0 for row in edge_rows):
        raise ValueError("Non-positive distance found in stored edge output")

    final_month = MONTHS[-1]
    final_infected = [
        row["abbrev"]
        for row in state_rows
        if row["year_month"] == final_month and int(row["infected"]) == 1
    ]
    if len(final_infected) <= 1:
        raise ValueError("Default seeded run did not spread beyond the seed state")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    population_rows = load_population_rows()
    weather_rows, vaccination_rows = load_monthly_covariates()
    model_states = build_model_states(population_rows, weather_rows, vaccination_rows)
    distance_lookup = build_distance_lookup(model_states, population_rows)
    flights_by_month = build_monthly_flights(model_states)

    state_rows, edge_rows = simulate_spread(
        model_states,
        population_rows,
        weather_rows,
        vaccination_rows,
        distance_lookup,
        flights_by_month,
    )
    validate_outputs(model_states, state_rows, edge_rows)

    state_output_path = OUTPUT_DIR / "state_infection_status.csv"
    edge_output_path = OUTPUT_DIR / "edge_transmission_scores.csv"

    write_csv(
        state_output_path,
        state_rows,
        [
            "year_month",
            "state",
            "abbrev",
            "infected",
            "newly_infected",
            "seed_state",
            "infection_source",
            "beta",
            "random_seed",
        ],
    )
    write_csv(
        edge_output_path,
        edge_rows,
        [
            "year_month",
            "origin_abbrev",
            "dest_abbrev",
            "flight_normalized",
            "population_origin_normalized",
            "population_dest_normalized",
            "distance_km",
            "vaccination_pct",
            "avg_temp_f",
            "precip_in",
            "raw_score",
            "infection_probability",
            "transmission_event",
        ],
    )

    map_paths = generate_infection_maps(
        status_csv_path=state_output_path,
        output_dir=OUTPUT_DIR / "maps",
        map_style="infection",
    )

    print(f"Saved state output to {state_output_path}")
    print(f"Saved edge output to {edge_output_path}")
    for path in map_paths:
        print(f"Saved map to {path}")


if __name__ == "__main__":
    main()
