#!/usr/bin/env python3
"""Turn bench/results/runs.csv into results.md, summary.json and SVG charts.

    python3 bench/analyze.py [bench/results]

Standard library only.
"""
import csv
import json
import math
import os
import random
import statistics as st
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "bench", "results")
DATA = os.path.join(ROOT, "bench", "data", "atlanta.json")

MAIN = ["nearest_neighbor", "2opt", "ortools", "ortools_closed_loop", "brute_force"]
LABEL = {
    "entered_order": "Entered order",
    "nearest_neighbor": "Nearest neighbor",
    "2opt": "2-opt",
    "ortools": "OR-Tools (open route, 5 s)",
    "ortools_closed_loop": "OR-Tools before the fix (round trip, 5 s)",
    "brute_force": "Brute force (optimal)",
}
SWEEP = ["ortools_0.2s", "ortools_0.5s", "ortools_1s", "ortools_2s", "ortools", "ortools_30s"]
SWEEP_S = [0.2, 0.5, 1, 2, 5, 30]
M_PER_MI = 1609.344


def pct(x):
    return f"{100 * x:.1f}%"


def boot_ci(xs, n=4000, seed=7):
    """95% bootstrap interval for the mean of xs."""
    r = random.Random(seed)
    means = sorted(st.fmean(r.choices(xs, k=len(xs))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def load():
    by_shift = defaultdict(dict)
    times = defaultdict(list)
    with open(os.path.join(OUT, "runs.csv")) as f:
        for r in csv.DictReader(f):
            key = (int(r["stops"]), r["shift"])
            by_shift[key][r["solver"]] = int(r["distance_m"])
            times[(int(r["stops"]), r["solver"])].append(float(r["time_ms"]))
    return by_shift, times


def summarize(by_shift, times):
    sizes = sorted({k for k, _ in by_shift})
    out = {"sizes": sizes, "per_size": {}}
    for k in sizes:
        shifts = [v for (kk, _), v in by_shift.items() if kk == k]
        best = [min(v.values()) for v in shifts]
        entered = [v["entered_order"] for v in shifts]
        rows = {}
        for s in shifts[0]:
            if s == "entered_order":
                continue
            d = [v[s] for v in shifts]
            saving = [(e - x) / e for e, x in zip(entered, d)]
            gap = [(x - b) / b for x, b in zip(d, best)]
            rows[s] = {
                "saving_mean": st.fmean(saving),
                "saving_ci": boot_ci(saving),
                "saving_min": min(saving),
                "saving_max": max(saving),
                "gap_mean": st.fmean(gap),
                "gap_max": max(gap),
                "found_best": sum(1 for x, b in zip(d, best) if x == b),
                "time_ms_median": st.median(times[(k, s)]),
                "miles_mean": st.fmean(d) / M_PER_MI,
            }
        ot, two, nn = ([v[s] for v in shifts] for s in ("ortools", "2opt", "nearest_neighbor"))
        vs2 = [(b - a) / b for a, b in zip(ot, two)]
        vsnn = [(b - a) / b for a, b in zip(ot, nn)]
        out["per_size"][k] = {
            "shifts": len(shifts),
            "entered_miles_mean": st.fmean(entered) / M_PER_MI,
            "solvers": rows,
            "ortools_vs_2opt": {"mean": st.fmean(vs2), "ci": boot_ci(vs2),
                                "wins": sum(a < b for a, b in zip(ot, two)),
                                "ties": sum(a == b for a, b in zip(ot, two)),
                                "losses": sum(a > b for a, b in zip(ot, two))},
            "ortools_vs_nn": {"mean": st.fmean(vsnn), "ci": boot_ci(vsnn),
                              "miles_saved_mean": st.fmean(b - a for a, b in zip(ot, nn)) / M_PER_MI},
        }
    return out


def matrix_facts():
    d = json.load(open(DATA))
    m, places = d["distance_m"], d["places"]
    n = len(m)
    asym = [abs(m[i][j] - m[j][i]) / ((m[i][j] + m[j][i]) / 2) for i in range(n) for j in range(i + 1, n)]
    pairs = len(asym)
    garden, park = places.index("Atlanta Botanical Garden, Atlanta, GA"), places.index("Piedmont Park, Atlanta, GA")
    return {
        "places": n,
        "fetched_at": d["fetched_at"],
        "pairs": pairs,
        "asymmetric_pairs": sum(1 for a in asym if a > 0),
        "asymmetry_over_10pct": sum(1 for a in asym if a > 0.10),
        "asymmetry_median": st.median(asym),
        "asymmetry_max": max(asym),
        "garden_to_piedmont_park_m": m[garden][park],
        "garden_coords": d["coords"][garden],
    }


# --- charts -------------------------------------------------------------------

STYLE = """<style>
svg { --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --grid:#e4e3df;
      --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; }
@media (prefers-color-scheme: dark) {
  svg { --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --grid:#383835;
        --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; } }
text { font: 13px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: var(--ink2); }
.title { font-size: 15px; font-weight: 600; fill: var(--ink); }
.lab { fill: var(--ink); }
.grid { stroke: var(--grid); stroke-width: 1; }
.line { fill: none; stroke-width: 2; stroke-linejoin: round; }
.dot { stroke: var(--surface); stroke-width: 2; }
</style>"""


def line_chart(path, title, subtitle, xs, xlabels, series, ylabel, ymax, yfmt, xlog=False, steps=5):
    """series: list of (name, css var, [y or None per x]). Direct-labeled at the right end."""
    W, H, L, R, T, B = 760, 380, 64, 250, 64, 52
    pw, ph = W - L - R, H - T - B
    lx = [math.log(x) for x in xs] if xlog else list(xs)
    x0, x1 = min(lx), max(lx)
    X = lambda v: L + (v - x0) / (x1 - x0) * pw  # noqa: E731
    Y = lambda v: T + ph - v / ymax * ph  # noqa: E731
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="{title}">', STYLE,
         f'<rect width="{W}" height="{H}" rx="8" fill="var(--surface)"/>',
         f'<text x="{L}" y="28" class="title">{title}</text>',
         f'<text x="{L}" y="47">{subtitle}</text>']
    for i in range(steps + 1):
        v = ymax * i / steps
        o.append(f'<line class="grid" x1="{L}" x2="{L + pw}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>')
        o.append(f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{yfmt(v)}</text>')
    for v, lab in zip(lx, xlabels):
        o.append(f'<text x="{X(v):.1f}" y="{T + ph + 20}" text-anchor="middle">{lab}</text>')
    o.append(f'<text x="{L + pw / 2}" y="{H - 10}" text-anchor="middle">{ylabel}</text>')
    ends = []
    for name, var, ys in series:
        pts = [(X(v), Y(y)) for v, y in zip(lx, ys) if y is not None]
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
        o.append(f'<path class="line" d="{d}" stroke="var({var})"/>')
        for x, y in pts:
            o.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="5" fill="var({var})"/>')
        last = [y for y in ys if y is not None][-1]
        ends.append([pts[-1][1], name, var, yfmt(last)])
    ends.sort()
    for i in range(1, len(ends)):  # keep end labels 16px apart...
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 16)
    floor = T + ph - 2                # ...and above the x-axis labels
    for i in range(len(ends) - 1, -1, -1):
        ends[i][0] = min(ends[i][0], floor - 16 * (len(ends) - 1 - i))
    for y, name, var, val in ends:
        o.append(f'<circle cx="{L + pw + 14}" cy="{y - 4:.1f}" r="5" fill="var({var})"/>')
        o.append(f'<text x="{L + pw + 24}" y="{y:.1f}" class="lab">{name} <tspan>{val}</tspan></text>')
    o.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(o))


