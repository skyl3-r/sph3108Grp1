import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt

# ----------------------------
# 1. Unzip and read shapefile
# ----------------------------
zip_path = Path("cb_2024_us_state_500k.zip")
extract_dir = Path("us_state_shapefile_insets")
extract_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_path, "r") as zf:
    zf.extractall(extract_dir)

shp_path = next(extract_dir.glob("*.shp"))
gdf = gpd.read_file(shp_path)

# ----------------------------
# 2. Split data into main map and inset groups
# ----------------------------
exclude_main = {"AK", "HI", "DC", "PR", "VI", "GU", "MP", "AS"}
gdf_main = gdf[~gdf["STUSPS"].isin(exclude_main)].copy()

regions = {
    "Alaska": gdf[gdf["STUSPS"] == "AK"].copy(),
    "Hawaii": gdf[gdf["STUSPS"] == "HI"].copy(),
    "District of Columbia": gdf[gdf["STUSPS"] == "DC"].copy(),
    "Puerto Rico": gdf[gdf["STUSPS"] == "PR"].copy(),
}

# ----------------------------
# 3. Helper for inset boxes
# ----------------------------
def draw_inset(fig, ax_pos, title, geodf):
    ax = fig.add_axes(ax_pos)
    geodf.plot(ax=ax)

    minx, miny, maxx, maxy = geodf.total_bounds
    xpad = max((maxx - minx) * 0.08, 0.5)
    ypad = max((maxy - miny) * 0.10, 0.5)

    ax.set_xlim(minx - xpad, maxx + xpad)
    ax.set_ylim(miny - ypad, maxy + ypad)
    ax.set_xticks([])
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.2)

    ax.set_title(title, fontsize=10, pad=4)
    return ax

# ----------------------------
# 4. Plot
# ----------------------------
fig = plt.figure(figsize=(16, 10))

# Main contiguous U.S.
ax_main = fig.add_axes([0.05, 0.16, 0.72, 0.76])
gdf_main.plot(ax=ax_main)

minx, miny, maxx, maxy = gdf_main.total_bounds
xpad = (maxx - minx) * 0.02
ypad = (maxy - miny) * 0.03

ax_main.set_xlim(minx - xpad, maxx + xpad)
ax_main.set_ylim(miny - ypad, maxy + ypad)
ax_main.set_axis_off()
ax_main.set_title("United States Map with Insets", pad=12)

# Insets
draw_inset(fig, [0.05, 0.03, 0.22, 0.18], "Alaska", regions["Alaska"])
draw_inset(fig, [0.28, 0.03, 0.16, 0.12], "Hawaii", regions["Hawaii"])

draw_inset(fig, [0.79, 0.61, 0.17, 0.12], "District of Columbia", regions["District of Columbia"])
draw_inset(fig, [0.79, 0.46, 0.17, 0.12], "Puerto Rico", regions["Puerto Rico"])

plt.savefig("us_map_with_insets.png", dpi=200, bbox_inches="tight")
plt.show()
