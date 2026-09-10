/* Amazon Flex Route Optimizer - Frontend Logic */

let map = null;
let markers = [];
let routePolyline = null;
let routeData = null;
let comparisonChart = null;
let currentRoute = null;  // Track current route for next-stop feature
let routeSegments = [];   // Store geometry segments between consecutive stops
let segmentPolylines = []; // Store individual polyline layers for segment display

// Colors for stops (gradient from red to green based on order)
const STOP_COLORS = [
    '#E74C3C', '#E67E22', '#F39C12', '#F1C40F',
    '#2ECC71', '#1ABC9C', '#3498DB', '#9B59B6',
    '#E91E63', '#00BCD4', '#8BC34A', '#FF9800',
    '#673AB7', '#3F51B5', '#009688',
    '#FF5722', '#795548', '#607D8B', '#CDDC39',
    '#FFC107', '#00ACC1', '#AF52CC', '#5C6BC0',
    '#EC407A', '#26A69A', '#9CCC65', '#FFA726',
    '#8D6E63', '#78909C', '#D4E157', '#FFB74D',
    '#BA68C8', '#7986CB', '#4DB6AC', '#AED581',
];

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('optimize-btn').addEventListener('click', optimizeRoute);
    document.getElementById('new-shift-btn').addEventListener('click', resetToSetup);
    document.getElementById('algo-select').addEventListener('change', () => {
        if (routeData) displayRoute(document.getElementById('algo-select').value);
    });
    document.getElementById('csv-upload').addEventListener('change', handleCSVUpload);

    // Load saved theme preference
    const savedTheme = localStorage.getItem('theme') || 'light';
    applyTheme(savedTheme);
});

// Theme toggle
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-icon');
    const label = document.getElementById('theme-label');
    if (icon && label) {
        if (theme === 'dark') {
            icon.textContent = '☀️';
            label.textContent = 'Light';
        } else {
            icon.textContent = '🌙';
            label.textContent = 'Dark';
        }
    }
}

// Handle CSV file upload
function handleCSVUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        const lines = text.split('\n').map(l => l.trim()).filter(l => l);

        // First line is start, rest are stops
        if (lines.length >= 2) {
            document.getElementById('start-address').value = lines[0];
            document.getElementById('stops-input').value = lines.slice(1).join('\n');
        } else if (lines.length === 1) {
            document.getElementById('start-address').value = lines[0];
        }
    };
    reader.readAsText(file);
}

// Main optimize function
async function optimizeRoute() {
    const startAddress = document.getElementById('start-address').value.trim();
    const stopsText = document.getElementById('stops-input').value.trim();
    const errorEl = document.getElementById('error-message');

    errorEl.classList.remove('show');

    if (!startAddress) {
        errorEl.textContent = 'Please enter a starting point.';
        errorEl.classList.add('show');
        return;
    }

    const stops = stopsText.split('\n').map(s => s.trim()).filter(s => s);

    if (stops.length === 0) {
        errorEl.textContent = 'Please enter at least one delivery stop.';
        errorEl.classList.add('show');
        return;
    }

    // Show loading screen
    document.getElementById('setup-screen').classList.add('hidden');
    document.getElementById('loading-screen').classList.remove('hidden');

    try {
        const response = await fetch(`${API_BASE_URL}/optimize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start: startAddress, stops: stops }),
        });

        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        routeData = data;
        showResults(data);
    } catch (err) {
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('setup-screen').classList.remove('hidden');
        errorEl.textContent = err.message;
        errorEl.classList.add('show');
    }
}

// Show results screen
function showResults(data) {
    document.getElementById('loading-screen').classList.add('hidden');
    document.getElementById('results-screen').classList.remove('hidden');

    // Store data globally so initMap can access it
    routeData = data;

    // Initialize map
    setTimeout(() => {
        initMap(data.coordinates);
        displayRoute('nearest_neighbor');
        updateSummary(data);
        drawComparisonChart(data);
    }, 100);
}

// Initialize Leaflet map
function initMap(coordinates) {
    if (map) {
        map.remove();
    }

    // Center on first coordinate (start point)
    const center = coordinates[0];
    map = L.map('map').setView([center[0], center[1]], 13);

    // Use Google Maps tiles via Leaflet
    L.tileLayer(`https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}&key=${GOOGLE_MAPS_API_KEY}`, {
        attribution: '&copy; Google Maps',
        maxZoom: 20,
    }).addTo(map);

    // Spread nearby markers around their shared center so none are hidden
    const displayCoordinates = separateNearbyCoordinates(coordinates);

    // Add markers for each stop
    markers = [];
    coordinates.forEach((coord, index) => {
        const isStart = index === 0;
        const color = isStart ? '#146EB4' : STOP_COLORS[index % STOP_COLORS.length];
        const displayCoord = displayCoordinates[index];

        // Custom marker icon
        const icon = L.divIcon({
            className: 'custom-marker',
            html: `<div style="
                background: ${color};
                color: white;
                border-radius: 50%;
                width: 28px;
                height: 28px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 12px;
                border: 2px solid white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            ">${isStart ? 'W' : index}</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14],
        });

        const label = isStart ? 'Warehouse / Start' : `Package ${index}`;
        const address = routeData.addresses[index] || '';
        const marker = L.marker([displayCoord[0], displayCoord[1]], { icon })
            .addTo(map)
            .bindPopup(`<strong>${label}</strong><br>${address}<br><small>Actual location: ${coord[0].toFixed(5)}, ${coord[1].toFixed(5)}</small>`);

        markers.push(marker);
    });

    // Fit map to show all markers
    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
}

