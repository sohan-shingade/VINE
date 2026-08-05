# D2 report: event-conditioned evaluation (event study)

**Deliverable:** D2 irrigation · **Date:** 2026-08-05 · **Status:** analysis
complete. Persistence stays served; the event split shows where the
water-balance edge lives and where it pays for it.

Aggregate MAE over the roughly 1,350-hour scored holdout is dominated by quiet
drydown hours where persistence is nearly exact. The hours that decide whether
a challenger is useful are the rare ones where the level moves fast: rain
fronts and irrigation jumps, each followed by a drainage transient. This
report scores forecasts separately on those event windows and on quiet hours,
and asks one question: does any challenger beat persistence where the tail
lives?

## Method

1. Rise events per probe come from the existing detector (`detect_rise_events`
   plus `attribute_rain`) with the settled catalog parameters: min_jump 0.5
   sensor units, max_span_h 12 hours, rise_tol 0.0, rain attribution at
   1.0 mm daily precipitation or more. All detected events count here, rain
   and irrigation alike.
2. The event mask lives on target timestamps: a scored (origin, target) pair
   belongs to the event subset when the target time falls inside
   [event start, event end + 24 h]. The trailing 24 h captures the post-jump
   drainage transient, where the level is still moving fast and a pre-jump
   origin is stale. Every other observed holdout hour is the quiet subset.
3. Models: persistence and two challengers, diurnal drift and the
   water-balance model under real archived forecast vintages (same knobs as
   the vintage validation). The purged walk-forward machinery is unchanged
   (5 expanding folds, h-1 training-label purge); per-timestamp predictions
   are retained and split by the mask afterward. Horizons 6, 12, 24, 48 h.
4. Skill is 1 minus the ratio of model MAE to persistence MAE on the same
   subset, so event-subset skill can only be earned on event hours.

Code: `vine.d2_irrigation.event_study`, runner `scripts/d2_event_study.py`,
config `configs/d2_irrigation/event_study.yaml`, full table
`assets/d2_event_study_results.csv`, MLflow experiment `d2_irrigation`, run
`event-study` (id `d1deb61b46aa44b780bc6ecd46200a5e`).

## The dilution number

On the four SE01 probes, event hours are 2.2 to 4.6 percent of the scored
holdout, yet they carry 17.3 to 39.8 percent of persistence's total absolute
error. Persistence's event-hour MAE runs roughly 6 to 28 times its quiet-hour
MAE: at 24 h, 1.77 to 2.69 on event hours against 0.15 to 0.21 on quiet
hours, and at 48 h, 2.60 to 3.13 against 0.29 to 0.42. Aggregate MAE
therefore understates the baseline's weakness exactly where forecasts matter.

Event-subset share of persistence's total absolute error, per probe and
horizon:

| Probe | Event hours | 6 h | 12 h | 24 h | 48 h |
|---|---|---|---|---|---|
| SE01-LS-1 | 60 | 0.268 | 0.286 | 0.272 | 0.222 |
| SE01-LS-2 | 60 | 0.356 | 0.398 | 0.337 | 0.288 |
| SE01-LS-3 | 65 | 0.355 | 0.368 | 0.361 | 0.298 |
| SE01-LS-4 | 31 | 0.374 | 0.391 | 0.297 | 0.173 |
| SE0X-LS-1 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |

SE0X-LS-1 contributes no event evidence: all six of its detected events fall
in the training half of its record, before the holdout begins.

## What the event windows actually are

The scored holdout begins in mid-April 2026, so the event subset reduces to
the rain fronts of April 20 to 22 (one to three overlapping rise events per
probe plus their 24 h tails, 31 to 65 hours per probe). The four inferred
irrigation events in the catalog all occur in March, inside the training
half, so this evaluation tests rain response only. Statistically the event
subset is one meteorological episode observed by four probes, and the
per-probe results below are correlated, never independent replications.

## Event-subset skill vs persistence

Positive means the challenger beats persistence on the event hours
themselves. Cells at exactly 0.000 are hours where the water-balance
correction never fires and the forecast equals persistence.