def charts(s):
    os.makedirs(os.path.join(OUT, "charts"), exist_ok=True)
    sizes = s["sizes"]
    gap = lambda name: [s["per_size"][k]["solvers"][name]["gap_mean"] * 100 for k in sizes]  # noqa: E731
    ser = [("OR-Tools", "--s1", gap("ortools")), ("2-opt", "--s2", gap("2opt")),
           ("Nearest neighbor", "--s3", gap("nearest_neighbor")),
           ("OR-Tools before the fix", "--s4", gap("ortools_closed_loop"))]
    ymax = math.ceil(max(max(v) for _, _, v in ser) / 5) * 5
    line_chart(os.path.join(OUT, "charts", "gap_by_size.svg"),
               "How far each solver is from the best route found",
               f"Mean extra distance over the best route, {s['per_size'][sizes[0]]['shifts']} real-road Atlanta shifts per size",
               sizes, [f"{k} stops" for k in sizes], ser, "Stops per shift", ymax, lambda v: f"{v:.0f}%")

    # The 30 s run is the reference route itself, so it is left off the chart.
    big = [k for k in sizes if k > 7]
    sweep = []
    for var, k in zip(["--s1", "--s2", "--s3"], big[::-1]):
        sweep.append((f"{k} stops", var, [s["per_size"][k]["solvers"][n]["gap_mean"] * 100 for n in SWEEP[:-1]]))
    ymax = math.ceil(max(max(v) for _, _, v in sweep) * 5) / 5
    line_chart(os.path.join(OUT, "charts", "ortools_time_limit.svg"),
               "OR-Tools: what more search time buys",
               "Mean extra distance over the best route (OR-Tools at 30 s); the app uses 5 s",
               SWEEP_S[:-1], [f"{t:g} s" for t in SWEEP_S[:-1]], sweep,
               "OR-Tools time limit (log scale)", ymax, lambda v: f"{v:.1f}%", xlog=True,
               steps=round(ymax / 0.2))


