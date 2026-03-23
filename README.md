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

- `SEED_STATE = "LA"`
- `BETA = 15000000`
- `RANDOM_SEED = 3780`
- `MONTHS = ["2024-12", "2025-01", "2025-02"]`

The default seed state used is Louisiana because that was the only state with 'High' level of influneza infection at that start of December. The checked-in CSV outputs and map PNGs correspond to this default run, which is tuned to end with 30 infected states by February 2025 without changing the fixed `python run_model.py` entrypoint. This tuning is done to match the 30+ states that had the Very High level of influenza infection at the end of February 2025.

The simulation uses an SI-persistent model. This means once a state becomes infected in a month, it stays infected for the remaining months in the run.

## Modelling relationship

The stored transmission score follows this relationship:

`infection_probability = beta * flight_frequency * population_at_origin * population_at_destination * (1 / distance) * (1 / vaccination_rate) * (1 / temperature) * (1 / precipitation)`

- Flight frequency is normalized within each month.
- Population uses the normalized values in `US_pop_with_geo.csv`.
- Distance, vaccination, temperature, and precipitation enter as inverse terms.
- Self-loops are removed before scoring so zero-distance origin-destination pairs are never modeled.
- Final probabilities are forced into the valid probability range `[0, 1]` by setting any value above `1` to `1`.

### Explain beta used

Using the lecture value `beta = 0.1` yields near-zero transmission probabilities on this dataset over three months, so the default demo workflow uses `beta = 15000000` for the saved Louisiana scenario.

In this implementation, `beta` is best interpreted as a calibration constant for the current normalized scoring formula rather than as a directly estimated biological influenza transmission rate. The model multiplies several small normalized or inverse terms together, so the unscaled edge scores are extremely small on this dataset. A much smaller `beta` makes the simulation effectively inert, while a much larger `beta` pushes more edges toward the probability cap of `1.0` and makes the spread less informative.

Across the current contiguous-48 inter-state monthly edge set:

- raw transmission scores range from `1.05e-14` to `1.19e-05`
- with `beta = 15000000`, unclamped infection probabilities range from `1.58e-07` to `178.20`
- probabilities are then clamped to the valid range `[0, 1]` before transmission is sampled

Under the default seed state (`LA`) and random seed (`3780`), the observed infection totals are:

- December 2024: `5` infected states
- January 2025: `20` infected states
- February 2025: `30` infected states

So the justification for `beta = 15000000` is that it serves as the documented default calibration for this specific dataset and three-month time window: large enough to produce a visible Louisiana-seeded spread and tuned so the saved default run reaches 30 infected states by February 2025. The runtime validation remains a generic sanity check that the default run spreads beyond the seed state; it does not enforce the 30-state endpoint as a hard invariant.

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

| Column             | Description                                                                                                          |
| ------------------ | -------------------------------------------------------------------------------------------------------------------- |
| `year_month`       | Simulation month in `YYYY-MM` format                                                                                 |
| `state`            | Full state name                                                                                                      |
| `abbrev`           | State abbreviation                                                                                                   |
| `infected`         | `1` if the state is infected by the end of that month, else `0`                                                      |
| `newly_infected`   | `1` if the state first becomes infected in that month, else `0`                                                      |
| `seed_state`       | Seed state used for the run                                                                                          |
| `infection_source` | `seed` for the initial seed row, otherwise the origin state abbreviation that first infected the state in that month |
| `beta`             | Fixed transmission scaling used in the run                                                                           |
| `random_seed`      | RNG seed used in the run                                                                                             |

### `outputs/edge_transmission_scores.csv`

One row per inter-state origin-destination-month edge, with these columns:

| Column                         | Description                                                           |
| ------------------------------ | --------------------------------------------------------------------- |
| `year_month`                   | Simulation month in `YYYY-MM` format                                  |
| `origin_abbrev`                | Origin state abbreviation                                             |
| `dest_abbrev`                  | Destination state abbreviation                                        |
| `flight_normalized`            | Month-normalized departures for the origin-destination pair           |
| `population_origin_normalized` | Normalized origin population                                          |
| `population_dest_normalized`   | Normalized destination population                                     |
| `distance_km`                  | Great-circle distance between state centroids                         |
| `vaccination_pct`              | Destination-state vaccination percentage for that month               |
| `avg_temp_f`                   | Destination-state average temperature for that month                  |
| `precip_in`                    | Destination-state precipitation for that month                        |
| `raw_score`                    | Unscaled structural transmission score before multiplying by `beta`   |
| `infection_probability`        | Applied transmission probability after eligibility rules and clamping |
| `transmission_event`           | `1` if transmission occurred on that edge in that month, else `0`     |

## Plotting

`US_plot.py` now renders only the contiguous 48-state map and colors each state by simulated infection status:

- susceptible = light gray
- infected = red

The plotting script reads `outputs/state_infection_status.csv`, loads the Census state shapefile from `cb_2024_us_state_500k.zip`, filters out Alaska, Hawaii, District of Columbia, Puerto Rico, and other non-contiguous territories, then saves one PNG per month.

You can rerun plotting alone with:

```powershell
python US_plot.py
```

## Validation

Actual influenza data for every state is loaded to compare against our predicted infection spread. The raw data consists of the influenza activity level (`Minimal`, `Low`, `Moderate`, `High`, `Very High`) of every state during every week of the flu season. We processed this by extracting the average activity level of every state for each month, and treating the `Very High` activity level as infected states.

We then compared the predicted infection status of a state with the actual infection status by calculating the accuracy, recall and precision of our predictions. This was done for individual months and the overall results for all 3 months.

Our results are:

| Month       | N States | Accuracy  | Recall    | Precision | TP     | TN     | FP     | FN     |
| ----------- | -------- | --------- | --------- | --------- | ------ | ------ | ------ | ------ |
| 2024-12     | 48       | 0.875     | 0.4       | 0.4       | 2      | 40     | 3      | 3      |
| 2025-01     | 48       | 0.604     | 0.52      | 0.65      | 13     | 16     | 7      | 12     |
| 2025-02     | 48       | 0.625     | 0.676     | 0.767     | 23     | 7      | 7      | 11     |
| **Overall** | **144**  | **0.701** | **0.594** | **0.691** | **38** | **63** | **17** | **26** |

**Metrics:**

- **Accuracy**: Proportion of correctly predicted infected/susceptible states
- **Recall**: Proportion of actual infected states correctly identified (true positive rate)
- **Precision**: Proportion of predicted infected states that were actually infected
- **TP/TN/FP/FN**: Confusion matrix components (True Positives, True Negatives, False Positives, False Negatives)

Additionally, maps of the actual infected states can be plotted with:

```powershell
python US_plot.py --mode validate
```
