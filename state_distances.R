library(readr)
library(dplyr)

haversine_km <- function(lat1, lon1, lat2, lon2) {
  earth_radius_km <- 6371

  lat1_rad <- lat1 * pi / 180
  lon1_rad <- lon1 * pi / 180
  lat2_rad <- lat2 * pi / 180
  lon2_rad <- lon2 * pi / 180

  delta_lat <- lat2_rad - lat1_rad
  delta_lon <- lon2_rad - lon1_rad

  a <- sin(delta_lat / 2) ^ 2 +
    cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ^ 2

  2 * earth_radius_km * asin(pmin(1, sqrt(a)))
}

states <- read_csv("US_pop_with_geo.csv") %>%
  select(name, latitude, longitude)

distance_matrix <- outer(
  seq_len(nrow(states)),
  seq_len(nrow(states)),
  Vectorize(function(i, j) {
    haversine_km(
      states$latitude[i],
      states$longitude[i],
      states$latitude[j],
      states$longitude[j]
    )
  })
)

rownames(distance_matrix) <- states$name
colnames(distance_matrix) <- states$name

distance_matrix_df <- data.frame(
  state = rownames(distance_matrix),
  distance_matrix,
  check.names = FALSE
)

edge_index <- expand.grid(
  from = seq_len(nrow(states)),
  to = seq_len(nrow(states))
)

edge_list <- tibble(
  from = states$name[edge_index$from],
  to = states$name[edge_index$to],
  distance = distance_matrix[cbind(edge_index$from, edge_index$to)]
) %>%
  filter(from != to)

saveRDS(
  list(
    distance_matrix = distance_matrix_df,
    distance_edges = edge_list
  ),
  "US_state_distances.rds"
)
