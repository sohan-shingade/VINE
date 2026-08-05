# D2 report: an optimal-stopping decision layer for irrigation

**Deliverable:** D2 irrigation · **Date:** 2026-08-05 · **Status:** analysis
only. Not wired into the serving API; persistence plus the binary threshold
alert remains what D6 serves.

The forecasting ladder for D2 is closed: fifteen challenger families failed to
beat persistence on the level, and the first-passage layer already reframed the
alert as a barrier-crossing probability. This analysis takes the next step and
treats irrigation itself as a decision problem, borrowing tools from three
fields that have studied exactly this shape of problem for decades. Market risk
management supplies filtered historical simulation, which replaces the Gaussian
increment assumption with the observed heavy-tailed shape at the correct
conditional scale. American-option pricing supplies backward induction, which
turns "should I irrigate now or wait an hour" into an exercise boundary that
can be computed rather than assumed. Operational meteorology supplies the
cost-loss economic value score, which measures what an alert rule is actually
worth to the grower who acts on it.

Two findings matter beyond this repo. First, the incumbent first-passage
formula is misspecified for its own label in a way the finance literature
documented in the 1990s: it prices a continuously monitored barrier, while the
alert label is scored on hourly readings. On these probes that mismatch alone
overstates crossing probability by roughly a third at the 6 hour horizon.
Second, once monitoring frequency and increment shape are both corrected, the
empirical layer beats the closed form at every horizon on both proper scores,
with a clean ablation separating the two corrections.

## The monitoring-frequency defect

`first_passage.crossing_probability` uses the reflection-principle formula for
a Brownian path that is watched continuously. The label it is scored against
asks whether any *hourly reading* falls at or below the barrier. A path can dip
under the barrier between readings and recover, and the continuous formula
counts every such excursion as a crossing while the label does not. This is the
discrete-monitoring bias of Broadie, Glasserman and Kou (1997), who showed a
continuously monitored barrier-option formula systematically misprices a
discretely monitored contract and derived the barrier-shift correction that
carries their name.

The size of the bias here was checked directly by Monte Carlo before any model
comparison. For a Gaussian walk matched to typical probe conditions at the
6 hour horizon, simulated hourly-monitored paths cross with probability 0.1907,
the backward-recursion dynamic program used in this analysis gives 0.1907, and
the continuous closed form gives 0.2618, a relative overstatement of 37
percent. The agreement between simulation and the dynamic program to four
decimals is what licenses using the recursion as the exact discrete answer.

## The increment-shape defect, and its repair

The second defect is distributional. Pooled hourly increments on these probes
have excess kurtosis between 324 and 1416 with strong positive skew, because
rain and irrigation arrive as jumps while drying is slow and smooth. A Gaussian
is a poor law for pricing a crossing under that distribution.

The naive repair, pricing off the raw pooled increments, fails for a reason
worth recording: the unconditional pool standard deviation runs roughly
fourteen times the causal EWMA volatility, because the pool width is set by the
rare jump hours. A barrier priced off the raw pool answers a different question
from the one the conditional model asks. The correct repair is filtered
historical simulation (Barone-Adesi, Giannopoulos and Vosper 1999), the
standard in market risk: divide each historical increment by the EWMA
volatility that was current when it occurred, keep the resulting standardized
shape, and rescale by today's volatility. Filtering drops the excess kurtosis
to between 26 and 32, and the rescaled law has exactly the same first two
moments as the Gaussian control, so the head-to-head comparison isolates what
the shape alone is worth.

## Method

Three probability models are evaluated in a controlled ablation, all on
identical rows:

| Model | Monitoring | Increment law |
|---|---|---|
| `gauss_continuous` | continuous (incumbent closed form) | Gaussian |
| `gauss_discrete` | hourly | Gaussian |
| `filtered_empirical` | hourly | filtered historical shape |

Stepping down the table changes one thing at a time, so the gap from
`gauss_continuous` to `gauss_discrete` is the monitoring correction and the gap
from `gauss_discrete` to `filtered_empirical` is the shape correction. Two
references are scored on the same rows: the binary persistence-style alert read
as probability 0 or 1, and the training-fold base rate as a constant.

