"""
Geocoding and routing utilities using Google Maps Platform APIs.
- Geocoding API: converts addresses to lat/long coordinates
- Distance Matrix API: computes real driving distances between coordinates
- Directions API: computes the actual driving route geometry (polyline)

Requires a Google Maps API key with Geocoding, Distance Matrix, and Directions APIs enabled.
Set it in the .env file as GOOGLE_MAPS_API_KEY.
"""
import urllib.request
import urllib.parse
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


def geocode_address(address):
    """
    Convert a street address to (latitude, longitude) using Google Geocoding API.
    Returns None if the address cannot be found.
    """
    params = urllib.parse.urlencode({
        'address': address,
        'key': API_KEY,
    })
    url = f"{GEOCODE_URL}?{params}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if data['status'] == 'OK' and data['results']:
                loc = data['results'][0]['geometry']['location']
                return loc['lat'], loc['lng']
            else:
                print(f"Geocoding error for '{address}': {data.get('status', 'unknown')}")
    except Exception as e:
        print(f"Geocoding error for '{address}': {e}")
    return None


def geocode_addresses(addresses):
    """
    Geocode a list of addresses. Returns list of (lat, lng) tuples.
    Google Maps API is fast — no rate limit delay needed (unlike Nominatim).
    """
    coords = []
    for addr in addresses:
        result = geocode_address(addr)
        if result:
            coords.append(result)
        else:
            coords.append(None)
    return coords


def get_distance_matrix(coords):
    """
    Get driving distance matrix using Google Distance Matrix API.
    coords: list of (lat, lng) tuples
    Returns 2D list where matrix[i][j] = driving distance in meters.

    Google limits 100 elements per request (origins x destinations).
    For n locations, we need n x n = n^2 elements.
    We batch the requests: send 10 origins at a time to stay under the limit.
    """
    n = len(coords)
    if n > 100:
        print("Too many locations for Distance Matrix API (max 100)")
        return None

    # Build pipe-separated coordinate strings
    locations = [f"{lat},{lng}" for lat, lng in coords]

    # Google allows max 25 destinations per request
    # And max 100 elements (origins x destinations) per request
    # We batch both origins and destinations to stay within limits
    max_destinations = min(25, n)
    batch_size = min(max_destinations, max(1, 100 // n))

    matrix = [[0] * n for _ in range(n)]

    # Batch both origins and destinations to stay within Google's limits:
    # - Max 25 origins per request
    # - Max 25 destinations per request
    # - Max 100 elements (origins x destinations) per request
    dest_batch_size = min(25, n)
    origin_batch_size = min(25, max(1, 100 // dest_batch_size))

    for origin_start in range(0, n, origin_batch_size):
        origin_end = min(origin_start + origin_batch_size, n)
        batch_origins = locations[origin_start:origin_end]

        for dest_start in range(0, n, dest_batch_size):
            dest_end = min(dest_start + dest_batch_size, n)
            batch_dests = locations[dest_start:dest_end]

            origins_str = "|".join(batch_origins)
            destinations_str = "|".join(batch_dests)

            params = urllib.parse.urlencode({
                'origins': origins_str,
                'destinations': destinations_str,
                'key': API_KEY,
                'units': 'metric',
            })
            url = f"{DISTANCE_MATRIX_URL}?{params}"

            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read().decode())
                    if data['status'] != 'OK':
                        print(f"Distance Matrix API error: {data.get('status')} - {data.get('error_message', '')}")
                        return None

                    # Fill in the matrix rows for this batch
                    for i, row in enumerate(data['rows']):
                        row_idx = origin_start + i
                        for j, element in enumerate(row['elements']):
                            col_idx = dest_start + j
                            if element['status'] == 'OK':
                                matrix[row_idx][col_idx] = element['distance']['value']
                            else:
                                matrix[row_idx][col_idx] = 0
            except Exception as e:
                print(f"Google Distance Matrix API error: {e}")
                return None

    return matrix


def get_route_geometry(coords, route_order):
    """
    Get the actual driving path (polyline) using Google Directions API.
    coords: list of (lat, lng) tuples
    route_order: list of indices in the order to visit
    Returns list of [lat, lng] points representing the driving path.

    Google Directions API allows up to 25 waypoints (plus origin/destination) per request.
    For routes with more than 25 stops, we split into multiple segments and concatenate.
    """
    if len(route_order) <= 1:
        return None

    # Order coordinates by route_order (skip the last index if it's a return-to-start)
    if route_order[-1] == route_order[0]:
        ordered_indices = route_order[:-1]
    else:
        ordered_indices = route_order

    ordered_coords = [coords[i] for i in ordered_indices]
    n = len(ordered_coords)

    # Google allows max 25 waypoints per request (plus origin + destination = 27 stops)
    max_stops_per_request = 25

    all_points = []

    # If route fits in a single request, do it the simple way
    if n <= max_stops_per_request + 2:
        points = _fetch_directions_segment(ordered_coords)
        if points:
            all_points.extend(points)
    else:
        # Split into multiple segments, overlapping at endpoints
        # Each segment: origin + 25 waypoints + destination
        # But we overlap by 1 (destination of segment i = origin of segment i+1)
        segment_size = max_stops_per_request + 1  # origin + 25 waypoints

        for start in range(0, n, segment_size - 1):
            end = min(start + segment_size, n)
            segment = ordered_coords[start:end]

            points = _fetch_directions_segment(segment)
            if points:
                # Avoid duplicating the first point of subsequent segments
                if start > 0 and all_points and points:
                    points = points[1:]
                all_points.extend(points)

            if end >= n:
                break

    return all_points if all_points else None


def _fetch_directions_segment(segment_coords):
    """
    Fetch directions for a single segment (max 27 stops: origin + 25 waypoints + destination).
    Returns list of [lat, lng] points, or None on error.
    """
    if len(segment_coords) <= 1:
        return None

    origin = f"{segment_coords[0][0]},{segment_coords[0][1]}"
    destination = f"{segment_coords[-1][0]},{segment_coords[-1][1]}"
    waypoints = "|".join([
        f"{c[0]},{c[1]}" for c in segment_coords[1:-1]
    ]) if len(segment_coords) > 2 else ""

    params = {
        'origin': origin,
        'destination': destination,
        'key': API_KEY,
    }
    if waypoints:
        params['waypoints'] = waypoints
        params['optimize_waypoints'] = 'false'  # We already optimized

    url = f"{DIRECTIONS_URL}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            if data['status'] == 'OK' and data['routes']:
                points = decode_polyline(data['routes'][0]['overview_polyline']['points'])
                return points
            else:
                print(f"Directions API error: {data.get('status')} - {data.get('error_message', '')}")
    except Exception as e:
        print(f"Google Directions API error: {e}")
    return None


def decode_polyline(polyline_str):
    """
    Decode a Google Maps encoded polyline string into a list of [lat, lng] points.
    Uses the Google polyline encoding algorithm.
    """
    index = 0
    lat = 0
    lng = 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    while index < len(polyline_str):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        changes['latitude'] += ~(result >> 1) if (result & 1) else (result >> 1)
        lat = changes['latitude'] / 100000.0

        # Decode longitude
        shift = 0
        result = 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1f) << shift
            shift += 5
            if byte < 0x20:
                break
        changes['longitude'] += ~(result >> 1) if (result & 1) else (result >> 1)
        lng = changes['longitude'] / 100000.0

        coordinates.append([lat, lng])

    return coordinates