library(sf)
library(ggplot2)
library(grid)

# ----------------------------
# 1. Read shapefile directly from unzipped folder
#    Unzip the file first if needed
# ----------------------------
zipfile <- "cb_2024_us_state_500k.zip"
unzip_dir <- "us_state_shapefile_insets"

if (!dir.exists(unzip_dir)) {
  dir.create(unzip_dir, recursive = TRUE)
  unzip(zipfile, exdir = unzip_dir)
}

shp_file <- list.files(unzip_dir, pattern = "\\.shp$", full.names = TRUE)[1]
us <- st_read(shp_file, quiet = TRUE)

# ----------------------------
# 2. Split data
# ----------------------------
main_us <- subset(us, !(STUSPS %in% c("AK", "HI", "DC", "PR", "VI", "GU", "MP", "AS")))

ak <- subset(us, STUSPS == "AK")
hi <- subset(us, STUSPS == "HI")
dc <- subset(us, STUSPS == "DC")
pr <- subset(us, STUSPS == "PR")

# ----------------------------
# 3. Helper theme
# ----------------------------
base_map_theme <- theme_void() +
  theme(
    panel.border = element_rect(color = "black", fill = NA, linewidth = 0.7),
    plot.title = element_text(hjust = 0.5, size = 10)
  )

# ----------------------------
# 4. Build each subplot
# ----------------------------
p_main <- ggplot(main_us) +
  geom_sf(fill = "steelblue", color = "white", linewidth = 0.1) +
  theme_void() +
  ggtitle("United States Map with Insets") +
  theme(plot.title = element_text(hjust = 0.5, size = 14))

p_ak <- ggplot(ak) +
  geom_sf(fill = "steelblue", color = "white", linewidth = 0.1) +
  ggtitle("Alaska") +
  base_map_theme

p_hi <- ggplot(hi) +
  geom_sf(fill = "steelblue", color = "white", linewidth = 0.1) +
  ggtitle("Hawaii") +
  base_map_theme

p_dc <- ggplot(dc) +
  geom_sf(fill = "steelblue", color = "white", linewidth = 0.1) +
  ggtitle("District of Columbia") +
  base_map_theme

p_pr <- ggplot(pr) +
  geom_sf(fill = "steelblue", color = "white", linewidth = 0.1) +
  ggtitle("Puerto Rico") +
  base_map_theme

# ----------------------------
# 5. Convert ggplots to grobs
# ----------------------------
g_main <- ggplotGrob(p_main)
g_ak <- ggplotGrob(p_ak)
g_hi <- ggplotGrob(p_hi)
g_dc <- ggplotGrob(p_dc)
g_pr <- ggplotGrob(p_pr)

# ----------------------------
# 6. Draw layout manually
# ----------------------------
png("us_map_with_insets_r.png", width = 1600, height = 1000, res = 150)
grid.newpage()

# Main map
pushViewport(viewport(x = 0.41, y = 0.54, width = 0.72, height = 0.76))
grid.draw(g_main)
upViewport()

# Bottom-left
pushViewport(viewport(x = 0.16, y = 0.12, width = 0.22, height = 0.18))
grid.draw(g_ak)
upViewport()

pushViewport(viewport(x = 0.36, y = 0.09, width = 0.16, height = 0.12))
grid.draw(g_hi)
upViewport()

# Right side
pushViewport(viewport(x = 0.88, y = 0.67, width = 0.17, height = 0.12))
grid.draw(g_dc)
upViewport()

pushViewport(viewport(x = 0.88, y = 0.52, width = 0.17, height = 0.12))
grid.draw(g_pr)
upViewport()

dev.off()
