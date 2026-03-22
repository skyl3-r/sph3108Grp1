# Modelling the Spread of Influenza Between U.S. States

This repository contains cleaned state-level inputs and a Python simulation workflow for modelling influenza spread across the contiguous 48 U.S. states from December 2024 to February 2025.

## Workflow

Run the model with:

```powershell
python run_model.py
```

The script reads directly from the cleaned CSV inputs already stored in the repo:

- `US_pop_with_geo.csv`
- `state_month_weather.csv`
- `state_month_vaccination.csv`
- `flight_data/state_flight_freq_final.csv`

It then:

1. restricts the model to the contiguous 48-state cohort
2. computes pairwise state distances in Python
3. normalizes monthly flight departures in Python
4. simulates month-by-month spread using an SI-persistent infection model
5. stores tabular outputs in `outputs/`
6. saves one 48-state infection map PNG per month in `outputs/maps/`

## Default model settings

- `SEED_STATE = "TX"`
- `BETA = 300000`
- `RANDOM_SEED = 42`
- `MONTHS = ["2024-12", "2025-01", "2025-02"]`

Texas is the default seed because, within the contiguous-48 cohort in the current flight dataset, it has the highest total departure volume and is therefore the strongest single-state default for a first spread scenario.

The simulation uses an SI-persistent model. This means once a state becomes infected in a month, it stays infected for the remaining months in the run.

## Modelling relationship

The stored transmission score follows this relationship:

`infection_probability = beta * flight_frequency * population_at_origin * population_at_destination * (1 / distance) * (1 / vaccination_rate) * (1 / temperature) * (1 / precipitation)`

- Flight frequency is normalized within each month.
- Population uses the normalized values in `US_pop_with_geo.csv`.
- Distance, vaccination, temperature, and precipitation enter as inverse terms.
- Self-loops are removed before scoring so zero-distance origin-destination pairs are never modeled.
- Final probabilities are clamped to `[0, 1]`.

The lecture-style `beta = 0.1` yields near-zero transmission probabilities on this dataset over only three months, so the current demo workflow uses `beta = 300000` to produce visible but still bounded spread in the saved outputs.

## Alignment rules

- The weather-linked modelling cohort is restricted to the 48 contiguous U.S. states because the raw weather source files do not include Alaska, Hawaii, District of Columbia, or Puerto Rico. (limitation)
- Vaccination cleaning excludes non-state and sub-state records by keeping only geographies that match the weather-ready state cohort.
- The simulation uses the weather-ready and vaccination-ready 48-state overlap as the source of truth for the modelling cohort.

## Stored outputs

`python run_model.py` writes:

- `outputs/state_infection_status.csv`
- `outputs/edge_transmission_scores.csv`
- `outputs/maps/infection_map_2024-12.png`
- `outputs/maps/infection_map_2025-01.png`
- `outputs/maps/infection_map_2025-02.png`

### `outputs/state_infection_status.csv`

One row per state-month, with these columns:

| Column | Description |
| --- | --- |
| `year_month` | Simulation month in `YYYY-MM` format |
| `state` | Full state name |
| `abbrev` | State abbreviation |
| `infected` | `1` if the state is infected by the end of that month, else `0` |
| `newly_infected` | `1` if the state first becomes infected in that month, else `0` |
| `seed_state` | Seed state used for the run |
| `infection_source` | `seed` for the initial seed row, otherwise the origin state abbreviation that first infected the state in that month |
| `beta` | Fixed transmission scaling used in the run |
| `random_seed` | RNG seed used in the run |

### `outputs/edge_transmission_scores.csv`

One row per inter-state origin-destination-month edge, with these columns:

| Column | Description |
| --- | --- |
| `year_month` | Simulation month in `YYYY-MM` format |
| `origin_abbrev` | Origin state abbreviation |
| `dest_abbrev` | Destination state abbreviation |
| `flight_normalized` | Month-normalized departures for the origin-destination pair |
| `population_origin_normalized` | Normalized origin population |
| `population_dest_normalized` | Normalized destination population |
| `distance_km` | Great-circle distance between state centroids |
| `vaccination_pct` | Destination-state vaccination percentage for that month |
| `avg_temp_f` | Destination-state average temperature for that month |
| `precip_in` | Destination-state precipitation for that month |
| `raw_score` | Unscaled structural transmission score before multiplying by `beta` |
| `infection_probability` | Applied transmission probability after eligibility rules and clamping |
| `transmission_event` | `1` if transmission occurred on that edge in that month, else `0` |

## Plotting

`US_plot.py` now renders only the contiguous 48-state map and colors each state by simulated infection status:

- susceptible = light gray
- infected = red

The plotting script reads `outputs/state_infection_status.csv`, loads the Census state shapefile from `cb_2024_us_state_500k.zip`, filters out Alaska, Hawaii, District of Columbia, Puerto Rico, and other non-contiguous territories, then saves one PNG per month.

You can rerun plotting alone with:

```powershell
python US_plot.py
```
