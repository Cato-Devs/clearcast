"""Builds app/nairobi_constituencies.geojson, the boundaries for the map.

Source: geoBoundaries gbOpen KEN ADM2 (IEBC, OCHA ROSEA; CC BY 3.0 IGO).

The source still uses two older names, so they are renamed to the current constituencies:
    Kilimani  -> Dagoretti North (Kilimani is one of its wards)
    Dagoretti -> Dagoretti South (the western part of the old Dagoretti constituency)

Run from the ml-service folder:
    python tools/build_nairobi_boundaries.py
"""
import json
from pathlib import Path

import requests

try:
    import truststore  # same certificate fix as training/fetch_historical.py

    truststore.inject_into_ssl()
except ImportError:
    pass

SOURCE_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/KEN/ADM2/"
    "geoBoundaries-KEN-ADM2_simplified.geojson"
)
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "nairobi_constituencies.geojson"

# Name in the source -> name ClearCast uses
NAMES = {
    "Westlands": "Westlands",
    "Kilimani": "Dagoretti North",
    "Dagoretti": "Dagoretti South",
    "Langata": "Lang'ata",
    "Kibra": "Kibra",
    "Roysambu": "Roysambu",
    "Kasarani": "Kasarani",
    "Ruaraka": "Ruaraka",
    "Embakasi South": "Embakasi South",
    "Embakasi North": "Embakasi North",
    "Embakasi Central": "Embakasi Central",
    "Embakasi East": "Embakasi East",
    "Embakasi West": "Embakasi West",
    "Makadara": "Makadara",
    "Kamukunji": "Kamukunji",
    "Starehe": "Starehe",
    "Mathare": "Mathare",
}


def centroid(geometry):
    """Area-weighted centre of a polygon's outer ring(s), as (lat, lon)."""
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    area = x_sum = y_sum = 0.0
    for polygon in polygons:
        ring = polygon[0]
        for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
            cross = x0 * y1 - x1 * y0
            area += cross
            x_sum += (x0 + x1) * cross
            y_sum += (y0 + y1) * cross
    return y_sum / (3 * area), x_sum / (3 * area)


def main():
    response = requests.get(SOURCE_URL, timeout=120)
    response.raise_for_status()
    source = {f["properties"]["shapeName"]: f for f in response.json()["features"]}

    missing = [name for name in NAMES if name not in source]
    if missing:
        raise SystemExit(f"Not found in the source: {missing}")

    features = [
        {"type": "Feature", "properties": {"name": name}, "geometry": source[source_name]["geometry"]}
        for source_name, name in NAMES.items()
    ]
    OUTPUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print(f"Saved {len(features)} constituencies to {OUTPUT}\n")
    for feature in features:
        lat, lon = centroid(feature["geometry"])
        print(f'    {{"name": "{feature["properties"]["name"]}", "lat": {lat:.5f}, "lon": {lon:.5f}}},')


if __name__ == "__main__":
    main()