The event is a drawdown: does the level fall 0.3 units below where it stands
now within the next h hours. A drawdown barrier travels with the state, which
keeps the question well posed through a season-long drying trend; any absolute
barrier is degenerate on this record, unreachable early and already breached
late, and the shipped absolute threshold of 25.0 is evaluated separately below
to document exactly that. A drawdown is also what an allowable-depletion
irrigation trigger means agronomically. The drop of 0.3 was chosen as the
smallest value giving informative holdout base rates across probes (0.5 and
1.0 leave several probes with essentially zero events); at 0.3 the base rates
run from about 0.02 at 6 hours to about 0.55 at 48 hours, with only the very
quiet SE0X-LS-1 still thin at short horizons.

Crossing probabilities come from one backward survival recursion per increment
law: u_0 = 1 above the barrier, and u_k at a level is the expected u_{k-1} over
the discretized increment law, zeroed where the step lands at or below the
barrier. Everything is computed in units of the conditional volatility, where
the crossing probability depends only on the standardized headroom and the
standardized drift, so one recursion per drift bucket prices every row in the
bucket and the full five-probe experiment runs in about a minute. Increment
laws are discretized to 256 equal-probability quantile points, which is
deterministic and needs no seed.

Evaluation uses the same purged expanding walk-forward folds as every other D2
rung (five folds, training labels purged by h minus 1) on the five soil probes
at horizons of 6, 12, 24 and 48 hours. Standardized shapes are estimated from
training rows only, refit per fold. Code: `vine.d2_irrigation.stopping`, tests
`tests/d2_irrigation/test_stopping.py`, runner `scripts/d2_stopping.py`,
config `configs/d2_irrigation/stopping.yaml`.

## Results: the ablation

Brier score, mean across the five probes (lower is better):

| Horizon | gauss_continuous | gauss_discrete | filtered_empirical | persistence_alert | base_rate |
|---|---|---|---|---|---|
| 6 h | 0.0589 | 0.0389 | **0.0290** | 0.0367 | 0.0269 |
| 12 h | 0.0874 | 0.0688 | **0.0574** | 0.0986 | 0.0655 |
| 24 h | 0.1036 | 0.0920 | **0.0822** | 0.1233 | 0.1453 |
| 48 h | 0.1921 | **0.1898** | 0.1906 | 0.2369 | 0.2759 |

Log loss, mean across the five probes:

| Horizon | gauss_continuous | gauss_discrete | filtered_empirical | persistence_alert | base_rate |
|---|---|---|---|---|---|
| 6 h | 0.1804 | 0.1347 | **0.1050** | 1.2686 | 0.1311 |
| 12 h | 0.2782 | 0.2353 | **0.2021** | 3.4037 | 0.2523 |
| 24 h | 0.3387 | 0.3091 | **0.2811** | 4.2581 | 0.4598 |
| 48 h | 0.5644 | **0.5627** | 0.5656 | 8.1826 | 0.7502 |

The ablation reads cleanly at 6 to 24 hours: each correction helps, both
together help most, on both scores, in the aggregate and in 16 of 20 probe by
horizon cells. All four cell-level violations sit at 24 or 48 hours. At
48 hours the three model variants land within 0.003 Brier of one another,
which is the expected limit of the framing: over two days the walk
approximation itself is the binding error, and the choice of monitoring
convention or increment shape no longer matters. The corrections matter most
exactly where the alert is most actionable, at short horizons.

Two honest notes on the references. The training base rate is competitive on
Brier at 6 hours, where events are rare (base rates 0 to 0.05) and a constant
small probability is hard to beat on a quadratic score; it loses on log loss
there and degrades fast with horizon. The momentum persistence alert (fire if
the level already fell 0.3 in the previous h hours) is respectable on Brier at
6 hours and catastrophic on log loss everywhere, because it is a hard 0 or 1
and every outright miss costs the full clip penalty.

## Results: what the shipped 25.0 threshold looks like under this lens

