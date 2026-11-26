#!/usr/bin/env python3
"""Fetch real driving distances for the benchmark, once.

Geocodes every place in bench/places.txt and fetches the full driving
distance matrix between them with the backend's own Google Maps code (the
same batching the app uses). Writes bench/data/atlanta.json. Every benchmark
run after this is offline.

Needs GOOGLE_MAPS_API_KEY in backend/.env. For 41 places this is 41
geocodes and 1,681 Distance Matrix elements in 22 requests.

    make bench-fetch
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from osm_utils import geocode_addresses, get_distance_matrix  # noqa: E402

PLACES = os.path.join(ROOT, "bench", "places.txt")
OUT = os.path.join(ROOT, "bench", "data", "atlanta.json")


def main():
    if os.path.exists(OUT) and "--force" not in sys.argv:
        sys.exit(f"{OUT} already exists; pass --force to fetch again (costs API quota).")

    with open(PLACES) as f:
        places = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    coords = geocode_addresses(places)
    missing = [p for p, c in zip(places, coords) if c is None]
    if missing:
        sys.exit(f"Could not geocode: {missing}")

    matrix = get_distance_matrix(coords)
    if matrix is None:
        sys.exit("Distance Matrix request failed")

    # The backend writes 0 for any pair Google can't route; flag those.
    zeros = [(i, j) for i in range(len(places)) for j in range(len(places))
             if i != j and matrix[i][j] == 0]
    if zeros:
        sys.exit(f"{len(zeros)} unroutable pairs, e.g. {zeros[:5]}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({
            "source": "Google Maps Geocoding + Distance Matrix APIs (driving, metric)",
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "places": places,
            "coords": [list(c) for c in coords],
            "distance_m": matrix,
        }, f)
    print(f"Wrote {OUT}: {len(places)} places, {len(places) ** 2} matrix elements")


if __name__ == "__main__":
    main()