// Spread markers that are too close to one another in a small radial pattern.
// Routing continues to use routeData.coordinates, so this only changes display.
function separateNearbyCoordinates(coordinates) {
    const thresholdMeters = 45;
    const spreadMeters = 32;
    const result = coordinates.map(coord => [...coord]);
    const groups = [];
    const assigned = new Set();

    coordinates.forEach((coord, index) => {
        if (assigned.has(index)) return;

        const group = [];
        coordinates.forEach((otherCoord, otherIndex) => {
            if (distanceBetweenMeters(coord, otherCoord) <= thresholdMeters) {
                group.push(otherIndex);
            }
        });

        group.forEach(groupIndex => assigned.add(groupIndex));
        if (group.length > 1) groups.push(group);
    });

    groups.forEach(group => {
        const center = group.reduce(
            (sum, index) => [sum[0] + coordinates[index][0], sum[1] + coordinates[index][1]],
            [0, 0]
        );
        center[0] /= group.length;
        center[1] /= group.length;

        group.forEach((index, position) => {
            const angle = (2 * Math.PI * position) / group.length - Math.PI / 2;
            const latOffset = (spreadMeters * Math.sin(angle)) / 111320;
            const lngOffset = (spreadMeters * Math.cos(angle)) /
                (111320 * Math.cos(center[0] * Math.PI / 180));
            result[index] = [center[0] + latOffset, center[1] + lngOffset];
        });
    });

    return result;
}

function distanceBetweenMeters(first, second) {
    const latDiff = (first[0] - second[0]) * 111320;
    const lngDiff = (first[1] - second[1]) *
        111320 * Math.cos(first[0] * Math.PI / 180);
    return Math.sqrt(latDiff * latDiff + lngDiff * lngDiff);
}

// Display a route on the map
function displayRoute(algoName) {
    if (!routeData || !routeData.algorithms[algoName]) return;

    const algo = routeData.algorithms[algoName];

    // Remove existing route polyline and segment polylines
    if (routePolyline) {
        map.removeLayer(routePolyline);
        routePolyline = null;
    }
    segmentPolylines.forEach(p => map.removeLayer(p));
    segmentPolylines = [];

    // Draw the full route geometry (faded)
    if (algo.geometry && algo.geometry.length > 0) {
        const latlngs = algo.geometry.map(coord => [coord[0], coord[1]]);
        routePolyline = L.polyline(latlngs, {
            color: '#FF9900',
            weight: 4,
            opacity: 0.8,
        }).addTo(map);
    }

    // Split geometry into segments between consecutive stops
    // Each segment = the portion of the polyline between stop[i] and stop[i+1]
    routeSegments = splitGeometryIntoSegments(algo.geometry, algo.route);

    // Fit bounds to include ALL markers (not just the route polyline)
    if (markers.length > 0) {
        const group = L.featureGroup(markers);
        if (routePolyline) {
            const routeBounds = routePolyline.getBounds();
            const markerBounds = group.getBounds();
            const combinedBounds = L.latLngBounds(
                [Math.min(routeBounds.getSouth(), markerBounds.getSouth()),
                 Math.min(routeBounds.getWest(), markerBounds.getWest())],
                [Math.max(routeBounds.getNorth(), markerBounds.getNorth()),
                 Math.max(routeBounds.getEast(), markerBounds.getEast())]
            );
            map.fitBounds(combinedBounds.pad(0.1));
        } else {
            map.fitBounds(group.getBounds().pad(0.1));
        }
    }

    // Update stop list
    updateStopList(algo.route);
}

