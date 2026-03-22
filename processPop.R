library(readr)
library(dplyr)

# code to get df with state names, population, latitude, longitude

# Read the CSVs
pop <- read_csv("pop2023.csv")
geo <- read_csv("US_GeoCode.csv")
geo <- geo %>%
  rename(abbrev = `state&teritory`)

# Join on state name
df <- pop %>%
  inner_join(geo, by = c("name" = "Name")) %>%
  mutate(
    population_normalized = population / max(population, na.rm = TRUE)
  ) %>%
  select(name, population, population_normalized, abbrev, latitude, longitude)

# Save result
write_csv(df, "US_pop_with_geo.csv")

# View result
print(df)
