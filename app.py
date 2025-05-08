"""
Flask backend for the Amazon Flex Route Optimizer.
Handles:
- Geocoding addresses via Google Maps Geocoding API
- Computing driving distance matrix via Google Distance Matrix API
- Running TSP algorithms (brute force, nearest neighbor, 2-opt, simulated annealing, OR-Tools)
- Returning optimized routes with map geometry from Google Directions API
"""
from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv
import time
from algorithms import (
    solve_brute_force,
    solve_nearest_neighbor,
    solve_2opt,
    solve_simulated_annealing,
    solve_ortools,
    calculate_route_distance,
)
from osm_utils import geocode_addresses, get_distance_matrix, get_route_geometry

load_dotenv()
app = Flask(__name__)


@app.route('/')
def index():
    """Render the main page with Google Maps API key for tiles."""
    return render_template('index.html', google_maps_api_key=os.getenv('GOOGLE_MAPS_API_KEY', ''))


@app.route('/optimize', methods=['POST'])
def optimize():
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
                "route": [0, 2, 1, 3, 0],
                "distance": 12345.6,
                "time_ms": 5,
                "geometry": [[lat, lon], ...]
            },
            ...
        }
    }
    """
    data = request.get_json()
    start_address = data.get('start', '').strip()
    stop_addresses = data.get('stops', [])

    if not start_address or not stop_addresses:
        return jsonify({'error': 'Start address and at least one stop are required.'}), 400

    if len(stop_addresses) > 40:
        return jsonify({'error': 'Maximum 40 stops supported for demo.'}), 400

    # Step 1: Geocode all addresses (start + stops)
    all_addresses = [start_address] + stop_addresses
    coords = geocode_addresses(all_addresses)

    # Check for geocoding failures
    failed = [addr for addr, coord in zip(all_addresses, coords) if coord is None]
    if failed:
        return jsonify({
            'error': f'Could not find these addresses: {", ".join(failed)}'
        }), 400

    # Step 2: Get driving distance matrix from OSRM
    distance_matrix = get_distance_matrix(coords)
    if distance_matrix is None:
        return jsonify({'error': 'Could not compute driving distances. Try again.'}), 500

    # Step 3: Run all algorithms and measure performance
    results = {}
    algorithms = {
        'nearest_neighbor': solve_nearest_neighbor,
        '2opt': solve_2opt,
        'simulated_annealing': solve_simulated_annealing,
        'ortools': solve_ortools,
    }

    # Only run brute force for small inputs (n <= 8)
    if len(all_addresses) <= 8:
        algorithms['brute_force'] = solve_brute_force

    # Add "original" route (the order the user entered, no optimization, no return to start)
    original_route = list(range(len(all_addresses)))
    original_distance = calculate_route_distance(original_route, distance_matrix)
    original_geometry = get_route_geometry(coords, original_route)
    results['original'] = {
        'route': original_route,
        'distance_m': original_distance,
        'distance_mi': round(original_distance * 0.000621371, 2),
        'time_ms': 0,
        'geometry': original_geometry,
    }

    for name, solver in algorithms.items():
        start_time = time.time()
        route = solver(distance_matrix, start_index=0)
        elapsed_ms = (time.time() - start_time) * 1000
        distance = calculate_route_distance(route, distance_matrix)

        # Get actual driving path geometry from OSRM
        geometry = get_route_geometry(coords, route)

        results[name] = {
            'route': route,
            'distance_m': distance,
            'distance_mi': round(distance * 0.000621371, 2),
            'time_ms': round(elapsed_ms, 2),
            'geometry': geometry,
        }

    # Step 4: Return everything
    return jsonify({
        'coordinates': coords,
        'addresses': all_addresses,
        'algorithms': results,
    })


if __name__ == '__main__':
    app.run(debug=True, port=5001)