# --- report -------------------------------------------------------------------

def report(s, mf, api):
    sizes = s["sizes"]
    L = ["# Benchmark results", "",
         "Generated by `bench/analyze.py` from `runs.csv`. Read [findings.md](findings.md) for what it means.", "",
         f"Shifts per size: {s['per_size'][sizes[0]]['shifts']}. Distances are real driving distances from "
         f"the Google Distance Matrix API between {mf['places']} public Atlanta places, fetched {mf['fetched_at'][:10]}. "
         "Best route = the shortest any solver found for that shift (brute force for 7 stops, so the true optimum there; "
         "OR-Tools with 30 s for larger shifts).", ""]
    L += ["## Savings against the entered order", "",
          "Mean saving, with its 95% bootstrap interval and the range over shifts.", "",
          "| Solver | " + " | ".join(f"{k} stops" for k in sizes) + " |",
          "|---|" + "---|" * len(sizes)]
    for name in MAIN:
        cells = []
        for k in sizes:
            r = s["per_size"][k]["solvers"].get(name)
            cells.append("-" if not r else f"{pct(r['saving_mean'])} ({pct(r['saving_ci'][0])}–{pct(r['saving_ci'][1])}); "
                                           f"range {pct(r['saving_min'])} to {pct(r['saving_max'])}")
        L.append(f"| {LABEL[name]} | " + " | ".join(cells) + " |")
    L += ["", "Entered-order distance, mean: " + ", ".join(
        f"{s['per_size'][k]['entered_miles_mean']:.1f} mi ({k} stops)" for k in sizes) + ".", ""]

    L += ["## Distance from the best route", "", "![Gap to best route](charts/gap_by_size.svg)", "",
          "Mean / worst extra distance over the best route found, and how many shifts hit it exactly.", "",
          "| Solver | " + " | ".join(f"{k} stops" for k in sizes) + " |", "|---|" + "---|" * len(sizes)]
    for name in MAIN:
        cells = []
        for k in sizes:
            r = s["per_size"][k]["solvers"].get(name)
            n = s["per_size"][k]["shifts"]
            cells.append("-" if not r else f"{pct(r['gap_mean'])} / {pct(r['gap_max'])}; best on {r['found_best']}/{n}")
        L.append(f"| {LABEL[name]} | " + " | ".join(cells) + " |")

    L += ["", "## OR-Tools against the other heuristics (paired by shift)", "",
          "| Stops | vs 2-opt: mean shorter (95% CI) | wins / ties / losses | vs nearest neighbor: mean shorter (95% CI) | miles saved vs nearest neighbor |",
          "|---|---|---|---|---|"]
    for k in sizes:
        a, b = s["per_size"][k]["ortools_vs_2opt"], s["per_size"][k]["ortools_vs_nn"]
        L.append(f"| {k} | {pct(a['mean'])} ({pct(a['ci'][0])}–{pct(a['ci'][1])}) | {a['wins']} / {a['ties']} / {a['losses']} | "
                 f"{pct(b['mean'])} ({pct(b['ci'][0])}–{pct(b['ci'][1])}) | {b['miles_saved_mean']:.2f} mi |")

    L += ["", "## OR-Tools time limit", "", "![OR-Tools time limit](charts/ortools_time_limit.svg)", "",
          "Mean extra distance over the best route found.", "",
          "| Stops | " + " | ".join(f"{t:g} s" for t in SWEEP_S) + " |", "|---|" + "---|" * len(SWEEP_S)]
    for k in sizes:
        r = s["per_size"][k]["solvers"]
        L.append(f"| {k} | " + " | ".join(pct(r[n]["gap_mean"]) if n in r else "-" for n in SWEEP) + " |")

    L += ["", "## Solver time", "", "Median wall-clock time per shift (8 shifts solved in parallel).", "",
          "| Solver | " + " | ".join(f"{k} stops" for k in sizes) + " |", "|---|" + "---|" * len(sizes)]
    for name in MAIN:
        cells = []
        for k in sizes:
            r = s["per_size"][k]["solvers"].get(name)
            cells.append("-" if not r else (f"{r['time_ms_median']:.2f} ms" if r["time_ms_median"] < 100
                                            else f"{r['time_ms_median'] / 1000:.2f} s"))
        L.append(f"| {LABEL[name]} | " + " | ".join(cells) + " |")

    L += ["", "## Google Maps requests per optimize call", "",
          "Counted by `bench/api_calls.py`, which runs the backend's request code against a stubbed network.", "",
          "| Stops | Geocoding | Distance Matrix requests (elements) | Largest matrix request | Directions | Most waypoints | Total |",
          "|---|---|---|---|---|---|---|"]
    for r in api:
        L.append(f"| {r['stops']} | {r['geocode']} | {r['distance_matrix']} ({r['matrix_elements']:,}) | "
                 f"{r['max_elements']} elements | {r['directions']} | {r['max_waypoints']} | {r['total_requests']} |")

    L += ["", "## The distance matrix", "",
          f"- {mf['asymmetric_pairs']} of {mf['pairs']} place pairs have a different distance each way; "
          f"{mf['asymmetry_over_10pct']} differ by more than 10% (median {pct(mf['asymmetry_median'])}, "
          f"max {pct(mf['asymmetry_max'])}).",
          f"- \"Atlanta Botanical Garden, Atlanta, GA\" geocoded to {mf['garden_coords'][0]:.4f}, {mf['garden_coords'][1]:.4f}, "
          f"{mf['garden_to_piedmont_park_m'] / 1000:.1f} km by road from Piedmont Park, which the garden borders.", ""]
    with open(os.path.join(OUT, "results.md"), "w") as f:
        f.write("\n".join(L))


def main():
    by_shift, times = load()
    s = summarize(by_shift, times)
    mf = matrix_facts()
    api_path = os.path.join(OUT, "api_calls.json")
    api = json.load(open(api_path)) if os.path.exists(api_path) else []
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump({"matrix": mf, **s}, f, indent=1)
    charts(s)
    report(s, mf, api)
    print(f"Wrote {OUT}/results.md, summary.json, charts/")


if __name__ == "__main__":
    main()
