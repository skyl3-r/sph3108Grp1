from __future__ import annotations

from dataclasses import dataclass
import csv
import struct
import zipfile
from pathlib import Path
import argparse

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
ZIP_PATH = ROOT / "cb_2024_us_state_500k.zip"
STATUS_CSV = ROOT / "outputs" / "state_infection_status.csv"
OUTPUT_DIR = ROOT / "outputs" / "maps"
POPULATION_CSV = ROOT / "US_pop_with_geo.csv"

EXCLUDED_STATES = {"AK", "HI", "DC", "PR", "VI", "GU", "MP", "AS"}
IMAGE_SIZE = (1800, 1100)
BACKGROUND_COLOR = "#f7f5f0"
STATE_OUTLINE_COLOR = "#ffffff"
SUSCEPTIBLE_COLOR = "#d9d9d9"
INFECTED_COLOR = "#c62828"
TEXT_COLOR = "#1f1f1f"
LEGEND_OUTLINE_COLOR = "#5f5f5f"
LABEL_TEXT_COLOR = "#ffffff"
LABEL_STROKE_COLOR = "#1f1f1f"

STATE_LABEL_OFFSETS: dict[str, tuple[int, int]] = {
    "VT": (-18, -18),
    "NH": (34, -24),
    "MA": (58, -6),
    "RI": (62, 18),
    "CT": (24, 24),
    "NY": (-36, -10),
    "NJ": (46, 24),
    "PA": (-24, 20),
    "DE": (52, 34),
    "MD": (10, 40),
}


@dataclass(frozen=True)
class MapStyleConfig:
    map_name: str
    title_font_size: float | None
    subtitle_font_size: float | None
    legend_font_size: float | None
    show_state_labels: bool
    state_label_font_size: float | None = None


MAP_STYLE_CONFIGS = {
    "infection": MapStyleConfig(
        map_name="infection_map",
        title_font_size=28,
        subtitle_font_size=20,
        legend_font_size=20,
        show_state_labels=True,
        state_label_font_size=12,
    ),
    "validation": MapStyleConfig(
        map_name="validation_map",
        title_font_size=None,
        subtitle_font_size=None,
        legend_font_size=None,
        show_state_labels=False,
        state_label_font_size=None,
    ),
}


def read_dbf_records(dbf_bytes: bytes) -> list[dict[str, str]]:
    record_count = struct.unpack_from("<I", dbf_bytes, 4)[0]
    header_length = struct.unpack_from("<H", dbf_bytes, 8)[0]
    record_length = struct.unpack_from("<H", dbf_bytes, 10)[0]

    fields: list[tuple[str, str, int]] = []
    offset = 32
    while dbf_bytes[offset] != 0x0D:
        descriptor = dbf_bytes[offset : offset + 32]
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii")
        field_type = chr(descriptor[11])
        field_length = descriptor[16]
        fields.append((name, field_type, field_length))
        offset += 32

    records: list[dict[str, str]] = []
    data_offset = header_length
    for index in range(record_count):
        start = data_offset + index * record_length
        end = start + record_length
        record_bytes = dbf_bytes[start:end]
        if record_bytes[:1] == b"*":
            continue

        field_offset = 1
        row: dict[str, str] = {}
        for name, _field_type, field_length in fields:
            value = record_bytes[field_offset : field_offset + field_length]
            row[name] = value.decode("utf-8", errors="ignore").strip()
            field_offset += field_length
        records.append(row)

    return records


