# Modelling the spread of Influenza a between cities in the US

This repository contains cleaned state-level inputs for influenza modelling from December 2024 to February 2025.

## Variable summary

| Variable | Description | Unit | Mean | Min | Max |
| --- | --- | --- | ---: | ---: | ---: |
| `departures_normalized` | normalized flight count used in `state_flight_freq_norm_matrices.rds` | unitless | 0.0158 | 0.000037 | 1.0000 |
| `population_normalized` | Population scaled by the maximum population in `US_pop_with_geo.csv` | unitless | 0.1669 | 0.0150 | 1.0000 |
| `distance_km` | Great-circle distance between state centroids in the 48-state cohort, excluding self-pairs in `state_distances.rds`| kilometers | 1673.44 | 88.83 | 4226.84 |
| `vaccination_pct` | Influenza vaccination estimate for population age `>=6 Months` in `state_month_vaccination.csv`| percent | 39.30 | 24.20 | 56.60 |
| `avg_temp_f` | Monthly average temperature in `state_month_weather.csv` | degrees Fahrenheit | 32.56 | 5.60 | 65.80 |
| `precip_in` | Monthly precipitation in `state_month_weather.csv`| inches | 2.43 | 0.01 | 7.80 |

## Modelling relationship

The intended infection probability relationship is:

`infection_probability = beta * flight_frequency * population_at_origin * population_at_destination * (1 / distance) * (1 / vaccination_rate) * (1 / temperature) * (1 / precipitation)`

- Distance, vaccination, temperature, and precipitation enter as inverse terms under this stated modelling assumption.
- Flight frequency and population are normalized so they stay on a comparable scale inside the probability expression and do not dominate `beta` purely because their raw magnitudes are much larger than the other terms.

## Alignment rules

- The current weather-linked modelling cohort is restricted to the 48 contiguous U.S. states because the raw weather source files do not include Alaska, Hawaii, District of Columbia, or Puerto Rico. (Limitation)
- Vaccination cleaning excludes non-state and sub-state records by keeping only geographies that match the weather-ready state cohort.
- The current cleaning step produces standalone weather and vaccination inputs; it does not merge them into a single modelling table.


