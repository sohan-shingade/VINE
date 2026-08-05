# The irrigation clock: asking "how long until water?" the way medicine would

*2026-08-05 · D2 · survival analysis, censoring, and a model blend*

Every D2 layer until now answered a fixed-horizon question. What will the
level be at t+h. Will it cross the barrier within h hours. A grower standing
in the row asks the transpose: how many hours until this block needs water?
That is a time-to-event question, and the field that owns it is survival
analysis, the statistics of medical trials. As far as we can tell from the
literature sweep, nobody has scored an irrigation model this way.

## The defect that motivated it

The import was worth it for the censoring machinery alone. The
[stopping layer](2026-08-05-decision-layer.md) scores a decision window only
when all h future readings exist. Sounds harmless, and it deletes every
decision near the June outage and the record end. Worse, whether a window
turns out complete is unknowable at decision time, so the rule quietly
conditions on the future. Survival analysis calls these rows right-censored
and has handled them since the 1950s: keep them in the risk set, reweight the
scored rows by the inverse probability of censoring (Graf et al. 1999), and
estimate that censoring distribution with a reverse Kaplan-Meier. On this
record the repair scores 98 to 139 previously-dropped rows per probe, out of
1409 decisions each. [ADR-0012](../adr/0012-censoring-aware-time-to-event.md)
records the decision.

## Seven curves walk into a walk-forward

Each model outputs a full survival curve S(h) for h = 1 to 48 hours, scored
by the integrated IPCW Brier score (IBS) under the usual purged expanding
walk-forward. The ladder: the training-fold Kaplan-Meier curve (the survival
null), the deterministic drydown calculator (current practice), the
closed-form Brownian first passage (the literature's incumbent), its
discretely-monitored cousin, the filtered historical simulation curve from
the stopping layer, a discrete-time hazard regression, and an equal-weight
blend of the last two.

The hazard regression deserves a sentence. Singer and Willett (1993) showed
that a survival model with hour-level hazards is exactly a logistic
regression on expanded person-period rows, and censored rows just contribute
fewer at-risk hours to the likelihood. It is also the only model in the
ladder that can see the clock on the wall: soil moisture drops on a diurnal
evapotranspiration cycle, so hour of day at the target hour carries timing
information that no random-walk model can represent. A unit test confirms it
recovers synthetic noon-crossing timing at less than half the KM null's IBS.

## What the record said

Full table in the [report](../reports/2026-08-05-survival-clock.md). The
short version: the drydown calculator loses badly everywhere (a step
function pays full price for every miss), the KM null is embarrassingly
strong on the quiet probe (timing lives in seasonality there, and the walk
models cannot see it), the hazard model wins exactly where the walk models
are weakest (best on SE01-LS-3 and SE01-LS-4), and it loses where they are
strong (SE0X-LS-1, where its seasonal coefficients transfer worst). The
errors are complementary, so the blend, with no fitted weight at all, is
best on three probes, second on one, and third by 0.0012 on the last. Brier
convexity guarantees the blend never does worse than the average of its two
members; the record shows it usually beats both.

The blend is also the only model whose aggregate skill against the KM null
is positive on all five probes. It still does not pass the uniform
worst-fold gate (quiet folds make ratio skills explode against a
near-perfect trivial reference, and the final fold has zero events on every
probe, so 35 fold cells are excluded from skill aggregation outright).
Nothing is promoted. Persistence plus a threshold stays served, and the
survival clock joins the stopping layer as research with an honest scorecard.

## What I would tell the mentor

The methodological piece is the durable part: labels that censor instead of
drop, and a proper score that pays for censoring with weights instead of
deletion, now cover every decision hour on the record. Any future timing
model gets this harness for free. The clock reading itself is the
operator-facing win: at the last valid hour the median time to a 0.3
drawdown is beyond 48 hours on every probe, with a 10 percent chance
arriving at 33 to 48 hours depending on probe. That is a statement a person
can irrigate against.
