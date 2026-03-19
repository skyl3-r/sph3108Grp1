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
  inner_join(geo, by = c("name" = "Name"))

# View result
print(df)