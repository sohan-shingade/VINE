# The decision layer: what finance and control theory taught the irrigation alert

**Date:** 2026-08-05  
**GSoC deliverables:** D2, D7

Week 11 of 13, second session. The forecasting question for D2 is settled:
fifteen challenger families lost to persistence, and the literature review
that closed the ladder found that no published irrigation study even
benchmarks against persistence. This session took the project somewhere the
irrigation-ML literature mostly has not gone, by asking what the alert is
*for* and borrowing the machinery of fields that answer that kind of question
for a living.

## The setup: three borrowed tools

The shipped alert is a threshold rule on soil moisture, and the first-passage
layer already prices "will we cross the threshold within h hours" as a
barrier-crossing probability under a Gaussian random walk. Three imports from
other disciplines take that further.

**From derivatives pricing:** the closed-form crossing probability assumes the
barrier is watched continuously. Our label is scored on hourly readings.
Broadie, Glasserman and Kou showed in 1997 that this mismatch systematically
overprices crossing for discretely monitored barrier options, and it does the
same thing here: at the 6 hour horizon the continuous formula overstates the
hourly-monitored crossing probability by about 37 percent. A backward
survival recursion prices the discrete barrier exactly; a 200k-path Monte
Carlo agrees with it to four decimals.

**From market risk management:** the observed hourly increments are wildly
non-Gaussian (excess kurtosis 324 to 1416; rain and irrigation arrive as
jumps). Raw pooling is the wrong fix, because the unconditional spread runs
about fourteen times the conditional volatility. Filtered historical
simulation, standard in value-at-risk work since Barone-Adesi et al. 1999,
divides each historical move by the volatility current when it occurred and
rescales the surviving shape to today's conditions. That drops the kurtosis
to 26 to 32 and makes the comparison against the Gaussian fair, since both
laws then share the same first two moments.

**From operational meteorology:** Brier score cannot see that an alert firing
on 99 percent of hours is useless. The cost-loss economic value score
(Murphy 1977, Richardson 2000) measures what acting on a rule is worth
relative to the best trivial strategy, across the whole range of
cost-to-loss ratios. This is now policy for D2 alert evaluation, recorded as
[ADR-0010](../adr/0010-economic-value-for-alert-rules.md).

## What came out

The ablation is clean where it matters. Correcting monitoring frequency
helps, correcting the increment shape helps more, and both together win on
Brier and log loss at 6 to 24 hours, in the aggregate and in 16 of 20 probe
by horizon cells. At 48 hours the variants converge, which is honest physics:
two days out, the random-walk approximation itself is the binding error.

The economic-value lens sharpened the story in a way proper scores could not.
The corrected probability rule holds a positive value band at every horizon,
while the incumbent closed form goes sharply negative at moderate cost
ratios. An overpriced crossing probability trips the action threshold too
often, and in operational terms that is systematic over-irrigation, which is
exactly the failure mode a water-savings program cares about.

The optimal-stopping result is my favorite because it explains the whole
summer. Treating irrigation as an American-option exercise problem and
running backward induction gives the moisture level at which irrigating beats
waiting. At the observed conditional volatilities (0.013 to 0.026 units per
hour), that boundary sits only 0.02 to 0.13 units above the stress barrier.
The early-exercise premium a smarter rule could capture is tiny, which is the
quantitative reason fifteen model families could not beat a threshold rule on
this plant: on a slow, low-noise, directly measured state there is almost
nothing above the threshold to win. The premium grows with irrigation
response delay, and extending the recursion with a lead-time term made that
concrete: the first two hours of delay cost as much trigger headroom as the
entire instant-response premium, and at a 24 hour lead time the required
headroom equals the 0.3-unit event depth itself. Same-hour response keeps
the fixed trigger near optimal; day-scale lead times make a delay-blind rule
guaranteed late. The actual lead-time distribution at Iron Horse is now a
question for the mentor.

One methodological note for anyone reproducing this: the shipped absolute
threshold of 25.0 is fine as a safety floor and useless as an evaluation
target on this record, because the season-long drydown makes the labels
nearly constant (holdout base rates 0.61 to 1.00). The evaluation event is a
0.3-unit drawdown instead, which travels with the state and matches what an
allowable-depletion trigger means agronomically.

## Status

All of it is research, none of it is promoted, and persistence plus the
threshold remains what D6 serves; the difference is that this now has a
derivation behind it rather than only an empirical losing streak. Code is
`vine.d2_irrigation.stopping` (pure functions, 26 tests including the Monte
Carlo pin), full write-up in the
[optimal-stopping report](../reports/2026-08-05-optimal-stopping.md), and the
gate is green at 314 tests.

Remaining blockers are unchanged: the GitLab project for the D6 registry
push, and the rotated InfluxDB token handoff for live ingest.
