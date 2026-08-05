# D2 report: first-passage probabilities for the irrigation alert

**Deliverable:** D2 irrigation · **Date:** 2026-08-05 · **Status:** analysis
only. Not wired into the serving API; persistence plus the binary threshold
alert remains what D6 serves.

Twelve challenger families failed to beat persistence on level MAE, which is
strong evidence that soil moisture is close to a random walk at these
horizons. This analysis stops fighting that conclusion and changes the
question instead. What the irrigation decision actually needs is the answer to
"will moisture fall below 25.0 within the next h hours", and for a random walk
that question has a closed-form answer. This is the same move finance makes
when pricing a barrier option or a default probability: accept the random
walk, then compute the probability that the path touches a barrier. The output
becomes a calibrated probability instead of a hard yes or no.

## Method

At each decision hour t the future path over (t, t+h] is modeled as a Gaussian
random walk starting at the last observed level, with per-hour drift mu and
volatility sigma estimated strictly from the past. Sigma is an EWMA of squared
hourly deltas (halflife 72 gap-free pairs); deltas are only taken over
consecutive-hour pairs where both ends are observed, so gaps are never
imputed or bridged. Mu is either zero or a slow EWMA of the same deltas
(halflife 336 pairs); both variants were evaluated. The crossing probability
is the Brownian first-passage formula from the reflection principle with
drift; a level already at or below the threshold is probability 1, and as
sigma approaches zero the formula degenerates to a step function on the
drifted level. Code: `vine.d2_irrigation.first_passage`, tests
`tests/d2_irrigation/test_first_passage.py`, runner
`scripts/d2_first_passage.py`, config `configs/d2_irrigation/first_passage.yaml`.

Evaluation uses the same purged expanding walk-forward folds as every other D2
rung (five folds over the second half of each probe's history, training labels
purged by h minus 1) on the five soil probes, at horizons of 6, 12, 24, and
48 hours. The outcome for decision hour t is whether the observed series
actually dropped below 25.0 within (t, t+h]; only windows with every hour
observed count, and windows containing gaps are skipped. Scores are Brier
score and log loss against two references scored on identical rows: the
current binary persistence alert read as probability 0 or 1, and the
training-fold crossing base rate as a constant probability. Log loss clips
probabilities at 1e-15, so each wrong binary alert costs about 34.5 nats;
Brier is the fairer number for the binary reference.

## Results, pooled across the five probes

Brier score (lower is better):

| Horizon | n | Crossed | First-passage (drift) | First-passage (zero) | Persistence alert | Base rate |
|---|---|---|---|---|---|---|
| 6 h | 6,970 | 6,166 | 0.0089 | 0.0090 | **0.0056** | 0.1146 |
| 12 h | 6,880 | 6,110 | **0.0091** | 0.0093 | 0.0094 | 0.1110 |
| 24 h | 6,700 | 5,979 | **0.0092** | 0.0094 | 0.0149 | 0.1058 |
| 48 h | 6,340 | 5,674 | **0.0099** | 0.0103 | 0.0203 | 0.1012 |

Log loss (lower is better):

| Horizon | First-passage (drift) | First-passage (zero) | Persistence alert | Base rate |
|---|---|---|---|---|
| 6 h | **0.0603** | 0.0606 | 0.1933 | 0.3492 |
| 12 h | **0.0426** | 0.0431 | 0.3263 | 0.3360 |
| 24 h | **0.0350** | 0.0355 | 0.5155 | 0.3159 |
| 48 h | **0.0320** | 0.0328 | 0.7028 | 0.2961 |

The binary alert is sharper at 6 hours, where the situation is nearly
deterministic and hedged probabilities near the threshold only add error. From
12 hours out the probabilities win on Brier, and the margin grows with
horizon: at 48 hours the first-passage Brier is roughly half the binary
alert's. On log loss the probabilities win everywhere, though the binary
reference's log loss is dominated by the clip penalty on its outright misses.
The slow drift EWMA calibrated slightly better than zero drift at every
horizon, so drift is the kept default; both stay available as parameters.

Evaluable windows per probe (n, crossed):

