# Amazon Flex Route Optimizer

A web application that optimizes delivery routes for Amazon Flex drivers using multiple TSP (Traveling Salesman Problem) algorithms, visualized on an interactive Google Maps map.

## Features

- **Address input** — Enter a starting point (warehouse/home) and up to 35 delivery stops, or upload a CSV
- **Google Maps integration** — Real geocoding, driving distances, and route geometry via Google Maps Platform APIs
- **Interactive map** — Leaflet.js with Google Maps tiles, custom package markers, route polyline
- **5 TSP algorithms:**
  - Brute force (optimal but O(n!) — only for ≤8 stops)
  - Nearest neighbor (greedy heuristic, O(n²))
  - 2-opt local search (improves nearest neighbor with edge swaps)
  - Simulated annealing (probabilistic optimization)
  - Google OR-Tools (industry-standard constraint programming solver)
- **Original route comparison** — See how much you save vs. the order you entered
- **Open TSP** — Route ends at the last stop instead of returning to the warehouse, saving unnecessary driving
- **Algorithm comparison** — Bar chart comparing distance and computation time
- **Shift summary** — Total distance, estimated drive time, gas savings
- **Click-to-navigate** — Click any stop in the delivery order list to zoom to it on the map
- **Segment view** — Clicking a stop shows only the route segment from that stop to the next, centered on screen; a "Show full route" button restores the complete view
- **Marker separation** — Stops that are geographically close are automatically spread apart on the map so none are hidden behind another
- **Dark/Light theme** — Toggle between themes, saved across sessions
- **Amazon Flex-style UI** — Navy/orange color scheme, "Package 1, 2, 3..." labels

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python + Flask |
| Algorithms | Custom Python implementations + Google OR-Tools |
| Map | Leaflet.js + Google Maps tiles |
| Geocoding | Google Maps Geocoding API |
| Distance Matrix | Google Maps Distance Matrix API |
| Route Geometry | Google Maps Directions API |
| Charts | Chart.js |
| Styling | Custom CSS (Amazon Flex theme + dark mode) |

## Setup

### Prerequisites

1. A Google Maps API key with these APIs enabled:
   - Geocoding API
   - Distance Matrix API
   - Directions API
   - Maps JavaScript API (for map tiles)

2. Create a `.env` file in the project root:
```
GOOGLE_MAPS_API_KEY=your_api_key_here
```

### Install & Run

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py

# 4. Open in browser
# Go to http://localhost:5001
```

## How to Use

1. Enter your starting address (e.g., "123 Main St, Atlanta, GA")
2. Enter delivery stops (one address per line, up to 35) or upload a CSV
3. Click "Optimize Route"
4. View the optimized route on the map with all stops marked
5. Switch between algorithms using the dropdown to compare results
6. Click any stop in the "Delivery Order" list to zoom to it on the map
7. Click a stop to see the **Next Stop panel** with the route segment from that stop to the next one highlighted on the map; click "Show full route" to return to the complete view
8. Check the shift summary for distance, time, and gas savings
9. Toggle dark/light theme with the button in the header

## CSV Format

```csv
123 Main St, Atlanta, GA
456 Oak Ave, Atlanta, GA
789 Pine St, Atlanta, GA
321 Elm Dr, Atlanta, GA
```

First line = starting point, remaining lines = delivery stops.

## Theoretical Background

The Traveling Salesman Problem (TSP) asks: *given a list of locations and distances between them, what is the shortest possible route that visits each location exactly once and returns to the origin?*

TSP is **NP-complete**, proven by reduction from the Hamiltonian Cycle problem. This means:
- **Brute force** checks all n! permutations — works for n ≤ 10 but becomes infeasible
- **Heuristics** (nearest neighbor, 2-opt, simulated annealing) trade optimality for speed
- **OR-Tools** uses constraint programming with guided local search — the industry-standard approach

This project solves the **open TSP variant**: the route starts at the warehouse and ends at the last delivery stop without returning to the warehouse, which better models a real Amazon Flex shift.

This project demonstrates that tradeoff in practice: brute force finds the optimal route for small inputs, while heuristics and OR-Tools scale to larger problems with good (but not perfect) solutions.

## APIs Used

- **Google Maps Geocoding API** — Converts addresses to lat/long coordinates
- **Google Maps Distance Matrix API** — Computes real driving distances between all stops (batched to respect API limits)
- **Google Maps Directions API** — Returns the actual driving route geometry (polyline), split into segments for routes with 25+ stops

All require a Google Maps API key set in the `.env` file.

## Project Structure

```
amazon-flex-optimizer/
├── app.py                  # Flask backend
├── osm_utils.py            # Google Maps API utilities (geocoding, distance matrix, directions)
├── .env                    # Google Maps API key (not committed)
├── .gitignore
├── requirements.txt
├── algorithms/
│   ├── __init__.py
│   ├── base.py             # Shared utilities (route distance calculation)
│   ├── brute_force.py      # O(n!) optimal solver (≤8 stops)
│   ├── nearest_neighbor.py # O(n²) greedy heuristic
│   ├── two_opt.py          # Local search improvement
│   ├── simulated_annealing.py  # Probabilistic metaheuristic
│   └── ortools_solver.py   # Google OR-Tools constraint programming solver
├── static/
│   ├── style.css           # Amazon Flex theme + dark mode + next-stop panel
│   └── app.js              # Frontend logic, Leaflet map, segment view, marker separation
└── templates/
    └── index.html          # Main page with theme toggle + next-stop panel
```