// Split the full route geometry into segments between consecutive stops
// Returns array of {fromIndex, toIndex, latlngs} for each segment
function splitGeometryIntoSegments(geometry, route) {
    if (!geometry || geometry.length === 0 || !route || route.length < 2) return [];

    const segments = [];
    const coords = routeData.coordinates;

    // For each consecutive pair of stops in the route, find the portion
    // of the geometry polyline that belongs to that segment
    // We do this by finding the closest geometry points to each stop
    const stopIndicesInGeometry = [];

    for (let i = 0; i < route.length; i++) {
        const stopCoord = coords[route[i]];
        if (!stopCoord) continue;

        // Find the closest point in the geometry to this stop
        let minDist = Infinity;
        let closestIdx = 0;
        for (let j = 0; j < geometry.length; j++) {
            const dist = Math.pow(geometry[j][0] - stopCoord[0], 2) +
                         Math.pow(geometry[j][1] - stopCoord[1], 2);
            if (dist < minDist) {
                minDist = dist;
                closestIdx = j;
            }
        }
        stopIndicesInGeometry.push(closestIdx);
    }

    // Create segments between consecutive stops
    for (let i = 0; i < stopIndicesInGeometry.length - 1; i++) {
        const startIdx = stopIndicesInGeometry[i];
        const endIdx = stopIndicesInGeometry[i + 1];

        // Extract the portion of geometry between these two stops
        const segmentLatLngs = [];
        const lo = Math.min(startIdx, endIdx);
        const hi = Math.max(startIdx, endIdx);

        for (let j = lo; j <= hi; j++) {
            segmentLatLngs.push([geometry[j][0], geometry[j][1]]);
        }

        segments.push({
            fromIndex: route[i],
            toIndex: route[i + 1],
            order: i,
            latlngs: segmentLatLngs,
        });
    }

    return segments;
}

// Show only one segment on the map (from stop at given order to next stop)
// Hides the full route, shows only the segment between current and next stop
function showSegmentOnly(order) {
    if (!routeSegments.length) return;

    // Remove the full route polyline
    if (routePolyline) {
        map.removeLayer(routePolyline);
        routePolyline = null;
    }

    // Remove any existing segment polylines
    segmentPolylines.forEach(p => map.removeLayer(p));
    segmentPolylines = [];

    // Find the segment for this order
    const segment = routeSegments.find(s => s.order === order);
    if (!segment || segment.latlngs.length === 0) return;

    // Draw only this segment, highlighted
    const segmentPolyline = L.polyline(segment.latlngs, {
        color: '#FF9900',
        weight: 6,
        opacity: 1.0,
    }).addTo(map);
    segmentPolylines.push(segmentPolyline);

    // Fit bounds to just this segment, centered on screen
    const bounds = segmentPolyline.getBounds().pad(0.3);
    map.fitBounds(bounds, { animate: true, duration: 0.5 });
}

// Restore the full route view
function showFullRoute() {
    // Remove segment polylines
    segmentPolylines.forEach(p => map.removeLayer(p));
    segmentPolylines = [];

    // Redraw the full route
    const algoName = document.getElementById('algo-select').value;
    const algo = routeData.algorithms[algoName];
    if (algo && algo.geometry && algo.geometry.length > 0) {
        const latlngs = algo.geometry.map(coord => [coord[0], coord[1]]);
        routePolyline = L.polyline(latlngs, {
            color: '#FF9900',
            weight: 4,
            opacity: 0.8,
        }).addTo(map);
    }

    // Fit bounds to all markers + route
    if (markers.length > 0) {
        const group = L.featureGroup(markers);
        if (routePolyline) {
            const routeBounds = routePolyline.getBounds();
            const markerBounds = group.getBounds();
            const combinedBounds = L.latLngBounds(
                [Math.min(routeBounds.getSouth(), markerBounds.getSouth()),
                 Math.min(routeBounds.getWest(), markerBounds.getWest())],
                [Math.max(routeBounds.getNorth(), markerBounds.getNorth()),
                 Math.max(routeBounds.getEast(), markerBounds.getEast())]
            );
            map.fitBounds(combinedBounds.pad(0.1));
        } else {
            map.fitBounds(group.getBounds().pad(0.1));
        }
    }
}