| Probe | 6 h | 12 h | 24 h | 48 h |
|---|---|---|---|---|
| SE01-LS-1 | 1,394 / 852 | 1,376 / 840 | 1,340 / 816 | 1,268 / 768 |
| SE01-LS-2 | 1,394 / 1,358 | 1,376 / 1,352 | 1,340 / 1,333 | 1,268 / 1,268 |
| SE01-LS-3 | 1,394 / 1,394 | 1,376 / 1,376 | 1,340 / 1,340 | 1,268 / 1,268 |
| SE01-LS-4 | 1,394 / 1,168 | 1,376 / 1,166 | 1,340 / 1,150 | 1,268 / 1,102 |
| SE0X-LS-1 | 1,394 / 1,394 | 1,376 / 1,376 | 1,340 / 1,340 | 1,268 / 1,268 |

Three probes are nearly or fully degenerate in the holdout. SE01-LS-3 and
SE0X-LS-1 sit below the threshold throughout, so every window crosses and all
forecasters score near zero. SE01-LS-1 separates perfectly (every crossing
window was already below the threshold at decision time), so all three
forecasters are exact there too. The pooled differences come almost entirely
from SE01-LS-2 and SE01-LS-4, the probes whose holdouts actually hover around
the threshold.

## Reliability (kept model, pooled across probes)

Predicted-probability deciles vs observed crossing frequency at 24 and
48 hours; the 6 and 12 hour patterns match, and the full table for both
models is in `assets/d2_first_passage_reliability.csv`.

| Bin | 24 h n | 24 h mean p | 24 h observed | 48 h n | 48 h mean p | 48 h observed |
|---|---|---|---|---|---|---|
| 0.0 to 0.1 | 542 | 0.001 | 0.000 | 512 | 0.001 | 0.000 |
| 0.1 to 0.2 | 18 | 0.158 | 0.111 | 5 | 0.147 | 0.000 |
| 0.2 to 0.3 | 30 | 0.251 | 0.100 | 11 | 0.266 | 0.273 |
| 0.3 to 0.4 | 15 | 0.345 | 0.067 | 24 | 0.359 | 0.250 |
| 0.4 to 0.5 | 25 | 0.453 | 0.040 | 21 | 0.443 | 0.095 |
| 0.5 to 0.6 | 29 | 0.546 | 0.138 | 32 | 0.566 | 0.062 |
| 0.6 to 0.7 | 47 | 0.646 | 0.234 | 26 | 0.653 | 0.154 |
| 0.7 to 0.8 | 21 | 0.732 | 0.476 | 66 | 0.748 | 0.258 |
| 0.8 to 0.9 | 30 | 0.824 | 0.200 | 33 | 0.862 | 0.939 |
| 0.9 to 1.0 | 5,943 | 1.000 | 1.000 | 5,610 | 1.000 | 1.000 |

About 97% of decision hours land in the two extreme deciles, and those are
well calibrated (the 0.9 to 1.0 bin observes 0.994 to 1.000 across horizons,
the 0.0 to 0.1 bin observes 0.000). The middle deciles are overconfident:
predicted probabilities of 0.3 to 0.8 correspond to observed crossing rates
well below the prediction (at 48 hours the 0.5 to 0.6 bin predicts 0.566 and
observes 0.062). Only the 0.8 to 0.9 bin at 48 hours runs underconfident.
The honest reading is that the model is trustworthy when it is nearly sure
either way, and overstates the risk in the genuinely uncertain middle, which
holds roughly 160 to 220 hours per horizon.

## Limitations

- The Gaussian independent-increment assumption is wrong in detail. The
  series has diurnal structure and upward jumps from rain and irrigation, and
  its volatility clusters in storms; the mid-range overconfidence is the
  expected symptom, since near-threshold levels revert or jump up more often
  than a driftless walk allows.
- Three of five probes are degenerate in the holdout (always crossing or
  perfectly separated), so the base-rate reference collapses to a constant
  near 1.0 there and the pooled comparison is really carried by two probes.
- Most evaluable windows are easy: a window already below the threshold at
  decision time is trivially probability 1. The scores therefore flatter
  every forecaster; the informative rows are the few hundred mid-range hours.
- The log-loss comparison against a hard 0/1 forecaster depends on the clip
  value; Brier is the comparison to trust for the binary reference.
- Windows overlapping the shared data outages are skipped, which removes much
  of the late dry season from the evaluation.
- This is an analysis, and it is not wired into the serving API. Promoting it
  would need an ADR and a decision-layer comparison at the operating point,
  since at 6 hours the served binary alert is still the sharper decision rule.

Artifacts: `assets/d2_first_passage_results.csv` (per-probe and pooled scores)
and `assets/d2_first_passage_reliability.csv`. Run logged to MLflow experiment
`d2_irrigation`, run name `first-passage`.