def read_polygon_records(shp_bytes: bytes) -> list[list[list[tuple[float, float]]]]:
    records: list[list[list[tuple[float, float]]]] = []
    offset = 100

    while offset < len(shp_bytes):
        if offset + 8 > len(shp_bytes):
            break

        _record_number, content_length_words = struct.unpack_from(">2i", shp_bytes, offset)
        offset += 8
        content_length = content_length_words * 2
        record_end = offset + content_length
        shape_type = struct.unpack_from("<i", shp_bytes, offset)[0]

        if shape_type == 0:
            records.append([])
            offset = record_end
            continue

        if shape_type != 5:
            raise ValueError(f"Unsupported shapefile shape type: {shape_type}")

        num_parts = struct.unpack_from("<i", shp_bytes, offset + 36)[0]
        num_points = struct.unpack_from("<i", shp_bytes, offset + 40)[0]
        parts_offset = offset + 44
        points_offset = parts_offset + num_parts * 4

        part_starts = list(struct.unpack_from(f"<{num_parts}i", shp_bytes, parts_offset))
        points = [
            struct.unpack_from("<2d", shp_bytes, points_offset + point_index * 16)
            for point_index in range(num_points)
        ]

        rings: list[list[tuple[float, float]]] = []
        for part_index, start_index in enumerate(part_starts):
            end_index = part_starts[part_index + 1] if part_index + 1 < num_parts else num_points
            rings.append(points[start_index:end_index])

        records.append(rings)
        offset = record_end

    return records


def load_contiguous_state_shapes(zip_path: Path = ZIP_PATH) -> list[dict[str, object]]:
    with zipfile.ZipFile(zip_path) as archive:
        shp_name = next(name for name in archive.namelist() if name.endswith(".shp"))
        dbf_name = next(name for name in archive.namelist() if name.endswith(".dbf"))
        shp_bytes = archive.read(shp_name)
        dbf_bytes = archive.read(dbf_name)

    shape_records = read_polygon_records(shp_bytes)
    dbf_records = read_dbf_records(dbf_bytes)

    if len(shape_records) != len(dbf_records):
        raise ValueError("Shapefile geometry and attribute record counts do not match")

    state_shapes: list[dict[str, object]] = []
    for attrs, rings in zip(dbf_records, shape_records):
        abbrev = attrs["STUSPS"]
        if abbrev in EXCLUDED_STATES:
            continue
        state_shapes.append(
            {
                "state": attrs["NAME"],
                "abbrev": abbrev,
                "rings": rings,
            }
        )

    if len(state_shapes) != 48:
        raise ValueError(f"Expected 48 contiguous states, found {len(state_shapes)}")

    state_shapes.sort(key=lambda row: row["abbrev"])
    return state_shapes


def load_status_rows(status_csv_path: Path = STATUS_CSV) -> list[dict[str, str]]:
    with status_csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_label_anchors(population_csv_path: Path = POPULATION_CSV) -> dict[str, dict[str, object]]:
    label_anchors: dict[str, dict[str, object]] = {}
    with population_csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            abbrev = row["abbrev"]
            if abbrev in EXCLUDED_STATES:
                continue
            label_anchors[abbrev] = {
                "state": row["name"],
                "longitude": float(row["longitude"]),
                "latitude": float(row["latitude"]),
            }
    return label_anchors


def build_status_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    status_index: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["year_month"], row["abbrev"])
        if key in status_index:
            raise ValueError(f"Duplicate status row for {row['year_month']} / {row['abbrev']}")
        status_index[key] = row
    return status_index


def get_bounds(state_shapes: list[dict[str, object]]) -> tuple[float, float, float, float]:
    min_x = min(point[0] for state in state_shapes for ring in state["rings"] for point in ring)
    min_y = min(point[1] for state in state_shapes for ring in state["rings"] for point in ring)
    max_x = max(point[0] for state in state_shapes for ring in state["rings"] for point in ring)
    max_y = max(point[1] for state in state_shapes for ring in state["rings"] for point in ring)
    return min_x, min_y, max_x, max_y


def build_transform(
    bounds: tuple[float, float, float, float],
    image_size: tuple[int, int] = IMAGE_SIZE,
) -> tuple[float, float, float, float]:
    width, height = image_size
    left_margin = 70
    right_margin = 70
    top_margin = 130
    bottom_margin = 80

    min_x, min_y, max_x, max_y = bounds
    usable_width = width - left_margin - right_margin
    usable_height = height - top_margin - bottom_margin
    scale = min(usable_width / (max_x - min_x), usable_height / (max_y - min_y))

    x_offset = left_margin + (usable_width - (max_x - min_x) * scale) / 2 - min_x * scale
    y_offset = top_margin + (usable_height - (max_y - min_y) * scale) / 2
    return scale, x_offset, y_offset, max_y