// Update the ordered stop list in sidebar
function updateStopList(route) {
    const stopList = document.getElementById('ordered-stops');
    stopList.innerHTML = '';

    // Store current route for next-stop feature
    currentRoute = route;

    // Route is open TSP — no return-to-start at the end, use as-is
    const displayRoute = route;

    displayRoute.forEach((index, order) => {
        const li = document.createElement('li');
        const label = index === 0 ? 'Warehouse / Start' : `Package ${index}`;
        const address = routeData.addresses[index] || '';
        li.textContent = `${label} — ${address}`;
        li.style.cursor = 'pointer';
        li.dataset.stopIndex = index;
        li.dataset.order = order;

        // Click to navigate to this stop + show next stop panel
        li.addEventListener('click', () => {
            navigateToStop(index);
            showNextStop(order);
        });

        // Hover effect
        li.addEventListener('mouseenter', () => {
            li.style.transform = 'translateX(4px)';
        });
        li.addEventListener('mouseleave', () => {
            li.style.transform = 'translateX(0)';
        });

        stopList.appendChild(li);
    });
}

// Show "Next Stop" panel — displays route from current stop to next stop
function showNextStop(order) {
    if (!currentRoute || !routeData) return;

    const panel = document.getElementById('next-stop-panel');
    const content = document.getElementById('next-stop-content');
    panel.classList.remove('hidden');

    const currentIndex = currentRoute[order];
    const nextIndex = currentRoute[order + 1];

    const currentLabel = currentIndex === 0 ? 'Warehouse / Start' : `Package ${currentIndex}`;
    const currentAddress = routeData.addresses[currentIndex] || '';

    if (nextIndex !== undefined) {
        const nextLabel = nextIndex === 0 ? 'Warehouse / Start' : `Package ${nextIndex}`;
        const nextAddress = routeData.addresses[nextIndex] || '';

        content.innerHTML = `
            <div class="next-stop-row">
                <span class="next-stop-label">From:</span>
                <span class="next-stop-value">${currentLabel}</span>
            </div>
            <div class="next-stop-row">
                <span class="next-stop-label">Address:</span>
                <span class="next-stop-value" style="font-size: 0.75rem; text-align: right; max-width: 200px;">${currentAddress}</span>
            </div>
            <div class="next-stop-arrow">↓</div>
            <div class="next-stop-row">
                <span class="next-stop-label">To:</span>
                <span class="next-stop-value">${nextLabel}</span>
            </div>
            <div class="next-stop-row">
                <span class="next-stop-label">Address:</span>
                <span class="next-stop-value" style="font-size: 0.75rem; text-align: right; max-width: 200px;">${nextAddress}</span>
            </div>
            <div class="next-stop-close">
                <button onclick="showFullRoute(); hideNextStop();">Show full route</button>
                <button onclick="hideNextStop();">Close</button>
            </div>
        `;

        // Show only this segment on the map
        showSegmentOnly(order);
    } else {
        // Last stop — no next stop
        content.innerHTML = `
            <div class="next-stop-row">
                <span class="next-stop-label">Current:</span>
                <span class="next-stop-value">${currentLabel}</span>
            </div>
            <div class="next-stop-row">
                <span class="next-stop-label">Address:</span>
                <span class="next-stop-value" style="font-size: 0.75rem; text-align: right; max-width: 200px;">${currentAddress}</span>
            </div>
            <div class="next-stop-arrow">🏁</div>
            <div class="next-stop-row">
                <span class="next-stop-label">Status:</span>
                <span class="next-stop-value">Final destination</span>
            </div>
            <div class="next-stop-close">
                <button onclick="showFullRoute(); hideNextStop();">Show full route</button>
                <button onclick="hideNextStop();">Close</button>
            </div>
        `;
    }
}

// Hide the next-stop panel
function hideNextStop() {
    document.getElementById('next-stop-panel').classList.add('hidden');
}

