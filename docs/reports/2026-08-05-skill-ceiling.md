# D2 report: the CRPS skill ceiling and the ensemble that attains most of it

**Deliverable:** D2 irrigation · **Date:** 2026-08-05 · **Status:** challenger
family 16, evaluated. First family out of sixteen to pass the strict
ADR-0003 worst-fold gate in all 20 probe/horizon cells. Persistence stays
served for the point endpoint; whether a probabilistic D6 product is wanted
is a mentor decision, so nothing is promoted.

## The question this rung answers

Rung 14 established that a calibrated spread around the persistence center
beats the persistence point mass on CRPS in every cell. That result invites
an obvious follow-up that the irrigation-ML literature never asks: how much
CRPS skill is attainable at all? Without an answer, "+0.19 mean skill" has
no denominator. A model could be leaving half the available skill on the
table and nobody would know. This rung derives the answer in closed form,
turns it into an efficiency metric that is robust to overfitting by
construction, and then builds the ensemble that collects most of it.

## The ceiling theorem

Soil moisture is close to a martingale, which is why fifteen point-forecast
families lost to persistence. Write the h-step observation as

    y_t = mu_t + sigma_t * Z

with mu_t the persistence level, sigma_t the conditional scale of the h-step
innovation, and Z the standardized innovation with law F. Two identities pin
down both ends of the comparison.

First, the CRPS of a point mass equals its absolute error, so persistence's
mean CRPS is E[sigma_t] * E|Z|. Second, the best possible probabilistic
forecaster, the one issuing the true conditional law each hour, has expected
CRPS equal to half the expected Gini mean difference (GMD) of that law,
which standardizes to E[sigma_t] * 0.5 * GMD(Z). Dividing, the maximum
attainable CRPS skill against the persistence point mass is

    ceiling = 1 - 0.5 * GMD(Z) / E|Z|

a pure shape functional of the standardized innovation. It does not depend
on the volatility level, the horizon, or the units. Closed forms for
reference shapes:

| Shape of Z | Ceiling |
|---|---|
| Gaussian | 1 - 1/sqrt(2) = 0.2929 |
| Uniform | 1/3 |
| Laplace | 1/4 exactly |
| Heavier tails | lower still |

The Gaussian value 0.2929 is the number the whole probabilistic-forecasting
exercise orbits: if innovations were Gaussian, no forecaster of any
complexity could exceed 29.3 percent CRPS skill over persistence, and
heavier tails push the bar down. The rung-14 Gaussian's mean skill of 0.193
was, it turns out, already two thirds of what this record allows.

## The exact hindsight bound

The population theorem needs an empirical counterpart that is a true bound
on realized scores. The training-shape estimate is not one: holdout
innovations here are lighter tailed than the full training history, so
realized skill exceeds the training-shape ceiling in 19 of 20 cells. The
honest yardstick comes from a different argument. CRPS is a proper score
and positively homogeneous, so among predictive laws of the form
mu_t + sigma_t * S with one shape S per evaluation fold, the shape that
minimizes the realized total CRPS on that fold is the sigma-weighted
empirical law of the fold's own standardized errors, and its realized total
collapses to a closed form:

    0.5 * weighted_GMD(u, sigma) * sum(sigma)

with weighted_GMD(u, sigma) = sum_ij sigma_i sigma_j |u_i - u_j| / (sum
sigma)^2. This is computable exactly per fold, it uses the test rows
themselves, and no sigma-scaled single-shape forecaster, causal or not, can
beat it on this record. The `ceiling_oracle` column is the skill this
hindsight optimum achieves; `efficiency_oracle` is achieved skill divided by
it, and it is less than or equal to one deterministically (unit-tested as an
invariant). The oracle exceeds the population ceiling in most cells because
it adapts a fresh shape to each fold's realized errors and exploits the
dependence between the EWMA sigma and the error magnitude; the gap between
the two is finite-sample hindsight, which is exactly why efficiency against
the oracle is a conservative metric.

## Models

1. `persistence-point`: the served baseline as a point mass, the skill
   reference.
2. `gaussian-ewma`: the rung-14 frontier. Gaussian around persistence with
   the causal EWMA sigma (halflife 72 pairs, warmup 24).
3. `fhs-ewma`: filtered historical simulation. The predictive law is
   mu_t + sigma_t * {z_i} where {z_i} are the standardized training-fold
   persistence errors, sorted and deterministically thinned to at most 512
   quantile points. Same center, same sigma as the Gaussian; the only change
   is the shape, which is now the data's own instead of assumed. Scored with
   the pooled-sample empirical CRPS, scaled by sigma via positive
   homogeneity.