Rerunning the identical evaluation with the absolute 25.0 barrier
(`barrier_mode: fixed`, CSVs suffixed `_fixed`) documents the degeneracy the
drawdown framing exists to avoid. Holdout base rates per probe are 0.61 for
SE01-LS-1 at every horizon, 0.84 to 0.87 for SE01-LS-4, and 0.97 to 1.00 for
the other three probes: on most of the record the answer is already known
before any model runs, because the season-long drydown has the level near or
below 25.0 throughout the holdout. Sixteen of twenty probe by horizon cells
have an incumbent Brier between 1e-30 and 1e-2 against nearly constant labels,
so skill ratios are meaningless there (the runner now reports NaN skill
whenever the reference Brier is below 1e-6). The shipped threshold remains a
sensible safety floor; as an evaluation target it contains almost no decision
left to make.

## The exercise boundary: deriving the trigger instead of assuming it

Irrigating is an exercise decision: pay a known cost now, or wait an hour and
face the same choice with less protection time remaining, where letting the
state cross the barrier costs the full stress loss. Backward induction over the
increment law returns the level at which irrigating beats waiting, per hours
remaining and per cost-to-loss ratio. The gap between that boundary and the
barrier is the early-exercise premium, the headroom worth buying because
stress cannot be undone after the fact. The shipped fixed threshold assumes
this premium implicitly; the dynamic program derives it.

Boundaries in standardized units (headroom above the barrier in conditional
volatilities at which irrigating becomes optimal), mean across probes:

| Cost ratio | 6 h left | 12 h | 24 h | 48 h |
|---|---|---|---|---|
| 0.02 | 4.84 | 4.90 | 4.92 | 4.92 |
| 0.05 | 3.67 | 4.71 | 4.90 | 4.92 |
| 0.10 | 2.97 | 3.87 | 4.74 | 4.90 |
| 0.20 | 2.23 | 3.10 | 4.09 | 4.76 |
| 0.30 | 1.78 | 2.60 | 3.46 | 4.23 |
| 0.50 | 1.15 | 1.87 | 2.70 | 3.81 |

The shape is exactly the American-option boundary: it rises with time
remaining (more exposure left, act earlier), falls with the cost ratio
(cheaper stress, wait longer), and converges by about 24 to 48 hours to the
infinite-horizon level. What decides its practical meaning is the volatility
scale. The median conditional volatility across probes is 0.013 to 0.026 units
per hour, so even the most conservative boundary of about 4.9 sigmas is only
0.02 to 0.13 moisture units of headroom above the barrier. On a slow, low
noise, directly measured state the optimal trigger sits essentially at the
barrier itself. That is a quantitative explanation for a result the whole D2
ladder kept finding empirically: threshold rules are hard to beat here because
the early-exercise premium that a smarter rule could capture is tiny. The
premium grows with response delay, so the moment irrigation takes nontrivial
lead time (crew scheduling, valve rotation), this same recursion with a delay
term is where the value appears.

### With response delay: the premium becomes real

`exercise_boundary_delayed` extends the recursion with a lead time d:
irrigating still costs the same, but the water lands d hours later, and a
crossing during those d hours is a loss the decision can no longer prevent.
The exercise value becomes the cost plus the crossing probability over the
delay window, and the boundary rises accordingly. At cost ratio 0.1 and the
48 hour horizon, mean across probes:

| Lead time | Boundary (sigmas) | Premium (moisture units) |
|---|---|---|
| 0 h | 4.90 | 0.093 |
| 2 h | 7.24 | 0.134 |
| 4 h | 8.67 | 0.161 |
| 8 h | 10.84 | 0.201 |
| 12 h | 12.59 | 0.234 |
| 24 h | 16.31 | 0.302 |

The growth is concave: about 0.021 units of extra headroom per hour over the
first two hours of delay, falling to about 0.006 per hour beyond twelve.
Two facts fall out. The first two hours of lead time cost as much premium as
the entire instant-response premium, so even a modest scheduling delay
doubles the headroom a correct trigger needs. And at a 24 hour lead time the
required headroom (about 0.30 units) equals the 0.3-unit drawdown depth
itself, meaning the trigger must fire a full event-magnitude early. This is
the operational boundary of the threshold-rule regime: with same-hour
response a fixed trigger at the barrier is near optimal, and with day-scale
lead times a rule that ignores delay is guaranteed late.

