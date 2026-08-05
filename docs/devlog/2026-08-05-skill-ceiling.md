# The skill ceiling: measuring the wall, then reaching most of it

**Date:** 2026-08-05  
**GSoC deliverables:** D2, D5, D7

Week 11 of 13, third session. The persistent embarrassment of irrigation ML
is that soil moisture is close to a martingale, so point forecasts cannot
beat persistence, yet papers keep publishing MAE wins against weaker
baselines. Our own ladder respected that: fifteen point-forecast families
lost, and rung 14 only won by switching to CRPS with the center held at
persistence. This session asked the question the field skips entirely: how
much probabilistic skill does the record contain at all?

## The theorem

For a martingale state written as y = mu + sigma * Z, persistence scored as
a point mass has mean CRPS equal to mean(sigma) * E|Z|, and the ideal
calibrated forecaster has expected CRPS equal to mean(sigma) * 0.5 * GMD(Z),
half the Gini mean difference of the standardized innovation. The maximum
attainable CRPS skill is therefore

    ceiling = 1 - 0.5 * GMD(Z) / E|Z|

a pure shape functional: no volatility, no horizon, no units. Gaussian
innovations give 1 - 1/sqrt(2), about 0.2929. Laplace gives exactly 1/4,
uniform exactly 1/3, and heavier tails push the ceiling down. This imports
the habit quantitative finance has and agricultural ML lacks: before
claiming skill, compute what skill is available.

On our record every training-shape ceiling lands between 0.112 and 0.283,
all below the Gaussian value. The innovations are heavy tailed on every
probe at every horizon, which caps attainable skill and retroactively
explains rung 14's over-covering 50 percent intervals.

## The bound that cannot be gamed

The first oracle attempt was wrong, and the failure was instructive: a
pooled unweighted GMD times mean sigma is not a bound, because the EWMA
sigma lags jumps and is therefore dependent with the standardized error
magnitude. The fix came from propriety. CRPS is proper and positively
homogeneous, so among laws mu + sigma * S with one shape S per fold, the
hindsight-optimal shape is the sigma-weighted empirical law of the fold's
own errors, and its realized total CRPS collapses to
0.5 * weighted_GMD(u, sigma) * sum(sigma). That is exactly computable per
fold, and no single-shape forecaster can beat it, causal or not. Efficiency
against this oracle is bounded by one deterministically, which makes it the
overfit-robust attainment metric the user story asked for. It is now policy
for probabilistic D2 rungs as ADR-0011.

## The ensemble that collects it

Filtered historical simulation, the same import from market risk that fixed
the first-passage tails: predictive law mu + sigma * {z_i} with {z_i} the
standardized training-fold persistence errors, thinned to 512 quantile
points. No fitted parameters at all beyond the error sample. It beats the
rung-14 Gaussian in all 20 probe/horizon cells (mean skill 0.193 to 0.306),
and its worst walk-forward fold is positive in all 20, making it the first
challenger family out of sixteen to pass the ADR-0003 gate, repairing the
three cells the Gaussian failed. It captures 64 to 88 percent of the exact
hindsight optimum. A recency-and-sigma-weighted variant raises the
worst-fold floor from +0.093 to +0.146 and wins 17 of 20 cells, but gives
back skill on the dry outlier probe, so plain FHS keeps the uniform-
dominance crown. The residual 12 to 36 percent is conditional-shape
information, now the identified frontier rather than a mystery.

## Status

Research, not promoted: the point endpoint is untouched and persistence
stays served. The full write-up is the
[skill-ceiling report](../reports/2026-08-05-skill-ceiling.md), the policy
is [ADR-0011](../adr/0011-skill-ceiling-evaluation.md), code is
`vine.d2_irrigation.ceiling` (18 tests, closed forms brute-force checked,
oracle bound unit-tested as an invariant), and the gate is green at 332
tests. Blockers unchanged: the GitLab project for the D6 registry push and
the rotated InfluxDB token handoff.