Water balance (vintage forecasts):

| Probe | n | 6 h | 12 h | 24 h | 48 h |
|---|---|---|---|---|---|
| SE01-LS-1 | 60 | +0.014 | +0.003 | +0.283 | +0.626 |
| SE01-LS-2 | 60 | 0.000 | 0.000 | +0.185 | +0.224 |
| SE01-LS-3 | 65 | 0.000 | 0.000 | +0.030 | +0.238 |
| SE01-LS-4 | 31 | −0.006 | −0.005 | +0.125 | +0.302 |

Diurnal drift:

| Probe | n | 6 h | 12 h | 24 h | 48 h |
|---|---|---|---|---|---|
| SE01-LS-1 | 60 | −0.008 | −0.010 | +0.007 | +0.009 |
| SE01-LS-2 | 60 | +0.054 | +0.030 | −0.010 | −0.019 |
| SE01-LS-3 | 65 | +0.010 | +0.013 | 0.000 | −0.002 |
| SE01-LS-4 | 31 | +0.061 | +0.045 | −0.028 | −0.073 |

## Quiet-subset skill vs persistence

| Probe | Model | 6 h | 12 h | 24 h | 48 h |
|---|---|---|---|---|---|
| SE01-LS-1 | water_balance | −0.010 | −0.018 | −0.216 | −0.044 |
| SE01-LS-2 | water_balance | +0.002 | 0.000 | −0.172 | −0.017 |
| SE01-LS-3 | water_balance | 0.000 | 0.000 | −0.104 | +0.010 |
| SE01-LS-4 | water_balance | −0.007 | −0.014 | −0.108 | 0.000 |
| SE0X-LS-1 | water_balance | −0.001 | −0.022 | −0.028 | +0.133 |
| SE01-LS-1 | diurnal_drift | +0.076 | +0.122 | +0.029 | +0.019 |
| SE01-LS-2 | diurnal_drift | −0.867 | −0.692 | +0.265 | +0.303 |
| SE01-LS-3 | diurnal_drift | −0.086 | −0.067 | +0.064 | +0.089 |
| SE01-LS-4 | diurnal_drift | −1.596 | −1.227 | +0.398 | +0.463 |
| SE0X-LS-1 | diurnal_drift | −4.015 | −3.183 | −0.673 | −0.762 |

## Verdict

Water balance does beat persistence where the tail lives, at the long
horizons: event-subset skill is positive on every probe with event evidence
at 24 h (+0.030 to +0.283) and at 48 h (+0.224 to +0.626). The split also
explains the aggregate signs from the vintage validation. At 24 h the
correction wins the event windows and loses the quiet hours (−0.104 to
−0.216 on the SE01 probes); quiet hours are over 95 percent of the sample,
so the aggregate flips negative. At 48 h the event-hour win is large enough
to carry the aggregate positive despite roughly flat quiet hours. At 6 and
12 h the correction rarely fires and its event skill stays within −0.006 to
+0.014, so nothing is won where the short-horizon tail lives.

Diurnal drift is the mirror image: its aggregate 24 to 48 h wins on
SE01-LS-2 and SE01-LS-4 come entirely from quiet drydown hours (up to
+0.463), while on event hours it stays within −0.073 to +0.061. It offers
nothing where persistence is worst.

The evidence base is thin. Every scored event hour comes from the single
April 20 to 22 storm, SE0X-LS-1 contributes none, and irrigation-driven
events are untested because all four inferred irrigation events predate the
holdout. One storm observed by four correlated probes cannot pass the
ADR-0003 gate, so persistence stays served and this analysis changes no ship
decision. What it does change is the shape of the open water-balance
question: the model already wins the hours that matter at 24 to 48 h, and it
loses aggregate 24 h skill only by degrading quiet hours it should leave
alone. An event-gated variant that applies the correction only when the
forecast shows rain, and otherwise emits persistence exactly, is the concrete
follow-up, and it needs a second wet season of events to validate.