def transform_ring(
    ring: list[tuple[float, float]],
    scale: float,
    x_offset: float,
    y_offset: float,
    max_y: float,
) -> list[tuple[int, int]]:
    transformed: list[tuple[int, int]] = []
    for x_value, y_value in ring:
        x_px = int(round(x_offset + x_value * scale))
        y_px = int(round(y_offset + (max_y - y_value) * scale))
        transformed.append((x_px, y_px))
    return transformed


def transform_point(
    x_value: float,
    y_value: float,
    scale: float,
    x_offset: float,
    y_offset: float,
    max_y: float,
) -> tuple[int, int]:
    x_px = int(round(x_offset + x_value * scale))
    y_px = int(round(y_offset + (max_y - y_value) * scale))
    return x_px, y_px


def load_font(size: float | None) -> ImageFont.ImageFont:
    if size is None:
        return ImageFont.load_default()
    return ImageFont.load_default(size=size)


def text_size(font: ImageFont.ImageFont, text: str) -> tuple[int, int]:
    left, top, right, bottom = font.getbbox(text)
    return right - left, bottom - top


def draw_legend(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, image_size: tuple[int, int]) -> None:
    width, _height = image_size
    box_size = 28
    label_gap = 14
    horizontal_margin = 70
    start_y = 55
    label_width = max(text_size(font, "Susceptible")[0], text_size(font, "Infected")[0])
    legend_width = box_size + label_gap + label_width
    start_x = width - horizontal_margin - legend_width
    row_height = max(box_size, text_size(font, "Susceptible")[1]) + 14

    draw.rectangle(
        [start_x, start_y, start_x + box_size, start_y + box_size],
        fill=SUSCEPTIBLE_COLOR,
        outline=LEGEND_OUTLINE_COLOR,
        width=1,
    )
    draw.text(
        (start_x + box_size + label_gap, start_y + box_size / 2),
        "Susceptible",
        fill=TEXT_COLOR,
        font=font,
        anchor="lm",
    )

    second_y = start_y + row_height
    draw.rectangle(
        [start_x, second_y, start_x + box_size, second_y + box_size],
        fill=INFECTED_COLOR,
        outline=LEGEND_OUTLINE_COLOR,
        width=1,
    )
    draw.text(
        (start_x + box_size + label_gap, second_y + box_size / 2),
        "Infected",
        fill=TEXT_COLOR,
        font=font,
        anchor="lm",
    )


def draw_state_labels(
    draw: ImageDraw.ImageDraw,
    state_shapes: list[dict[str, object]],
    status_index: dict[tuple[str, str], dict[str, str]],
    year_month: str,
    label_anchors: dict[str, dict[str, object]],
    scale: float,
    x_offset: float,
    y_offset: float,
    max_y: float,
    font: ImageFont.ImageFont,
) -> None:
    for state in state_shapes:
        row = status_index[(year_month, state["abbrev"])]
        if row["infected"] != "1":
            continue

        anchor = label_anchors.get(state["abbrev"])
        if anchor is None:
            continue

        label_x, label_y = transform_point(
            anchor["longitude"],
            anchor["latitude"],
            scale,
            x_offset,
            y_offset,
            max_y,
        )
        offset_x, offset_y = STATE_LABEL_OFFSETS.get(state["abbrev"], (0, 0))
        draw.text(
            (label_x + offset_x, label_y + offset_y),
            anchor["state"],
            fill=LABEL_TEXT_COLOR,
            font=font,
            anchor="mm",
            stroke_width=1,
            stroke_fill=LABEL_STROKE_COLOR,
        )


