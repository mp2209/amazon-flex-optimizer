#!/usr/bin/env python3
"""Count the Google Maps requests one /optimize call makes, without calling Google.

Runs the backend's real geocode / Distance Matrix / Directions code against
a stubbed network layer that records every request URL, then reports
requests per API and the largest request against Google's per-request
limits (100 elements, 25 origins, 25 destinations, 25 waypoints).

    python3 bench/api_calls.py
"""
import io
import json
import math
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import osm_utils  # noqa: E402

SIZES = [7, 15, 25, 40]
calls = []


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else req
    base, query = url.split("?", 1)
    q = dict(urllib.parse.parse_qsl(query))
    if base == osm_utils.GEOCODE_URL:
        calls.append(("geocode", {}))
        body = {"status": "OK", "results": [{"geometry": {"location": {"lat": 33.75, "lng": -84.39}}}]}
    elif base == osm_utils.DISTANCE_MATRIX_URL:
        o, d = len(q["origins"].split("|")), len(q["destinations"].split("|"))
        calls.append(("distance_matrix", {"origins": o, "destinations": d, "elements": o * d}))
        body = {"status": "OK", "rows": [{"elements": [{"status": "OK", "distance": {"value": 1}}] * d}] * o}
    elif base == osm_utils.DIRECTIONS_URL:
        w = len(q["waypoints"].split("|")) if "waypoints" in q else 0
        calls.append(("directions", {"waypoints": w}))
        body = {"status": "OK", "routes": [{"overview_polyline": {"points": "_p~iF~ps|U"}}]}
    else:
        raise AssertionError(url)
    return _Resp(json.dumps(body).encode())


osm_utils.urllib.request.urlopen = fake_urlopen


def optimize_calls(k):
    """Mirror main.optimize: geocode, one matrix, one Directions route per solver."""
    calls.clear()
    n = k + 1
    coords = osm_utils.geocode_addresses([f"stop {i}" for i in range(n)])
    osm_utils.get_distance_matrix(coords)
    routes = 1 + 3 + (1 if n <= 8 else 0)  # entered order + NN, 2-opt, OR-Tools (+ brute force)
    for _ in range(routes):
        osm_utils.get_route_geometry(coords, list(range(n)))
    out = {"stops": k, "locations": n}
    for api in ("geocode", "distance_matrix", "directions"):
        out[api] = sum(1 for a, _ in calls if a == api)
    dm = [c for a, c in calls if a == "distance_matrix"]
    out["matrix_elements"] = sum(c["elements"] for c in dm)
    out["max_elements"] = max(c["elements"] for c in dm)
    out["max_origins"] = max(c["origins"] for c in dm)
    out["max_destinations"] = max(c["destinations"] for c in dm)
    out["max_waypoints"] = max(c["waypoints"] for a, c in calls if a == "directions")
    out["total_requests"] = len(calls)
    out["matrix_requests_unbatched_min"] = math.ceil(n * n / 100)
    return out


def main():
    rows = [optimize_calls(k) for k in SIZES]
    for r in rows:
        assert r["max_elements"] <= 100 and r["max_origins"] <= 25 and r["max_destinations"] <= 25
        assert r["max_waypoints"] <= 25
    out = os.path.join(ROOT, "bench", "results", "api_calls.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(rows, open(out, "w"), indent=1)
    print(f"{'stops':>5} {'geocode':>8} {'matrix':>7} {'elements':>9} {'max/req':>8} {'directions':>11} {'max wp':>7} {'total':>6}")
    for r in rows:
        print(f"{r['stops']:>5} {r['geocode']:>8} {r['distance_matrix']:>7} {r['matrix_elements']:>9} "
              f"{r['max_elements']:>8} {r['directions']:>11} {r['max_waypoints']:>7} {r['total_requests']:>6}")


if __name__ == "__main__":
    main()
