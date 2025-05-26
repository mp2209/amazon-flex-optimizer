"""
TSP Solver - 2-opt Local Search Algorithm
Iteratively swaps pairs of edges to shorten the route.
Improves an initial route (e.g., from nearest neighbor) by reversing segments.
O(n^2) per iteration, multiple iterations until no improvement.
"""
from .base import calculate_route_distance


def solve_2opt(distance_matrix, start_index=0, max_iterations=1000):
    """
    Start with nearest neighbor, then improve with 2-opt swaps.
    Reverses segments of the route if it reduces total distance.
    """
    from .nearest_neighbor import solve_nearest_neighbor

    n = len(distance_matrix)
    if n <= 2:
        return list(range(n)) if n > 0 else []

    # Start with nearest neighbor solution (already open TSP — no return to start)
    route = solve_nearest_neighbor(distance_matrix, start_index)

    improved = True
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1

        for i in range(1, len(route) - 1):
            for j in range(i + 1, len(route)):
                # Try reversing the segment between i and j
                new_route = route[:i] + route[i:j+1][::-1] + route[j+1:]

                if calculate_route_distance(new_route, distance_matrix) < \
                   calculate_route_distance(route, distance_matrix):
                    route = new_route
                    improved = True

    return route  # Open TSP — no return to start