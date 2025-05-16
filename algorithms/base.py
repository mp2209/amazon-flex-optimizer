"""
Base utilities for TSP algorithms.
"""


def calculate_route_distance(route, distance_matrix):
    """
    Calculate total distance of a route given a distance matrix.
    Route is a list of indices, e.g., [0, 2, 1, 3, 0] (start and end at 0).
    """
    total = 0
    for i in range(len(route) - 1):
        total += distance_matrix[route[i]][route[i + 1]]
    return total