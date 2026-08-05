# D2 report: rain-gated persistence hybrid (gated water balance)

**Deliverable:** D2 irrigation · **Date:** 2026-08-05 · **Status:** evaluated,
does not ship. Persistence stays served. Weak dominance fails.

## Motivation

The event study (2026-08-05) split the vintage-forecast water-balance
evaluation by rain-event windows and found a clean structure: scored only on
event hours, the model beats persistence at 24 and 48 h on every probe with
event evidence (+0.030 to +0.626), and its aggregate 24 h losses come from
quiet hours where the correction fires with nothing happening (quiet skill
−0.104 to −0.216 on the SE01 probes at 24 h). The obvious follow-up is a
hybrid: predict persistence by default, and switch to the water-balance
forecast only when the forecast available at the origin predicts material
rain over the horizon window. This report builds that hybrid and evaluates
whether the gate preserves the event-window win while removing the quiet-hour
losses.

## Method

1. **Gate.** For each (origin, target) pair the gate reads the archived
   forecast vintage available at the origin, exactly the causal vintage
   machinery of the water-balance and event-study runs (lag `ceil(h/24)`
   days, never fresher). If the forecast precipitation summed over
   (origin, target] reaches the threshold, the hybrid emits the water-balance
   forecast; otherwise it emits persistence's exact float values, never a
   recomputation. A missing forecast never fires the gate.
2. **Threshold selection.** One global threshold from {0.5, 1.0, 2.0, 5.0} mm
   is chosen per walk-forward fold on the training window alone: the most
   recent 25 percent of the training rows is an inner holdout, the correction
   is refit on the earlier rows with the same h minus 1 label purge at the
   inner boundary, and the candidate with the lowest inner-holdout MAE wins.
   Ties go to the largest threshold, which fires least and stays closest to
   the served baseline. All four fixed thresholds are also reported so the
   sensitivity is visible.
3. **Evaluation.** Same purged expanding walk-forward as every other D2
   experiment (5 folds, h minus 1 label purge), horizons 6 to 48 h, all five
   probes. SE0X-LS-1 is included even though it has no scorable events; the
   gate still fires there on forecast rain.
4. **Subsets.** Results are split by the event mask of the event study
   (event windows plus a trailing 24 h drainage tail against quiet hours) and
   additionally scored on the fired subset, the pairs where the gate actually
   switched to the water-balance forecast.

Code: `vine.d2_irrigation.gated`, runner `scripts/d2_gated.py`, config
`configs/d2_irrigation/gated.yaml`, full table
`assets/d2_gated_results.csv`, MLflow experiment `d2_irrigation`, run
`gated-water-balance` (id `2292358f1a41441285d3c1fbcb1a06d6`).

## Selected thresholds

The causal selection is conservative: 84 of 100 fold-level selections picked
the largest candidate, 5.0 mm, because the candidates are nearly
indistinguishable on training MAE and ties resolve to the least-firing
threshold. The 16 other selections (0.5 to 2.0 mm) cluster in the folds
containing the March and April rain, where the inner holdout actually
rewards firing.

## Results: gated_wb_selected vs persistence

Aggregate skill, with worst-fold skill in parentheses:

| Probe | 6 h | 12 h | 24 h | 48 h |
|---|---|---|---|---|
| SE01-LS-1 | −0.003 (−0.084) | −0.010 (−0.114) | −0.074 (−2.399) | +0.112 (−0.504) |
| SE01-LS-2 | +0.001 (0.000) | 0.000 (0.000) | −0.052 (−1.194) | +0.057 (−0.386) |
| SE01-LS-3 | 0.000 (0.000) | 0.000 (0.000) | −0.058 (−0.559) | +0.077 (0.000) |
| SE01-LS-4 | −0.008 (−0.099) | −0.010 (−0.131) | −0.039 (−1.090) | +0.051 (−0.161) |
| SE0X-LS-1 | −0.003 (−0.073) | −0.022 (−0.355) | −0.029 (−0.518) | +0.122 (−0.268) |

Event-subset and quiet-subset skill:

| Probe | Event 24 h | Event 48 h | Quiet 24 h | Quiet 48 h |
|---|---|---|---|---|
| SE01-LS-1 | +0.297 | +0.625 | −0.213 | −0.035 |
| SE01-LS-2 | +0.180 | +0.223 | −0.170 | −0.010 |
| SE01-LS-3 | +0.026 | +0.238 | −0.106 | +0.009 |
| SE01-LS-4 | +0.127 | +0.302 | −0.108 | −0.002 |
| SE0X-LS-1 | no events | no events | −0.029 | +0.122 |