def render_month_map(
    state_shapes: list[dict[str, object]],
    status_index: dict[tuple[str, str], dict[str, str]],
    label_anchors: dict[str, dict[str, object]],
    style_config: MapStyleConfig,
    year_month: str,
    seed_state: str,
    output_path: Path,
) -> None:
    image = Image.new("RGB", IMAGE_SIZE, BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    title_font = load_font(style_config.title_font_size)
    subtitle_font = load_font(style_config.subtitle_font_size)
    legend_font = load_font(style_config.legend_font_size)
    label_font = (
        load_font(style_config.state_label_font_size)
        if style_config.show_state_labels and style_config.state_label_font_size is not None
        else None
    )

    bounds = get_bounds(state_shapes)
    scale, x_offset, y_offset, max_y = build_transform(bounds)

    for state in state_shapes:
        row = status_index.get((year_month, state["abbrev"]))
        if row is None:
            raise ValueError(f"Missing status for {state['abbrev']} in {year_month}")

        is_infected = row["infected"] == "1"
        fill_color = INFECTED_COLOR if is_infected else SUSCEPTIBLE_COLOR

        for ring in state["rings"]:
            if len(ring) < 3:
                continue
            transformed_ring = transform_ring(ring, scale, x_offset, y_offset, max_y)
            draw.polygon(transformed_ring, fill=fill_color, outline=STATE_OUTLINE_COLOR)

    if label_font is not None:
        draw_state_labels(
            draw,
            state_shapes,
            status_index,
            year_month,
            label_anchors,
            scale,
            x_offset,
            y_offset,
            max_y,
            label_font,
        )

    title = f"Influenza Spread Simulation - {year_month} - Seed: {seed_state}"
    subtitle = "Contiguous 48-state cohort"
    title_x = 70
    title_y = 45
    title_height = text_size(title_font, title)[1]
    subtitle_y = title_y + title_height + 10
    draw.text((title_x, title_y), title, fill=TEXT_COLOR, font=title_font)
    draw.text((title_x, subtitle_y), subtitle, fill=TEXT_COLOR, font=subtitle_font)
    draw_legend(draw, legend_font, IMAGE_SIZE)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def generate_infection_maps(
    status_csv_path: Path = STATUS_CSV,
    zip_path: Path = ZIP_PATH,
    output_dir: Path = OUTPUT_DIR,
    map_style: str = "infection",
) -> list[Path]:
    style_config = MAP_STYLE_CONFIGS.get(map_style)
    if style_config is None:
        raise ValueError(f"Unsupported map style: {map_style}")

    rows = load_status_rows(status_csv_path)
    if not rows:
        raise ValueError("Status CSV is empty")

    state_shapes = load_contiguous_state_shapes(zip_path)
    label_anchors = load_label_anchors()
    status_index = build_status_index(rows)
    year_months = sorted({row["year_month"] for row in rows})
    seed_state = rows[0]["seed_state"]

    output_paths: list[Path] = []
    for year_month in year_months:
        fname = f"{style_config.map_name}_{year_month}.png"
        output_path = output_dir / fname
        render_month_map(
            state_shapes,
            status_index,
            label_anchors,
            style_config,
            year_month,
            seed_state,
            output_path,
        )
        output_paths.append(output_path)

    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Render US influenza infection maps")
    parser.add_argument(
        "--mode",
        choices=["predict", "validate"],
        default="predict",
        help="Data mode: predict = state_infection_status.csv, validate = state_infection_validation.csv",
    )

    args = parser.parse_args()

    if args.mode == "validate":
        status_csv_path = Path("outputs") / "state_infection_validation.csv"
        map_style = "validation"
    else:
        status_csv_path = Path("outputs") / "state_infection_status.csv"
        map_style = "infection"

    print(f"Running US_plot in mode='{args.mode}', status CSV='{status_csv_path}'")

    output_paths = generate_infection_maps(status_csv_path=status_csv_path, map_style=map_style)
    for path in output_paths:
        print(f"Saved map to {path}")


if __name__ == "__main__":
    main()
