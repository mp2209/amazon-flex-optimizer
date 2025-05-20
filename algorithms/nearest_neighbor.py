"""
TSP Solver - Nearest Neighbor Algorithm
Greedy heuristic: always visit the closest unvisited stop next.
Fast (O(n^2)) but often produces suboptimal routes.
This mimics what a driver does intuitively.
"""
from .base import calculate_route_distance


def solve_nearest_neighbor(distance_matrix, start_index=0):
    """
    Greedy approach: from current stop, go to nearest unvisited stop.
    Returns route as list of indices (open TSP — no return to start).
    """
    n = len(distance_matrix)
    if n <= 1:
        return list(range(n))

    unvisited = set(range(n))
    unvisited.remove(start_index)

    route = [start_index]
    current = start_index

    while unvisited:
        # Find nearest unvisited stop
        nearest = min(unvisited, key=lambda j: distance_matrix[current][j])
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return route  # Open TSP — no return to start