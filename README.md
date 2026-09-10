# Amazon Flex Route Optimizer

A web application that optimizes delivery routes for Amazon Flex drivers using multiple TSP (Traveling Salesman Problem) algorithms, visualized on an interactive map.

**Architecture:** Decoupled frontend + backend.
- **Frontend** — static site (HTML/CSS/JS + Leaflet.js), deployed on Vercel
- **Backend** — FastAPI (containerized with Docker), deployed on AWS EC2
- **Google Maps Platform APIs** — geocoding, driving distances, route geometry

## Features

- **Address input** — Enter a starting point (warehouse/home) and up to 40 delivery stops, or upload a CSV
- **Google Maps integration** — Real geocoding, driving distances, and route geometry via Google Maps Platform APIs
- **Interactive map** — Leaflet.js with Google Maps tiles, custom package markers, route polyline
- **4 TSP algorithms:**
  - Brute force (optimal but O(n!) — only for ≤8 stops)
  - Nearest neighbor (greedy heuristic, O(n²))
  - 2-opt local search (improves nearest neighbor with edge swaps)
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
|-----------|------------|
| Backend | Python + FastAPI, Uvicorn |
| Algorithms | Custom Python implementations + Google OR-Tools |
| Container | Docker |
| Frontend hosting | Vercel (static) |
| Backend hosting | AWS EC2 |
| Map | Leaflet.js + Google Maps tiles |
| Geocoding | Google Maps Geocoding API |
| Distance Matrix | Google Maps Distance Matrix API |
| Route Geometry | Google Maps Directions API |
| Charts | Chart.js |
| Styling | Custom CSS (Amazon Flex theme + dark mode) |

## Project Structure

```
amazon-flex-optimizer/
├── backend/                     # FastAPI backend (Docker → AWS EC2)
│   ├── Dockerfile
│   ├── main.py                  # FastAPI app: /optimize endpoint + CORS
│   ├── requirements.txt
│   ├── osm_utils.py             # Google Maps API utilities (geocoding, distance matrix, directions)
│   └── algorithms/
│       ├── __init__.py
│       ├── base.py              # Shared utilities (route distance calculation)
│       ├── brute_force.py       # O(n!) optimal solver (≤8 stops)
│       ├── nearest_neighbor.py  # O(n²) greedy heuristic
│       ├── two_opt.py           # Local search improvement
│       └── ortools_solver.py    # Google OR-Tools constraint programming solver
└── frontend/                    # Static site (→ Vercel)
    ├── index.html               # Main page with theme toggle + next-stop panel
    ├── app.js                   # Frontend logic, Leaflet map, segment view, marker separation
    ├── style.css               # Amazon Flex theme + dark mode + next-stop panel
    └── vercel.json
```

## Setup

### Prerequisites

1. A Google Maps API key with these APIs enabled:
   - Geocoding API
   - Distance Matrix API
   - Directions API
   - Maps JavaScript API (for map tiles)

2. **Use two separate API keys** (important for a public deployment):
   - **Server key** — used by the backend for Geocoding / Distance Matrix / Directions. Restrict by the EC2 instance's IP address. Never exposed to the browser.
   - **Browser key** — used by the frontend only for map tiles. Restrict by HTTP referrer (your Vercel domain).

### Backend (local)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env in backend/ with your SERVER key:
echo "GOOGLE_MAPS_API_KEY=your_server_api_key" > .env

uvicorn main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

### Frontend (local)

The frontend is plain static files, deployed separately from the API:

1. Edit `frontend/index.html`:
   - Set `GOOGLE_MAPS_API_KEY` to your browser key
   - Set `API_BASE_URL` to `http://localhost:8000`
2. Serve the folder (e.g. VS Code Live Server on port 5500 — CORS is pre-configured for it)

## Deployment

### Backend → Docker → AWS EC2

```bash
cd backend
docker build -t flex-api .

# Run locally to test:
docker run -d -p 8000:8000 -e GOOGLE_MAPS_API_KEY=your_server_key flex-api
```

On EC2 (Ubuntu, t3.micro):

1. Open security group ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)
2. Install Docker: `curl -fsSL https://get.docker.com | sh`
3. Build & run the container (bind to localhost only — Caddy will proxy):

```bash
docker build -t flex-api .
docker run -d -p 127.0.0.1:8000:8000 -e GOOGLE_MAPS_API_KEY=your_server_key flex-api
```

4. **HTTPS via Caddy** (required — browsers block `https://` pages calling `http://` APIs). Point a domain (e.g. a free duckdns.org subdomain) at the EC2 Elastic IP, then run Caddy:

```
flex-api.yourname.duckdns.org
reverse_proxy localhost:8000
```

Caddy automatically obtains and renews a Let's Encrypt certificate.

5. Update `ALLOWED_ORIGINS` in `backend/main.py` to your Vercel domain, rebuild, and restart the container.

### Frontend → Vercel

```bash
cd frontend
# Edit index.html first:
#   - GOOGLE_MAPS_API_KEY = your browser key
#   - API_BASE_URL = https://flex-api.yourname.duckdns.org
npx vercel          # preview deploy
npx vercel --prod   # production
```

### Final checklist

- [ ] Server key restricted to EC2 Elastic IP (Geocoding / Distance Matrix / Directions only)
- [ ] Browser key restricted to your Vercel domain (Maps JavaScript API only)
- [ ] `API_BASE_URL` in `frontend/index.html` points to your HTTPS domain
- [ ] `ALLOWED_ORIGINS` in `backend/main.py` contains your Vercel domain
- [ ] Billing alert / spending cap set in Google Cloud Console

## How to Use

1. Enter your starting address (e.g., "123 Main St, Atlanta, GA")
2. Enter delivery stops (one address per line, up to 40) or upload a CSV
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
- **Heuristics** (nearest neighbor, 2-opt) trade optimality for speed
- **OR-Tools** uses constraint programming with guided local search — the industry-standard approach

This project solves the **open TSP variant**: the route starts at the warehouse and ends at the last delivery stop without returning to the warehouse, which better models a real Amazon Flex shift.

This project demonstrates that tradeoff in practice: brute force finds the optimal route for small inputs, while heuristics and OR-Tools scale to larger problems with good (but not perfect) solutions.

## APIs Used

- **Google Maps Geocoding API** — Converts addresses to lat/long coordinates
- **Google Maps Distance Matrix API** — Computes real driving distances between all stops (batched to respect API limits)
- **Google Maps Directions API** — Returns the actual driving route geometry (polyline), split into segments for routes with 25+ stops

All require a Google Maps API key set in the `.env` file.