// Navigate to a stop on the map — zoom in and open popup
function navigateToStop(index) {
    if (!routeData || !routeData.coordinates[index]) return;

    const coord = routeData.coordinates[index];
    const lat = coord[0];
    const lng = coord[1];

    // Pan and zoom to the stop
    map.setView([lat, lng], 16, { animate: true, duration: 0.5 });

    // Find the corresponding marker and open its popup
    const marker = markers[index];
    if (marker) {
        marker.openPopup();
    }

    // Highlight the stop briefly
    if (marker) {
        const originalIcon = marker.getIcon();
        const isStart = index === 0;
        const color = isStart ? '#146EB4' : STOP_COLORS[index % STOP_COLORS.length];

        // Temporarily enlarge the marker
        const highlightIcon = L.divIcon({
            className: 'custom-marker',
            html: `<div style="
                background: ${color};
                color: white;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 14px;
                border: 3px solid #FF9900;
                box-shadow: 0 0 12px rgba(255, 153, 0, 0.8);
                transition: all 0.3s;
            ">${isStart ? 'W' : index}</div>`,
            iconSize: [40, 40],
            iconAnchor: [20, 20],
        });

        marker.setIcon(highlightIcon);

        // Revert after 2 seconds
        setTimeout(() => {
            marker.setIcon(originalIcon);
        }, 2000);
    }
}

// Update the shift summary card
function updateSummary(data) {
    // Find best algorithm (shortest distance)
    let bestAlgo = null;
    let bestDist = Infinity;

    for (const [name, algo] of Object.entries(data.algorithms)) {
        // Skip 'original' — it's the baseline, not an optimization algorithm
        if (name === 'original') continue;
        if (algo.distance_m < bestDist) {
            bestDist = algo.distance_m;
            bestAlgo = name;
        }
    }

    const best = data.algorithms[bestAlgo];

    // Display best algorithm
    const algoLabels = {
        'original': 'Original (as entered)',
        'brute_force': 'Brute Force (Optimal)',
        'nearest_neighbor': 'Nearest Neighbor',
        '2opt': '2-opt',
        'ortools': 'Google OR-Tools',
    };

    document.getElementById('best-algo').textContent = algoLabels[bestAlgo] || bestAlgo;
    document.getElementById('best-distance').textContent = `${best.distance_mi} mi`;

    // Estimate drive time (avg 30 mph in city = 13.4 m/s)
    const driveTimeSec = best.distance_m / 13.4;
    const minutes = Math.round(driveTimeSec / 60);
    document.getElementById('best-time').textContent = `${minutes} min`;

    // Estimate gas saved vs. original order (the order user entered)
    const originalDist = data.algorithms['original'].distance_m;
    const savedMi = ((originalDist - bestDist) * 0.000621371).toFixed(1);
    const gasSaved = (savedMi * 0.25).toFixed(2); // ~$0.25/mile
    document.getElementById('gas-saved').textContent =
        savedMi > 0 ? `${savedMi} mi ($${gasSaved})` : '—';

    // Update algorithm dropdown
    const select = document.getElementById('algo-select');
    select.innerHTML = '';
    for (const [name, algo] of Object.entries(data.algorithms)) {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = `${algoLabels[name] || name} — ${algo.distance_mi} mi`;
        select.appendChild(option);
    }
    select.value = bestAlgo;
}

// Draw algorithm comparison chart
function drawComparisonChart(data) {
    const ctx = document.getElementById('comparison-chart').getContext('2d');

    const labels = [];
    const distances = [];
    const times = [];

    const algoLabels = {
        'original': 'Original',
        'brute_force': 'Brute Force',
        'nearest_neighbor': 'Nearest Neighbor',
        '2opt': '2-opt',
        'ortools': 'OR-Tools',
    };

    for (const [name, algo] of Object.entries(data.algorithms)) {
        labels.push(algoLabels[name] || name);
        distances.push(algo.distance_mi);
        times.push(algo.time_ms);
    }

    if (comparisonChart) {
        comparisonChart.destroy();
    }

    comparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Distance (miles)',
                data: distances,
                backgroundColor: '#FF9900',
                borderColor: '#E88B00',
                borderWidth: 1,
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Route Distance by Algorithm',
                    font: { size: 14 },
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { text: 'Miles', display: true },
                },
            },
        },
    });
}

// Reset to setup screen
function resetToSetup() {
    document.getElementById('results-screen').classList.add('hidden');
    document.getElementById('setup-screen').classList.remove('hidden');
    document.getElementById('next-stop-panel').classList.add('hidden');
    if (map) {
        map.remove();
        map = null;
    }
    routeData = null;
    currentRoute = null;
    routeSegments = [];
    segmentPolylines = [];
}