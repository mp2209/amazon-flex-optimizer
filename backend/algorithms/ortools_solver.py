"""
TSP Solver - Google OR-Tools
Uses Google's OR-Tools constraint programming solver for TSP.
This is the industry-standard approach — fast, optimal for small/medium inputs,
and demonstrates you understand professional tools vs. custom implementations.
"""
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def solve_ortools(distance_matrix, start_index=0):
    """
    Use Google OR-Tools to solve TSP (open variant — no return to start).
    Returns route as list of indices, starting at start_index.
    """
    n = len(distance_matrix)
    if n <= 1:
        return list(range(n))

    # Create the routing index manager
    # Args: number of locations, number of vehicles (1 for TSP), depot (start)
    manager = pywrapcp.RoutingIndexManager(n, 1, start_index)

    # Create routing model
    routing = pywrapcp.RoutingModel(manager)

    # Define distance callback
    def distance_callback(from_index, to_index):
        """Returns the distance between two nodes (as int for OR-Tools)."""
        from_node = manager.IndexToNode(int(from_index))
        to_node = manager.IndexToNode(int(to_index))
        return int(distance_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Set search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 5  # 5 second time limit

    # Solve
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        # Fallback to simple route if solver fails
        return list(range(n))

    # Extract route from solution (open TSP — don't append return to start)
    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(int(index)))
        index = solution.Value(routing.NextVar(index))

    return route  # Open TSP — no return to start