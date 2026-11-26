#!/usr/bin/env python3
"""The optimizer in thirty seconds, offline.

Routes the app's demo shift (Georgia Aquarium + 8 stops) and then a full
40-stop shift with every solver, on the real road distances saved in
bench/data/atlanta.json, and prints what the driver would save. No API calls.

    python3 scripts/demo.py
    python3 scripts/demo.py --record docs/demo.svg   # also write an animated SVG
"""
import argparse
import json
import os
import random
import sys
import time
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "bench"))

from algorithms import (  # noqa: E402
    calculate_route_distance,
    solve_2opt,
    solve_brute_force,
    solve_nearest_neighbor,
    solve_ortools,
)
from run import solve_ortools_closed_loop  # noqa: E402

M_PER_MI = 1609.344
CITY_MPS = 13.4        # the app's drive-time estimate: 30 mph
FUEL_PER_MI = 0.25     # the app's fuel estimate


class Screen:
    """Prints lines and remembers when each appeared, for --record."""

    def __init__(self, pace):
        self.start, self.lines, self.pace = time.monotonic(), [], pace

    def out(self, text="", kind="out"):
        print(text, flush=True)
        self.lines.append((time.monotonic() - self.start, text, kind))
        time.sleep(self.pace)

    def cmd(self, text):
        self.out("$ " + text, "cmd")

    def note(self, text):
        self.out("# " + text, "note")


def route_table(sc, m, solvers):
    entered = calculate_route_distance(list(range(len(m))), m)
    sc.out(f"  {'solver':<26}{'miles':>7}{'saved':>8}{'time':>10}")
    sc.out(f"  {'entered order':<26}{entered / M_PER_MI:>7.2f}{'':>8}{'':>10}")
    best = None
    for name, fn in solvers:
        t0 = time.perf_counter()
        route = fn(m)
        ms = (time.perf_counter() - t0) * 1000
        d = calculate_route_distance(route, m)
        t = f"{ms:.1f} ms" if ms < 1000 else f"{ms / 1000:.1f} s"
        sc.out(f"  {name:<26}{d / M_PER_MI:>7.2f}{100 * (entered - d) / entered:>7.1f}%{t:>10}")
        if "(" not in name and (best is None or d <= best[1]):  # only solvers the app runs
            best = (name, d)
    return entered, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", help="write an animated SVG of the output here")
    ap.add_argument("--pace", type=float, default=0.35, help="seconds between printed lines")
    a = ap.parse_args()

    data = json.load(open(os.path.join(ROOT, "bench", "data", "atlanta.json")))
    full, places = data["distance_m"], data["places"]
    sc = Screen(a.pace)

    sc.cmd("python3 scripts/demo.py")
    sc.note("The app's demo shift: start at Georgia Aquarium, 8 stops in the order entered")
    demo = list(range(9))  # places.txt starts with the demo shift, in the app's order
    for i, p in enumerate(places[1:9], 1):
        sc.out(f"  {i}. {p.split(',')[0]}")
    sc.note("Routing it on real Google road distances (saved, no API calls)")
    m = [[full[i][j] for j in demo] for i in demo]
    entered, (best_name, best) = route_table(sc, m, [
        ("Nearest neighbor", lambda m: solve_nearest_neighbor(m, 0)),
        ("2-opt", lambda m: solve_2opt(m, 0)),
        ("OR-Tools", lambda m: solve_ortools(m, 0)),
        ("Brute force (check)", lambda m: solve_brute_force(m, 0)),
    ])
    saved_mi = round((entered - best) / M_PER_MI, 1)  # the app rounds miles first
    sc.note("The shift summary panel, computed the way the app does")
    sc.out(f"  best algorithm {best_name}: {best / M_PER_MI:.2f} mi, est. {round(best / CITY_MPS / 60)} min of driving")
    sc.out(f"  gas saved {saved_mi} mi (${saved_mi * FUEL_PER_MI:.2f}) vs. the entered order")

    sc.note("A full 40-stop shift: random start and stops from 41 Atlanta places")
    idx = random.Random(40).sample(range(len(places)), 41)
    m = [[full[i][j] for j in idx] for i in idx]
    route_table(sc, m, [
        ("Nearest neighbor", lambda m: solve_nearest_neighbor(m, 0)),
        ("2-opt", lambda m: solve_2opt(m, 0)),
        ("OR-Tools", lambda m: solve_ortools(m, 0)),
        ("OR-Tools (before the fix)", solve_ortools_closed_loop),
    ])
    sc.note("The app runs brute force only up to 7 stops: 40 stops would be 40! orderings")

    if a.record:
        write_svg(a.record, sc.lines)
        print(f"wrote {a.record}", file=sys.stderr)


def write_svg(path, lines):
    """Terminal-style SVG; each line fades in at the moment it was printed."""
    lh, pad, width = 18, 16, 760
    end = lines[-1][0] + 4.0  # hold the last frame, then loop
    height = pad * 2 + lh * len(lines) + 24
    css = ["text { font: 13px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #d7d7d2; "
           "white-space: pre } .cmd { fill: #8fd18f } .note { fill: #e0b46b }"]
    body = []
    for i, (t, text, kind) in enumerate(lines):
        p = 100 * t / end
        css.append(f"@keyframes l{i} {{ 0%, {max(p - 0.05, 0):.3f}% {{ opacity: 0 }} {p:.3f}%, 100% {{ opacity: 1 }} }} "
                   f".l{i} {{ animation: l{i} {end:.2f}s infinite }}")
        cls = f"l{i}" + (f" {kind}" if kind != "out" else "")
        body.append(f'<text x="{pad}" y="{pad + 24 + lh * (i + 1) - 4}" class="{cls}" xml:space="preserve">'
                    f"{escape(text)}</text>")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           f'role="img" aria-label="Route optimizer demo: the demo shift and a 40-stop shift routed by four solvers">'
           f"<style>{' '.join(css)}</style>"
           f'<rect width="{width}" height="{height}" rx="8" fill="#1d1f21"/>'
           f'<circle cx="20" cy="16" r="5" fill="#ff5f56"/><circle cx="36" cy="16" r="5" fill="#ffbd2e"/>'
           f'<circle cx="52" cy="16" r="5" fill="#27c93f"/>' + "".join(body) + "</svg>")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write(svg)


if __name__ == "__main__":
    main()
