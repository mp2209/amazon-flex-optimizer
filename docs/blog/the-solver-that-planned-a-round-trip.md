# Google's route solver lost to a greedy heuristic, until I asked it the right question

*November 2026. Measured with the [Amazon Flex Route Optimizer](../../README.md)
on 100 delivery shifts over real Atlanta road distances.*

An Amazon Flex shift is a car, a few hours and 30 to 40 packages. The order
you deliver them in decides how far you drive, and that is the one cost you
control. So I built an app that takes the stops and finds the shortest
route, with four solvers to compare: brute force, nearest neighbor, 2-opt
and Google's OR-Tools.

I expected OR-Tools to win easily, because it's the industry-standard
routing library. On small shifts it was the worst solver in the app, worse
than the greedy one. And the headline number the app showed drivers turned
out to say more about their input than about any solver.

## The setup

A delivery route is the traveling salesman problem with one change: you
start at the warehouse but don't come back. You finish at your last stop
and go home. That's the *open* variant, and the app is built around it.

To measure the solvers properly I fetched one real road-distance matrix
from Google for 41 public places around Atlanta, then drew 100 random
shifts from it: 25 each of 7, 15, 25 and 40 stops. Every solver routed
every shift, and every route was scored on the real driving distances.
Brute force gives the true optimum at 7 stops; above that, OR-Tools with a
30-second budget gives the best route anyone found.

## Surprise 1: the best solver was planning a trip home

On 7-stop shifts, my OR-Tools routes were on average 19.5% longer than the
optimum, and on one shift 49% longer. The greedy "drive to the nearest stop
next" heuristic, about a dozen lines of Python, was 11.9% off, and it beat
OR-Tools outright on 16 of the 25 shifts.

The cause was a single assumption. OR-Tools' routing model is built for
vehicles that return to their depot, so every route it plans is a loop. My
code took that loop and dropped the last leg. That gives a valid one-way
route, but not the best one: OR-Tools had chosen its stop order to make the
*drive home* short. On a small shift the drive home is a big share of the
loop, and optimizing for it pulls the whole route out of shape.

Nothing crashed. Every route visited every stop exactly once, the map drew
it, and OR-Tools still beat the random entered order on 99 of 100 shifts,
so the app looked like it was working. I only saw the problem when I
compared routes against brute force on small shifts, where the optimum is
known.

The fix is one line: tell OR-Tools that any leg back to the start costs
nothing. Then the cheapest loop *is* the cheapest one-way route plus a free
ride home.

| Stops | Gap to best route, before the fix | After |
|---|---|---|
| 7 | 19.5% | 0.0% |
| 15 | 10.2% | 0.0% |
| 25 | 5.2% | 0.0% |
| 40 | 6.2% | 0.1% |

After the fix, OR-Tools found the best route on 96 of 100 shifts, matched
brute force on every 7-stop shift, and never lost to 2-opt.

## Surprise 2: "you saved 75%" was mostly measuring the input

The app's shift summary compares the optimized route against the order the
stops were entered. On the benchmark that comparison looks spectacular:
43% shorter at 7 stops, 75% at 40.

But in the benchmark the entered order is random, and a random order
across a city is a terrible route. A random 40-stop order averaged 208
miles. The saving grows with shift size because a random order gets worse
faster than a good route gets longer. That number measures the baseline,
not the solver.

No driver drives a random order. The realistic alternative to an optimizer
is driving by eye, always heading to the closest stop you haven't done yet,
and that is exactly the nearest-neighbor solver. Against that:

| Stops | OR-Tools shorter than nearest neighbor | Miles saved |
|---|---|---|
| 7 | 10% | 2.4 |
| 15 | 17% | 6.8 |
| 25 | 18% | 9.2 |
| 40 | 17% | 11.1 |

That's a smaller number and an honest one: on a full shift, about 11 miles,
22 minutes and $2.78 of fuel at the app's estimates, every shift.

## Two smaller things the benchmark turned up

- **OR-Tools spends its whole time budget, always.** Its search never
  decides it's done, so the app waited 5 seconds on every shift. Up to 15
  stops, 0.2 seconds found the same routes. At 40 stops, 1 second came
  within 0.2%. Brute force solves 7 stops exactly in under 2 milliseconds.
- **The demo shift had a stop in the wrong place.** "Atlanta Botanical
  Garden, Atlanta, GA" geocoded to a spot downtown, 5.8 km from the real
  garden, and the app took the first result without question. Clean input
  data is part of the route.

## What I'd tell someone building the same thing

- **Check the model's assumptions against your problem.** A solver built
  for round trips will happily optimize your one-way route as a round trip.
  Libraries don't know your problem variant unless you encode it.
- **Keep a slow, exact solver around as a referee.** Brute force is useless
  at 40 stops but perfect at 7. That's the only reason I found the bug.
- **Pick the baseline before the headline.** "Saves 75%" against a random
  order and "saves 17%" against driving by eye describe the same route.
  Only the second one tells a driver what the app is worth.

## Caveats

One city, one distance matrix with no traffic, and shifts drawn from 41
landmarks spread about 10 miles across Atlanta, which is looser than a real
delivery block. The entered order is random because I have no real Flex
itineraries; that's why the comparison that matters here is against nearest
neighbor. The method, every table and the raw routes are in the
[findings](../../bench/results/findings.md).
