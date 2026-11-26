# Benchmark findings

One benchmark run: 100 shifts (25 each of 7, 15, 25 and 40 stops), every
solver in the app plus five extra OR-Tools settings, 1,000 routes in all,
scored on real Atlanta driving distances. The numbers are in
[results.md](results.md), the raw routes in [runs.csv](runs.csv) and the
sampled shifts in [shifts.json](shifts.json).

## Method

**Distances.** 41 public Atlanta places ([list](../places.txt)): landmarks,
parks, campuses and stations from Buckhead to Decatur to the West End. No
homes or customer addresses. [`fetch_matrix.py`](../fetch_matrix.py)
geocoded them and fetched the full 41 x 41 driving-distance matrix from the
Google Distance Matrix API once, on 2026-11-26, with the app's own request
code: 41 geocodes, 1,681 elements in 22 requests. Every run after that is
offline, so the benchmark costs nothing to repeat and every solver sees the
same distances.

**Shifts.** [`run.py`](../run.py) draws each shift at random from the 41
places (seed 2026): a start, then K stops. The order the stops were drawn in
is the driver's "entered order", the baseline the app's shift summary
compares against.

**Solvers.** The app's own code, called the way `/optimize` calls it:
nearest neighbor, 2-opt, OR-Tools (open route, 5 s time limit) and, for 7
stops, brute force. Also run on every shift:

- OR-Tools as it was before the open-route fix: it optimizes a round trip
  back to the start, then the return leg is dropped.
- OR-Tools with time limits of 0.2, 0.5, 1 and 2 s.
- For 15 stops and up, OR-Tools with 30 s, as a reference.

**Measures.** Every route is scored on the real distances. The *best route*
for a shift is the shortest any solver found: at 7 stops that is brute
force, so the true optimum; above that it is usually the 30 s OR-Tools run.
*Gap* is a route's extra distance over the best route. Means come with a
95% bootstrap interval over shifts, and comparisons between two solvers are
paired by shift. Times are wall-clock on an Apple-silicon laptop with 8
shifts solved in parallel.

## 1. OR-Tools finds the best route almost every time, and never lost to 2-opt

| Stops | OR-Tools: best route found | Mean gap: OR-Tools | 2-opt | Nearest neighbor |
|---|---|---|---|---|
| 7 | 25 of 25 | 0.0% | 1.2% | 11.9% |
| 15 | 25 of 25 | 0.0% | 4.7% | 21.8% |
| 25 | 25 of 25 | 0.0% | 4.5% | 22.7% |
| 40 | 21 of 25 | 0.1% (worst 1.3%) | 5.8% | 21.3% |

OR-Tools at the app's 5 s setting matched the best route on 96 of 100
shifts, and on all 25 seven-stop shifts it matched brute force, so it found
the true optimum there. Against 2-opt it was shorter on 75 shifts, tied on
25 and longer on none; the gap grows with shift size, to 5.3% (4.1% to
6.5%) at 40 stops.

2-opt starts from the nearest-neighbor route and recovers most of its loss,
but stalls 4-6% short at 15 stops and up. One likely reason, not tested
here: 2-opt improves a route by reversing a stretch of it, and these
distances are not the same both ways (finding 6), so every reversal also
changes the length of each leg inside the stretch and fewer reversals pay
off.

## 2. The fair baseline is a driver who goes to the nearest stop next

The app reports savings against the order the stops were entered. Against
that baseline, OR-Tools saved 43% at 7 stops and 75% at 40. But the entered
order here is random, so most of that measures how bad a random order is,
and it grows with the shift: a random 40-stop order averaged 208 miles.

A driver doesn't drive a random order. Nearest neighbor, always heading to
the closest unvisited stop, is what a driver does by eye, and it is the
honest baseline:

| Stops | OR-Tools shorter than nearest neighbor (95% CI) | Miles saved per shift |
|---|---|---|
| 7 | 10.1% (7.5% to 12.8%) | 2.4 |
| 15 | 17.0% (13.6% to 20.5%) | 6.8 |
| 25 | 17.9% (15.5% to 20.6%) | 9.2 |
| 40 | 17.1% (15.2% to 19.2%) | 11.1 |

So on a full shift the optimizer is worth about one route in six, or 11
miles, over driving by eye. At the app's own estimates (30 mph, $0.25 a
mile), that's about 22 minutes and $2.78 a shift.

## 3. Before the fix, OR-Tools did worse than greedy on small shifts

OR-Tools' routing model always plans a loop back to the depot. The app
dropped the return leg afterwards, so OR-Tools chose the best round trip,
not the best one-way route. Measured on the same shifts:

| Stops | Mean gap before the fix | After | Nearest neighbor, for scale |
|---|---|---|---|
| 7 | 19.5% (worst 49%) | 0.0% | 11.9% |
| 15 | 10.2% | 0.0% | 21.8% |
| 25 | 5.2% | 0.0% | 22.7% |
| 40 | 6.2% | 0.1% | 21.3% |

