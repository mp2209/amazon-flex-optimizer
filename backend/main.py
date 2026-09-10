"""
FastAPI backend for the Amazon Flex Route Optimizer.
Handles:
- Geocoding addresses via Google Maps Geocoding API
- Computing driving distance matrix via Google Distance Matrix API
- Running TSP algorithms (brute force, nearest neighbor, 2-opt, OR-Tools)
- Returning optimized routes with map geometry from Google Directions API
"""
import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from algorithms import (
    solve_brute_force,
    solve_nearest_neighbor,
    solve_2opt,
    solve_ortools,
    calculate_route_distance,
)
from osm_utils import geocode_addresses, get_distance_matrix, get_route_geometry

load_dotenv()

# CORS: allow the deployed frontend (Vercel) to call this API.
# For local development, http://localhost:5500 (VS Code Live Server) and
# the local static file origin are also allowed.
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://localhost:5001",
    "http://127.0.0.1:5500",
    "https://amazon-flex-optimizer.vercel.app",  # TODO: replace with your real Vercel domain
]

app = FastAPI(title="Amazon Flex Route Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class OptimizeRequest(BaseModel):
    start: str = ""
    stops: list[str] = Field(default_factory=list)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "amazon-flex-route-optimizer-api"}


@app.post("/optimize")
def optimize(req: OptimizeRequest):
    """
    Main endpoint: takes addresses, returns optimized routes from all algorithms.

    Request JSON:
    {
        "start": "123 Main St, Atlanta, GA",
        "stops": ["456 Oak Ave, Atlanta, GA", "789 Pine St, Atlanta, GA", ...]
    }

    Response JSON:
    {
        "coordinates": [[lat, lon], ...],
        "algorithms": {
            "nearest_neighbor": {
                "route": [0, 2, 1, 3],
                "distance_m": 12345.6,
                "distance_mi": 7.67,
                "time_ms": 5,
                "geometry": [[lat, lon], ...]
            },
            ...
        }
    }
    """
    start_address = req.start.strip()
    stop_addresses = req.stops

    if not start_address or not stop_addresses:
        return {"error": "Start address and at least one stop are required."}

    if len(stop_addresses) > 40:
        return {"error": "Maximum 40 stops supported for demo."}

    # Step 1: Geocode all addresses (start + stops)
    all_addresses = [start_address] + stop_addresses
    coords = geocode_addresses(all_addresses)

    # Check for geocoding failures
    failed = [addr for addr, coord in zip(all_addresses, coords) if coord is None]
    if failed:
        return {"error": f"Could not find these addresses: {', '.join(failed)}"}

    # Step 2: Get driving distance matrix from Google Distance Matrix API
    distance_matrix = get_distance_matrix(coords)
    if distance_matrix is None:
        return {"error": "Could not compute driving distances. Try again."}

    # Step 3: Run all algorithms and measure performance
    results = {}
    algorithms = {
        "nearest_neighbor": solve_nearest_neighbor,
        "2opt": solve_2opt,
        "ortools": solve_ortools,
    }

    # Only run brute force for small inputs (n <= 8)
    if len(all_addresses) <= 8:
        algorithms["brute_force"] = solve_brute_force

    # Add "original" route (the order the user entered, no optimization, no return to start)
    original_route = list(range(len(all_addresses)))
    original_distance = calculate_route_distance(original_route, distance_matrix)
    original_geometry = get_route_geometry(coords, original_route)
    results["original"] = {
        "route": original_route,
        "distance_m": original_distance,
        "distance_mi": round(original_distance * 0.000621371, 2),
        "time_ms": 0,
        "geometry": original_geometry,
    }

    for name, solver in algorithms.items():
        start_time = time.time()
        route = solver(distance_matrix, start_index=0)
        elapsed_ms = (time.time() - start_time) * 1000
        distance = calculate_route_distance(route, distance_matrix)

        # Get actual driving path geometry from Google Directions API
        geometry = get_route_geometry(coords, route)

        results[name] = {
            "route": route,
            "distance_m": distance,
            "distance_mi": round(distance * 0.000621371, 2),
            "time_ms": round(elapsed_ms, 2),
            "geometry": geometry,
        }

    # Step 4: Return everything
    return {
        "coordinates": coords,
        "addresses": all_addresses,
        "algorithms": results,
    }