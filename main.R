if (!require("igraph")) install.packages("igraph")
if (!require("geosphere")) install.packages("geosphere")
library(igraph)
library(sf)
library(tidyverse)
library(geosphere)
library(ggplot2)
library(rnaturalearth)
library(rnaturalearthdata)

# constants 
timesteps <- 12 # 12 months
beta <- 0.1 # Transmission rate

# load cities 
nodes <- data.frame(
  name = c("Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu", "Chongqing", "Xian", "Wuhan", "Hangzhou", "Tianjin"),
  lat = c(39.9042, 31.2304, 23.1291, 22.5431, 30.5728, 29.5630, 34.3416, 30.5928, 30.2741, 39.3434),
  lon = c(116.4074, 121.4737, 113.2644, 114.0579, 104.0665, 106.5516, 108.9398, 114.3055, 120.1551, 117.3616),
  population = c(21540000, 24870000, 18680000, 17430000, 16330000,31020000, 12950000, 11240000, 11940000, 15620000))

#Calculate Pairwise Distances Between Cities
coordinates <- as.matrix(nodes[, c("lon", "lat")])
dist_matrix <- distm(coordinates, fun = distHaversine)/1000
# Assign city names to rows and columns
rownames(dist_matrix) <- nodes$name
colnames(dist_matrix) <- nodes$name
# Convert the distance matrix to a long-format dataframe
edges <- as.data.frame(as.table(dist_matrix))
# Map city names to 'from' and 'to'
colnames(edges) <- c("from", "to", "distance")
edges[] <- lapply(edges, function(x) if (is.factor(x)) as.character(x) else x)
# Remove self-loops (distances from a city to itself)
edges <- edges %>% filter(from != to)

# Step 3: Add Realistic Travel Frequencies
edges <- edges %>%
  mutate(
    travel_freq = case_when(
      distance < 500 ~ runif(n(), 0.8, 1.0),
      distance < 1000 ~ runif(n(), 0.5, 0.7), # Moderate frequency for medium distances
      TRUE ~ runif(n(), 0.2, 0.4)))

# Step 4: Build Network
g <- graph_from_data_frame(edges, directed = TRUE, vertices = nodes)
# Add initial infection status to nodes: 1 = infected, 0 = susceptible
V(g)$status <- ifelse(V(g)$name == "Beijing", 1, 0) # City 1 (Beijing) starts infected
# Initialize a list to store infection statuses over time
status_over_time <- data.frame(matrix(0,timesteps,length(nodes$name)))
colnames(status_over_time) <- nodes$name

# Step 5: Simulate Disease Spread and Track Status Over Time
for (t in 1:timesteps) {
  # Save the current infection status
  status_over_time[t,] <- V(g)$status
  # Simulate disease spread for the current timestep
  infected <- which(V(g)$status == 1) # Find infected cities
  for (node in infected) {
    neighbors <- neighbors(g, node, mode = "out") # Get outgoing neighbors
    for (neighbor in neighbors) {
      if (V(g)$status[neighbor] == 0) { # If neighbor is susceptible
        # Infection probability depends on travel frequency and populations of both cities
        prob <- beta * E(g)[node %->% neighbor]$travel_freq *
          (V(g)$population[node] / max(V(g)$population)) * # Source population
          (V(g)$population[neighbor] / max(V(g)$population)) # Target population
        if (runif(1) < prob) {
          V(g)$status[neighbor] <- 1 # Infect the neighbor city
        }}}}}
# Add a 'timestep' column to the status_over_time dataframe
status_over_time$timestep <- 1:timesteps
# Convert to long format
status_long <- status_over_time %>%
  pivot_longer(
    cols = -timestep, # All columns except 'timestep'
    names_to = "city", values_to = "status")
# Add coordinates to the data
status_long <- status_long %>%
  left_join(nodes, by = c("city" = "name"))

# Load country boundaries (focus on China)
world <- ne_countries(scale = "medium", returnclass = "sf") # Load all countries
china <- world %>% filter(name == "China") # Extract China outline
ggplot() +
  # Add country outline
  geom_sf(data = china, fill = NA, color = "black", size = 0.5) +
  # Add city infection points
  geom_point(data = status_long, aes(x = lon, y = lat, color = factor(status)), size = 2) +
  scale_color_manual(
    values = c("0" = "blue", "1" = "red"), # Susceptible = blue, Infected = red
    labels = c("Susceptible", "Infected"),
    name = "Status") +
  facet_wrap(~ timestep, ncol = 3) + # Control layout with 3 columns
  coord_sf() + # Use spatial coordinates
  theme_minimal(base_size = 12) + # Minimal theme
  theme(
    panel.grid = element_blank(), # Remove gridlines
    axis.line = element_line(color = "black"), # Add clean black axis lines
    axis.text = element_text(size = 8, color = "black"), # Smaller axis text
    axis.ticks = element_line(color = "black"), # Enable tick marks
    axis.title = element_text(size = 12), # Add axis titles
    panel.spacing = unit(0, "lines"), # Remove space between facets
    panel.border = element_rect(color = "black", fill = NA, size = 0.5), # Add black border
    strip.background = element_blank(), # Remove facet strip background
    strip.text = element_text(face = "bold", size = 12) # Style facet labels
  ) +
  labs(title = "Spread of Disease Across Cities Over Time", x = "Longitude", y = "Latitude")