4. `fhs-adaptive`: the same recipe with the training errors weighted by
   their own sigma and by exponential recency (halflife 500 rows) before the
   shape is formed. This is the causal analogue of the sigma-weighted
   hindsight optimum and is designed to track seasonal drift of the
   innovation shape.

## Method

The shared purged expanding walk-forward harness: five folds over the second
half of each probe's history, training labels purged by h minus 1, all
models scored on identical rows, five probes, horizons 6/12/24/48 h. Per
cell the table reports skill (aggregate, fold median, fold min), the
training-shape ceiling, the oracle ceiling, efficiency against each, and
central-interval coverage. The overfit-robustness of the metric package
comes from three design choices: the ceiling denominators are either causal
(training shape) or deterministic bounds (oracle), the gate is the worst
walk-forward fold rather than the mean, and the challenger has no fitted
parameters beyond the error sample itself. Code:
`vine.d2_irrigation.ceiling` (18 tests, including brute-force checks of both
GMD identities, the three closed-form ceilings, an attainment test where the
FHS recipe reaches the Laplace ceiling while a variance-matched Gaussian
falls short, and the oracle-bound invariant), runner `scripts/d2_ceiling.py`,
config `configs/d2_irrigation/ceiling.yaml`.

## Results

CRPS skill vs the persistence point mass. FHS efficiency is against the
oracle ceiling. Full table with coverage columns in
`assets/d2_ceiling_results.csv`.

| Probe | Horizon | Ceiling (train) | Oracle ceiling | Gaussian skill | FHS skill | FHS fold min | FHS eff. | Adaptive skill | Adaptive fold min |
|---|---|---|---|---|---|---|---|---|---|
| SE01-LS-1 | 6 h | 0.195 | 0.298 | +0.194 | **+0.261** | +0.225 | 0.88 | +0.268 | +0.200 |
| SE01-LS-1 | 12 h | 0.208 | 0.367 | +0.210 | **+0.306** | +0.280 | 0.83 | +0.326 | +0.271 |
| SE01-LS-1 | 24 h | 0.222 | 0.502 | +0.218 | **+0.379** | +0.221 | 0.76 | +0.422 | +0.372 |
| SE01-LS-1 | 48 h | 0.222 | 0.560 | +0.246 | **+0.368** | +0.093 | 0.66 | +0.430 | +0.373 |
| SE01-LS-2 | 6 h | 0.166 | 0.304 | +0.188 | **+0.258** | +0.229 | 0.85 | +0.265 | +0.255 |
| SE01-LS-2 | 12 h | 0.167 | 0.330 | +0.173 | **+0.276** | +0.249 | 0.84 | +0.287 | +0.274 |
| SE01-LS-2 | 24 h | 0.192 | 0.428 | +0.159 | **+0.310** | +0.252 | 0.73 | +0.354 | +0.317 |
| SE01-LS-2 | 48 h | 0.199 | 0.512 | +0.228 | **+0.334** | +0.273 | 0.65 | +0.422 | +0.383 |
| SE01-LS-3 | 6 h | 0.201 | 0.260 | +0.161 | **+0.211** | +0.163 | 0.81 | +0.217 | +0.187 |
| SE01-LS-3 | 12 h | 0.218 | 0.308 | +0.180 | **+0.257** | +0.228 | 0.83 | +0.266 | +0.248 |
| SE01-LS-3 | 24 h | 0.262 | 0.414 | +0.173 | **+0.330** | +0.289 | 0.80 | +0.354 | +0.307 |
| SE01-LS-3 | 48 h | 0.283 | 0.502 | +0.239 | **+0.364** | +0.239 | 0.73 | +0.391 | +0.324 |
| SE01-LS-4 | 6 h | 0.112 | 0.208 | +0.094 | **+0.169** | +0.120 | 0.81 | +0.180 | +0.146 |
| SE01-LS-4 | 12 h | 0.122 | 0.258 | +0.095 | **+0.192** | +0.118 | 0.74 | +0.212 | +0.163 |
| SE01-LS-4 | 24 h | 0.168 | 0.410 | +0.126 | **+0.270** | +0.120 | 0.66 | +0.305 | +0.205 |
| SE01-LS-4 | 48 h | 0.206 | 0.502 | +0.189 | **+0.320** | +0.127 | 0.64 | +0.371 | +0.236 |
| SE0X-LS-1 | 6 h | 0.152 | 0.357 | +0.250 | **+0.314** | +0.281 | 0.88 | +0.244 | +0.221 |
| SE0X-LS-1 | 12 h | 0.152 | 0.407 | +0.235 | **+0.348** | +0.297 | 0.85 | +0.269 | +0.247 |
| SE0X-LS-1 | 24 h | 0.167 | 0.521 | +0.231 | **+0.418** | +0.346 | 0.80 | +0.362 | +0.298 |
| SE0X-LS-1 | 48 h | 0.184 | 0.580 | +0.266 | **+0.426** | +0.335 | 0.73 | +0.431 | +0.360 |

