#!/usr/bin/env python3
"""Solver benchmark: every solver on hundreds of shifts, offline.

Shifts are sampled from the real road-distance matrix in bench/data/
(fetched once by fetch_matrix.py). Each shift picks a random start and
K random stops; the order the stops were drawn in is the driver's "entered
order", the baseline the app compares against. Each solver then routes the
shift with the app's own code, and every route is scored on the real
driving distances. No API calls.

    make bench          # run + analyze
    python3 bench/run.py --shifts 25 --jobs 6
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from algorithms import (  # noqa: E402
    calculate_route_distance,
    solve_2opt,
    solve_brute_force,
    solve_nearest_neighbor,
    solve_ortools,
)

DATA = os.path.join(ROOT, "bench", "data", "atlanta.json")
SIZES = [7, 15, 25, 40]           # stops per shift; 7 is the app's brute-force limit
SWEEP = [0.2, 0.5, 1.0, 2.0]      # extra OR-Tools time limits (s); the app uses 5
REFERENCE_S = 30.0                # long OR-Tools run for a best-known route (K > 7)


def solve_ortools_closed_loop(m, time_limit_s=5.0):
    """The app's OR-Tools solver before the open-route fix: it optimizes a
    round trip back to the start, then the return leg is dropped."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    n = len(m)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    cb = routing.RegisterTransitCallback(
        lambda a, b: int(m[manager.IndexToNode(int(a))][manager.IndexToNode(int(b))]))
    routing.SetArcCostEvaluatorOfAllVehicles(cb)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.FromMilliseconds(int(time_limit_s * 1000))
    sol = routing.SolveWithParameters(p)
    route, i = [], routing.Start(0)
    while not routing.IsEnd(i):
        route.append(manager.IndexToNode(int(i)))
        i = sol.Value(routing.NextVar(i))
    return route


def solvers_for(k):
    """Solver name -> function of the distance matrix (start is index 0)."""
    s = {
        "nearest_neighbor": lambda m: solve_nearest_neighbor(m, 0),
        "2opt": lambda m: solve_2opt(m, 0),
        "ortools": lambda m: solve_ortools(m, 0),  # the app's setting: 5 s
        "ortools_closed_loop": solve_ortools_closed_loop,
    }
    for t in SWEEP:
        s[f"ortools_{t:g}s"] = lambda m, t=t: solve_ortools(m, 0, time_limit_s=t)
    if k <= 7:
        s["brute_force"] = lambda m: solve_brute_force(m, 0)
    else:
        s[f"ortools_{REFERENCE_S:g}s"] = lambda m: solve_ortools(m, 0, time_limit_s=REFERENCE_S)
    return s


def run_shift(job):
    shift_id, k, idx, full = job
    m = [[full[i][j] for j in idx] for i in idx]  # start at 0, stops in entered order
    rows = []
    entered = calculate_route_distance(list(range(k + 1)), m)
    rows.append((shift_id, k, "entered_order", entered, 0.0))
    for name, solver in solvers_for(k).items():
        t0 = time.perf_counter()
        route = solver(m)
        ms = (time.perf_counter() - t0) * 1000
        assert route[0] == 0 and sorted(route) == list(range(k + 1)), (name, route)
        rows.append((shift_id, k, name, calculate_route_distance(route, m), ms))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shifts", type=int, default=25, help="shifts per size")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=os.path.join(ROOT, "bench", "results"))
    a = ap.parse_args()

    data = json.load(open(DATA))
    full, n_places = data["distance_m"], len(data["places"])
    rng = random.Random(a.seed)
    jobs, shifts = [], []
    for k in SIZES:
        for s in range(a.shifts):
            idx = rng.sample(range(n_places), k + 1)  # idx[0] is the start
            sid = f"k{k}-{s:02d}"
            jobs.append((sid, k, idx, full))
            shifts.append({"shift": sid, "stops": k, "places": idx})

    os.makedirs(a.out, exist_ok=True)
    started = time.time()
    rows = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, r in enumerate(ex.map(run_shift, jobs), 1):
            rows.extend(r)
            print(f"\r{i}/{len(jobs)} shifts", end="", flush=True)
    print(f"\ndone in {time.time() - started:.0f}s")

    with open(os.path.join(a.out, "runs.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shift", "stops", "solver", "distance_m", "time_ms"])
        w.writerows((s, k, n, d, f"{t:.2f}") for s, k, n, d, t in rows)
    with open(os.path.join(a.out, "shifts.json"), "w") as f:
        json.dump({"seed": a.seed, "data": os.path.relpath(DATA, ROOT), "jobs": a.jobs,
                   "shifts": shifts}, f, indent=1)
    print(f"Wrote {a.out}/runs.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
