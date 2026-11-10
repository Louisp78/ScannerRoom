#!/usr/bin/env python3
"""Bake Natural Earth bathymetry bands into an equirectangular depth-index PNG.

Output pixel value = depth band index x SCALE: 0 = land, 1 = 0-200 m,
2 = 200-1000 m, ..., 12 = deeper than 10 000 m. The ocean index is smoothed then
rounded back to whole bands (land stays crisp), so that the fragmented
abyssal-plain polygons merge into continuous contours instead of speckle.
SCALE makes each band step large: GPUs filter 8-bit textures at 8-bit precision,
and a 1-code step would render as texel-sized terraces. The globe shader colours
the bands, so this script only carries data, never styling.

Usage: bake-bathymetry.py [output.png]   (default: public/geo/bathymetry.png)
"""

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 8192, 4096  # ~5 km/px: past this, Natural Earth adds no detail
SCALE = 20  # 12 bands x 20 fits in 8 bits
BLUR_RADIUS = 2  # px, ~10 km at the equator
BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"
# Shallowest first: each band is a polygon set covering everything deeper than its
# depth, so painting them in order leaves each pixel with its deepest band.
BANDS = ["L_0", "K_200", "J_1000", "I_2000", "H_3000", "G_4000",
         "F_5000", "E_6000", "D_7000", "C_8000", "B_9000", "A_10000"]

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent.parent / "natural-earth"


def fetch(band: str) -> dict:
    path = CACHE / f"ne_10m_bathymetry_{band}.geojson"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"downloading {path.name}", file=sys.stderr)
        urllib.request.urlretrieve(f"{BASE_URL}/{path.name}", path)
    return json.loads(path.read_text())


def to_pixels(ring: list) -> list[tuple[float, float]]:
    return [((lon + 180) / 360 * WIDTH, (90 - lat) / 180 * HEIGHT) for lon, lat, *_ in ring]


def rasterize(collection: dict) -> np.ndarray:
    mask = Image.new("1", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(mask)
    for feature in collection["features"]:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"]
        if geometry["type"] == "Polygon":
            polygons = [polygons]
        for exterior, *holes in polygons:
            draw.polygon(to_pixels(exterior), fill=1)
            for hole in holes:
                draw.polygon(to_pixels(hole), fill=0)
    return np.asarray(mask, dtype=bool)


def box_blur(values: np.ndarray, radius: int) -> np.ndarray:
    """Box blur, wrapping across the antimeridian and clamping at the poles."""
    size = 2 * radius + 1
    padded = np.pad(values, ((0, 0), (radius, radius)), mode="wrap")
    sums = np.cumsum(np.pad(padded, ((0, 0), (1, 0))), axis=1)
    values = (sums[:, size:] - sums[:, :-size]) / size
    padded = np.pad(values, ((radius, radius), (0, 0)), mode="edge")
    sums = np.cumsum(np.pad(padded, ((1, 0), (0, 0))), axis=0)
    return (sums[size:] - sums[:-size]) / size


def smooth_ocean(depth: np.ndarray) -> np.ndarray:
    """Gaussian-like blur of the ocean only (normalised so land does not leak in)."""
    ocean = (depth > 0).astype(np.float64)
    values, weights = depth * ocean, ocean
    for _ in range(3):  # three box passes approximate a gaussian
        values, weights = box_blur(values, BLUR_RADIUS), box_blur(weights, BLUR_RADIUS)
    smoothed = np.divide(values, weights, out=np.zeros_like(values), where=weights > 0)
    return np.where(ocean > 0, np.clip(smoothed, 1, len(BANDS)), 0)


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "public" / "geo" / "bathymetry.png"
    depth = np.zeros((HEIGHT, WIDTH), dtype=np.float64)
    for index, band in enumerate(BANDS, start=1):
        depth[rasterize(fetch(band))] = index
    encoded = (np.rint(smooth_ocean(depth)) * SCALE).astype(np.uint8)
    Image.fromarray(encoded, mode="L").save(output, optimize=True)
    print(f"{output} ({output.stat().st_size // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