Four findings.

**The tails are heavy, quantifiably.** Every training-shape ceiling (0.112
to 0.283) sits below the Gaussian 0.2929. The standardized innovations of
this record are heavier tailed than Gaussian on every probe at every
horizon, which caps what any forecaster can earn and explains why the
Gaussian's cov50 over-covered on rung 14.

**FHS breaks the frontier uniformly.** `fhs-ewma` beats `gaussian-ewma` in
all 20 cells, lifting mean skill from 0.193 to 0.306 (a 62 percent mean
relative improvement) with aggregate skill from +0.169 to +0.426. Its
worst-fold skill is positive in all 20 cells (minimum +0.093, SE01-LS-1 at
48 h), so it is the first challenger family out of sixteen to pass the
ADR-0003 worst-fold gate, and it repairs the three cells the Gaussian
failed. The only change from the Gaussian is the shape of the spread, so
the entire gain is attributable to using the empirical error law instead of
a Gaussian assumption.

**The adaptive variant raises the floor further, at a cost.** `fhs-adaptive`
beats plain FHS in 17 of 20 cells, lifts mean skill to 0.319, raises the
worst-fold floor from +0.093 to +0.146, and lifts mean oracle efficiency
from 0.774 to 0.804. Its three losses are all on SE0X-LS-1 (at 6, 12, and
24 h, by 0.056 to 0.079 skill), the probe that reads far drier than the
fleet; there the full-history shape is evidently stable and recency
weighting discards useful data. At SE0X-LS-1 6 h it also slips below the
Gaussian (+0.244 vs +0.250), so plain `fhs-ewma` remains the variant with
uniform dominance over the old frontier.

**Attainment is high and the residual is identified.** FHS collects 64 to
88 percent of the exact hindsight optimum (mean 77 percent); the Gaussian
managed 31 to 70 percent (mean 49). The remaining gap is conditional-shape
information: the oracle re-fits the shape per fold with hindsight, so what
separates FHS from it is shape drift within and across folds. The adaptive
variant closing part of that gap on 17 cells confirms the diagnosis.
Efficiency declines with horizon in every probe, so long-horizon conditional
shape is where the remaining skill lives.

## Calibration caveat

FHS wins CRPS with sharper intervals: cov50 runs 0.343 to 0.701 against the
0.50 target and the adaptive variant is sharper still (0.118 to 0.517),
under-covering where the Gaussian over-covered. cov90 stays reasonable for
plain FHS (0.885 to 0.988) and degrades for the adaptive variant on
SE0X-LS-1 (0.696 at 48 h). CRPS is proper, so the ranking is honest, and the
empirical shape concentrates mass near zero because most hours barely move.
Anyone consuming these intervals operationally should recalibrate the
central quantiles first; the CRPS ordering is unaffected.

## Limitations

- The training-shape ceiling is an estimate of a population quantity, not a
  bound on realized skill; on this record it is exceeded whenever the
  holdout is calmer than the training history. The oracle ceiling is the
  bound. Both are reported.
- The oracle is restricted to sigma-scaled single-shape laws sharing the
  persistence center and the EWMA sigma. A forecaster that improves the
  center or the sigma path could in principle exceed it; fifteen failed
  center attempts say the center is not where the room is.
- The adaptive halflife (500 rows) was fixed a priori, not tuned. No per
  cell selection was performed anywhere.
- Cells within a probe share overlapping h-step errors, so the 20 cells are
  correlated.
- One vineyard, one season. The heavy-tail finding (every ceiling below
  0.2929) should be re-measured after a second wet season.

## Verdict

The frontier moved, and for the first time the distance to the wall is
measured. Persistence stays served for the point endpoint: nothing here
touches the forecast center, and D6 is unchanged. Within the probabilistic
lane, `fhs-ewma` dominates the previous frontier in every cell and passes
the gate everywhere; `fhs-adaptive` is the higher-mean, higher-floor variant
with a known weakness on the dry probe. If a probabilistic D6 product is
wanted, plain FHS is the recipe to ship, with quantile recalibration as the
first refinement and conditional-shape modeling as the identified residual
frontier.

Artifacts: `assets/d2_ceiling_results.csv`. Run logged to MLflow experiment
`d2_irrigation`, run name `skill-ceiling`, run id
`94253f29c4324271875f5ce48e7b3d07`.