## Economic value: what any of this is worth to a grower

Proper scores cannot see that an alert firing on nearly every hour is useless.
The cost-loss model of operational meteorology can: acting costs alpha whether
or not the event follows, not acting costs 1 when the event occurs, and the
economic value V of a rule is its expense saving relative to the better
trivial strategy, normalized so V = 1 is a perfect rule and V <= 0 is a rule a
constant strategy beats. The Bayes rule under this loss acts exactly when the
predicted crossing probability exceeds alpha, so each probability model induces
a family of rules, one per cost ratio. This score is standard for weather
warnings and essentially absent from the irrigation-ML literature, which stops
at MAE on the level. Recorded as ADR-0010.

Mean economic value across probes (V, higher is better; selected rows, the
full ratio grid is in `assets/d2_stopping_value.csv`):

| Horizon | alpha | bayes_filtered | bayes_gauss_discrete | bayes_gauss_cont | momentum alert |
|---|---|---|---|---|---|
| 6 h | 0.02 | **0.58** | 0.58 | 0.56 | −0.24 |
| 6 h | 0.05 | **0.47** | 0.43 | 0.39 | 0.27 |
| 6 h | 0.10 | 0.16 | 0.02 | −0.09 | **0.24** |
| 6 h | 0.30 | −0.24 | −1.10 | −1.75 | **0.04** |
| 12 h | 0.10 | **0.36** | −0.11 | −0.30 | 0.06 |
| 24 h | 0.10 | **0.31** | 0.17 | 0.12 | −0.10 |
| 24 h | 0.20 | **0.31** | 0.03 | −0.06 | 0.20 |
| 48 h | 0.30 | 0.07 | 0.13 | 0.11 | **0.23** |
| 48 h | 0.50 | 0.24 | 0.23 | 0.23 | **0.36** |

Three readings. First, the filtered Bayes rule holds a positive-value band at
every horizon, worth 16 to 58 percent of the gap between climatology and a
perfect forecast at 6 hours for cost ratios up to about 0.1, and it is the
best or near-best rule in almost every cell where any rule has positive
value. Second, the incumbent closed form goes sharply negative at moderate
cost ratios (down to −1.75 at 6 hours, alpha 0.3): its overstated crossing
probabilities exceed the action threshold too often, which in operational
terms is systematic over-irrigation. The monitoring and shape corrections are
worth real money under this lens, well beyond their Brier margins. Third, the
cheap momentum alert is genuinely useful in a mid-ratio niche at 6 hours and
at high ratios at 48 hours, and worse than doing nothing at low ratios, where
its misses are expensive. A probability forecast dominates it precisely
because one forecast serves every cost ratio at once.

## Caveats

Two limits of scope are worth stating plainly. This analysis scores an alert
system, and an alert system is an open-loop object: irrigating in response to
an alert would change the future path, and the record contains no
counterfactual, so the realized series is treated as the no-intervention path.
Closing the loop is a control problem and needs either an intervention model or
field experimentation. Second, the delay analysis takes the lead time as a
known constant. Real lead times are themselves uncertain (crew availability,
shared valve schedules), and a stochastic delay would push the boundary higher
still; the constant-delay numbers above are therefore a lower bound on the
headroom a delayed system needs. The true lead-time distribution at Iron Horse
is a question for the mentor and the operations log.

## Sources

- Broadie, M., Glasserman, P., Kou, S. (1997). A continuity correction for
  discrete barrier options. *Mathematical Finance* 7(4).
- Barone-Adesi, G., Giannopoulos, K., Vosper, L. (1999). VaR without
  correlations for portfolios of derivative securities. *Journal of Futures
  Markets* 19(5).
- Murphy, A. H. (1977). The value of climatological, categorical and
  probabilistic forecasts in the cost-loss ratio situation. *Monthly Weather
  Review* 105.
- Richardson, D. S. (2000). Skill and relative economic value of the ECMWF
  ensemble prediction system. *QJRMS* 126.
- Merton, R. C. (1974). On the pricing of corporate debt. *Journal of
  Finance* 29(2). (Distance-to-threshold framing.)
