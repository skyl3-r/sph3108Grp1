import zipfile
from pathlib import Path
from urllib.request import urlretrieve

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from affine import Affine
from matplotlib.colors import LogNorm
from rasterio.enums import Resampling
from rasterio.transform import array_bounds
from rasterio.windows import from_bounds

ZIP_PATH = Path("cb_2024_us_state_500k.zip")
EXTRACT_DIR = Path("us_state_shapefile_insets")
RASTER_PATH = Path("usa_pop_2024_CN_1km_R2025A_UA_v1.tif")
OUTPUT_PATH = Path("us_map_with_population_overlay.png")
RASTER_URL = (
    "https://worldpop-public-data.soton.ac.uk/GIS/Population/Global_2015_2030/"
    "R2025A/2024/USA/v1/1km_ua/constrained/"
    "usa_pop_2024_CN_1km_R2025A_UA_v1.tif"
)


def extract_states(zip_path: Path, extract_dir: Path) -> gpd.GeoDataFrame:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    shp_path = next(extract_dir.glob("*.shp"))
    return gpd.read_file(shp_path)


def ensure_raster(raster_path: Path, raster_url: str) -> None:
    if not raster_path.exists():
        urlretrieve(raster_url, raster_path)


def draw_inset(fig, ax_pos, title, geodf):
    ax = fig.add_axes(ax_pos)
    geodf.plot(ax=ax, facecolor="#f0f2f5", edgecolor="#2b2b2b", linewidth=0.7)

    minx, miny, maxx, maxy = geodf.total_bounds
    xpad = max((maxx - minx) * 0.08, 0.5)
    ypad = max((maxy - miny) * 0.10, 0.5)

    ax.set_xlim(minx - xpad, maxx + xpad)
    ax.set_ylim(miny - ypad, maxy + ypad)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor("white")

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.1)
        spine.set_edgecolor("#3b3b3b")

    ax.set_title(title, fontsize=10, pad=4)
    return ax


def load_mainland_raster(src: rasterio.io.DatasetReader, bounds, max_dim=2400):
    window = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
    window_height = max(1, int(window.height))
    window_width = max(1, int(window.width))
    scale = max(window_height / max_dim, window_width / max_dim, 1)
    out_height = max(1, int(window_height / scale))
    out_width = max(1, int(window_width / scale))

    data = src.read(
        1,
        window=window,
        out_shape=(out_height, out_width),
        masked=True,
        resampling=Resampling.average,
    )
    data = np.ma.masked_invalid(data)
    data = np.ma.masked_less_equal(data, 0)

    transform = src.window_transform(window) * Affine.scale(
        window_width / out_width,
        window_height / out_height,
    )
    west, south, east, north = array_bounds(out_height, out_width, transform)
    return data, (west, east, south, north)


ensure_raster(RASTER_PATH, RASTER_URL)
gdf = extract_states(ZIP_PATH, EXTRACT_DIR)

with rasterio.open(RASTER_PATH) as src:
    gdf = gdf.to_crs(src.crs)

exclude_main = {"AK", "HI", "DC", "PR", "VI", "GU", "MP", "AS"}
gdf_main = gdf[~gdf["STUSPS"].isin(exclude_main)].copy()
regions = {
    "Alaska": gdf[gdf["STUSPS"] == "AK"].copy(),
    "Hawaii": gdf[gdf["STUSPS"] == "HI"].copy(),
    "District of Columbia": gdf[gdf["STUSPS"] == "DC"].copy(),
    "Puerto Rico": gdf[gdf["STUSPS"] == "PR"].copy(),
    "U.S. Virgin Islands": gdf[gdf["STUSPS"] == "VI"].copy(),
    "Guam": gdf[gdf["STUSPS"] == "GU"].copy(),
    "N. Mariana Is.": gdf[gdf["STUSPS"] == "MP"].copy(),
    "American Samoa": gdf[gdf["STUSPS"] == "AS"].copy(),
}

with rasterio.open(RASTER_PATH) as src:
    mainland_bounds = gdf_main.total_bounds
    raster_data, raster_extent = load_mainland_raster(src, mainland_bounds)

fig = plt.figure(figsize=(16, 10))

ax_main = fig.add_axes([0.05, 0.18, 0.72, 0.72])
ax_main.set_facecolor("#ebf4fb")

image = ax_main.imshow(
    raster_data,
    extent=raster_extent,
    origin="upper",
    cmap="inferno",
    norm=LogNorm(vmin=1, vmax=float(raster_data.max())),
    alpha=0.88,
    zorder=1,
)
gdf_main.boundary.plot(ax=ax_main, color="white", linewidth=0.6, zorder=2)
gdf_main.boundary.plot(ax=ax_main, color="#1f1f1f", linewidth=0.2, zorder=3)

minx, miny, maxx, maxy = gdf_main.total_bounds
xpad = (maxx - minx) * 0.02
ypad = (maxy - miny) * 0.03

ax_main.set_xlim(minx - xpad, maxx + xpad)
ax_main.set_ylim(miny - ypad, maxy + ypad)
ax_main.set_axis_off()
ax_main.set_title("United States Population Raster (WorldPop 2024) with Insets", pad=12)

cax = fig.add_axes([0.05, 0.10, 0.72, 0.03])
colorbar = fig.colorbar(image, cax=cax, orientation="horizontal")
colorbar.set_label("Population count per 1 km cell (log scale)")

draw_inset(fig, [0.05, 0.03, 0.22, 0.18], "Alaska", regions["Alaska"])
draw_inset(fig, [0.28, 0.03, 0.16, 0.12], "Hawaii", regions["Hawaii"])
draw_inset(fig, [0.79, 0.61, 0.17, 0.12], "District of Columbia", regions["District of Columbia"])
draw_inset(fig, [0.79, 0.46, 0.17, 0.12], "Puerto Rico", regions["Puerto Rico"])
draw_inset(fig, [0.79, 0.30, 0.08, 0.10], "Guam", regions["Guam"])
draw_inset(fig, [0.88, 0.30, 0.08, 0.10], "U.S. Virgin Islands", regions["U.S. Virgin Islands"])
draw_inset(fig, [0.79, 0.17, 0.08, 0.10], "N. Mariana Is.", regions["N. Mariana Is."])
draw_inset(fig, [0.88, 0.17, 0.08, 0.10], "American Samoa", regions["American Samoa"])

plt.savefig(OUTPUT_PATH, dpi=200, bbox_inches="tight")
plt.close(fig)
