"""
TSP Solver - Simulated Annealing Algorithm
Probabilistic technique inspired by annealing in metallurgy.
Accepts worse solutions early (high temperature) to escape local minima,
gradually becomes more selective as temperature cools.
"""
import math
import random
from .base import calculate_route_distance


def solve_simulated_annealing(distance_matrix, start_index=0,
                               initial_temp=1000, cooling_rate=0.995,
                               min_temp=1, max_iterations=10000):
    """
    Use simulated annealing to approximate the shortest route.
    Starts with nearest neighbor, then explores with decreasing randomness.
    """
    from .nearest_neighbor import solve_nearest_neighbor

    n = len(distance_matrix)
    if n <= 2:
        return list(range(n)) if n > 0 else []

    # Start with nearest neighbor solution (already open TSP — no return to start)
    route = solve_nearest_neighbor(distance_matrix, start_index)

    current_distance = calculate_route_distance(route, distance_matrix)
    best_route = route[:]
    best_distance = current_distance

    temp = initial_temp
    iterations = 0

    while temp > min_temp and iterations < max_iterations:
        # Randomly swap two stops (not the start)
        if len(route) > 2:
            i, j = sorted(random.sample(range(1, len(route)), 2))
            new_route = route[:i] + route[i:j+1][::-1] + route[j+1:]
        else:
            continue

        new_distance = calculate_route_distance(new_route, distance_matrix)

        # Accept if better, or probabilistically if worse (based on temperature)
        delta = new_distance - current_distance
        if delta < 0 or random.random() < math.exp(-delta / temp):
            route = new_route
            current_distance = new_distance

            if current_distance < best_distance:
                best_route = route[:]
                best_distance = current_distance

        temp *= cooling_rate
        iterations += 1

    return best_route  # Open TSP — no return to start