On 7-stop shifts the old OR-Tools was further from optimal than the greedy
heuristic, and longer than it on 16 of 25 shifts; on one shift its route
was 6% longer than the random entered order. The damage shrinks as shifts grow, because the missing return leg is
a smaller share of a longer route. It never threw an error and always
returned a valid route, so nothing flagged it until the routes were checked
against brute force. The fix is one line: a leg back to the start costs 0.

## 4. Most of OR-Tools' 5 seconds buys nothing

Guided local search never stops on its own, so OR-Tools uses its full time
limit on every shift: 5.0 s for 7 stops and for 40. Brute force solves 7
stops exactly in under 2 ms (median 1.7 ms), with the same answer.

| Stops | 0.2 s | 0.5 s | 1 s | 2 s | 5 s (app) |
|---|---|---|---|---|---|
| 15 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 25 | 0.2% | 0.0% | 0.0% | 0.0% | 0.0% |
| 40 | 1.0% | 0.3% | 0.3% | 0.2% | 0.1% |

Up to 15 stops, 0.2 s already matches 5 s. At 40 stops, 1 s comes within
0.2% of 5 s, about a tenth of a mile on a 52-mile route. A limit that
scales with stop count (or brute force for the smallest shifts) would cut
most of the wait without measurably longer routes.

## 5. API batching stays inside Google's limits

Counted with [`api_calls.py`](../api_calls.py), which runs the backend's
request code against a stubbed network:

| Stops | Geocoding | Distance Matrix requests (elements) | Directions | Total |
|---|---|---|---|---|
| 7 | 8 | 1 (64) | 5 | 14 |
| 15 | 16 | 3 (256) | 4 | 23 |
| 25 | 26 | 14 (676) | 4 | 44 |
| 40 | 41 | 22 (1,681) | 8 | 71 |

No matrix request goes over 100 elements, 25 origins or 25 destinations,
and no Directions request over 25 waypoints. Two things cost more than they
need to:

- **Directions is fetched once per solver, even for the same route.** At 7
  stops, 46 of 125 Directions requests in the benchmark would repeat a
  route already fetched (OR-Tools and brute force agreed on every shift).
  Above 7 stops it's 4% or less.
- **At 25 stops the matrix takes 14 requests where 8 would do**: 26
  destinations split into batches of 25 and 1. Google bills by element, so
  this costs latency, not money.

## 6. Road distances are not the same both ways

795 of the 820 place pairs have a different driving distance each way, and
205 differ by more than 10% (median 3.9%, largest 153%): one-way streets,
highway ramps and turn restrictions make the trip back a different route. The solvers all read the
matrix in the direction of travel, so routes are scored correctly, but any
shortcut that assumes symmetry (straight-line distance, reusing A-to-B for
B-to-A, halving the matrix to save API calls) would be wrong on a quarter
of the pairs.

## 7. One place name geocoded to the wrong spot, and it's in the demo shift

"Atlanta Botanical Garden, Atlanta, GA" came back at 33.7501, -84.3885,
next to the State Capitol downtown. The garden borders Piedmont Park, 5.8
km away by road. The app takes the first geocoding result without checking
it, and this name is one of the eight stops in its "Try a Demo Shift"
button, so the demo routes a stop to the wrong place (stop 6 in the
[screenshot](../../docs/images/app-demo-shift.png)). The other 40
coordinates match where those places are. A street address, or showing each geocoded address
back to the driver, would catch it.

## Limitations

- **Random entered order.** It overstates savings against "the original
  order", which is why finding 2 uses nearest neighbor. A real Flex
  itinerary comes pre-sequenced; this benchmark has no access to one.
- **Spread-out shifts.** Stops are drawn from 41 places spread about 10
  miles across the city. A real block is usually tighter, which shortens routes
  but not, as far as this shows, the relative gaps.
- **One city, one fetch.** Atlanta only, one matrix fetched on 2026-11-26.
  Distances are Google's driving distances with no departure time, so
  traffic and time of day aren't modeled, and the solvers minimize miles,
  not minutes.
- **Best route is the best found.** Above 7 stops the reference is OR-Tools
  at 30 s, not a proven optimum; a gap of 0.0% means "no solver here found
  shorter".
- **25 shifts per size.** Enough for the paired comparisons, whose
  intervals are tight; per-size gaps of under half a percent are within
  noise.
- **Timing under load.** Shifts ran 8 at a time, so heuristic times are
  slightly pessimistic. OR-Tools times are set by its time limit either way.

## What's next

- Scale the OR-Tools time limit with stop count, or use brute force up to
  7 stops (finding 4).
- Fetch Directions once per distinct route (finding 5).
- Show the geocoded address for every stop, and switch the demo shift to
  street addresses (finding 7).
- Report savings against nearest neighbor in the shift summary, next to
  the entered order (finding 2).
