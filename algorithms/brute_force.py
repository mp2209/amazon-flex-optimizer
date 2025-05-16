"""
TSP Solver - Brute Force Algorithm
Explores all permutations to find the optimal route.
Only feasible for small inputs (n <= 10) due to O(n!) complexity.
"""
import itertools
from .base import calculate_route_distance


def solve_brute_force(distance_matrix, start_index=0):
    """
    Try every possible permutation of stops to find the shortest route.
    Returns the optimal route as a list of indices.
    """
    n = len(distance_matrix)
    if n <= 1:
        return list(range(n))

    # All stops except the starting point
    other_indices = [i for i in range(n) if i != start_index]

    best_route = None
    best_distance = float('inf')

    for perm in itertools.permutations(other_indices):
        route = [start_index] + list(perm)  # Open TSP — no return to start
        dist = calculate_route_distance(route, distance_matrix)

        if dist < best_distance:
            best_distance = dist
            best_route = route

    return best_route