Fired-subset skill (scored only on pairs where the gate switched to the
water-balance forecast) and the fraction of scored pairs that fired:

| Probe | Fired 6 h | Fired 12 h | Fired 24 h | Fired 48 h | Frac 24 h | Frac 48 h |
|---|---|---|---|---|---|---|
| SE01-LS-1 | −0.017 | −0.042 | −0.267 | +0.421 | 0.051 | 0.085 |
| SE01-LS-2 | +0.003 | 0.000 | −0.137 | +0.167 | 0.051 | 0.088 |
| SE01-LS-3 | 0.000 | 0.000 | −0.180 | +0.246 | 0.051 | 0.088 |
| SE01-LS-4 | −0.022 | −0.023 | −0.094 | +0.140 | 0.051 | 0.124 |
| SE0X-LS-1 | −0.018 | −0.104 | −0.110 | +0.484 | 0.051 | 0.088 |

The gate fires on 2.3 to 2.5 percent of pairs at 6 h, rising to 8.5 to 12.4
percent at 48 h.

## Threshold sensitivity

The four fixed thresholds are nearly indistinguishable. At 24 h the
aggregate skill spans at most 0.005 across 0.5 to 5.0 mm on any probe (for
example SE01-LS-1: −0.077, −0.077, −0.078, −0.074), and at 48 h the same
flatness holds (SE01-LS-1: +0.104, +0.104, +0.103, +0.112). No candidate
threshold separates the losing windows from the winning ones, which is the
central negative finding below.

## The weak-dominance verdict

Weak dominance would require worst-fold skill at or above zero in every
cell. It fails. Worst-fold skill is negative in 15 of 20 cells. It is
exactly 0.000 only where the hybrid degenerates to persistence: the four
6 and 12 h cells on SE01-LS-2 and SE01-LS-3 where the correction never
engages, plus SE01-LS-3 at 48 h, whose worst fold is a fold with nothing to
correct. The answers to the three questions this experiment was built to
settle:

1. **Worst-fold skill at or above zero everywhere: no.** The 24 h worst
   folds are as bad as −2.399, essentially the ungated water balance's
   failure reproduced.
2. **Skill strictly positive wherever the gate fired: no.** At 48 h, yes on
   all five probes (+0.140 to +0.484). At 24 h the fired subset is negative
   on all five probes (−0.094 to −0.267), and at 6 and 12 h it is zero to
   slightly negative.
3. **Event-window win retained: yes, essentially all of it.** Against the
   ungated water balance's event-subset skill, the hybrid retains 87 to 105
   percent at 24 h (for example +0.297 vs +0.283 on SE01-LS-1) and over 99
   percent at 48 h.

## Why the gate cannot rescue 24 h

The hybrid was built on the reading that the 24 h losses come from quiet
hours. The fired-subset numbers sharpen that reading in an uncomfortable
way: the quiet hours that lose are almost exactly the fired hours. The
water-balance correction already carries an internal 0.3 mm forecast-rain
gate, so on genuinely dry forecast windows it always emitted persistence;
the quiet-hour losses of the event study therefore sit on windows where the
forecast promised rain and the soil did not respond as predicted, whether
from drizzle or from a bust in amount or timing. An external rain gate fires on
those same windows, and raising the threshold to 5 mm trims almost nothing,
as the flat sensitivity shows. The 24 h problem is forecast quality on
fired windows, and no precipitation threshold available at the origin can
separate the busts from the hits.

## Caveats

- A single meteorological episode, the April 20 to 22 storm, carries all of
  the event-subset evidence, observed by four correlated probes. The four
  inferred irrigation events predate the holdout, so irrigation response is
  untested.
- The 24 h fired-subset losses are direct evidence of forecast-bust risk:
  when the vintage forecast is wrong about the next day's rain, the hybrid
  inherits the full water-balance error on exactly the pairs it chose to
  trust.
- The ADR-0003 strict gate (positive worst-fold skill on every probe) cannot
  be passed by a model that is identical to persistence on quiet cells, since
  those cells score exactly zero. The strongest claim this family could ever
  make is weak dominance, and this run fails even that in 15 of 20 cells.
- The serving decision belongs to the mentor. On this evidence there is no
  case to change it: persistence remains the served D2 forecaster, and the
  gated hybrid joins the water balance as research with the same open
  question, per-fold robustness to forecast busts, now localized to the
  fired windows at 24 h.
