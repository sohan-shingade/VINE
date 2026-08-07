# GSoC 2026 final work product

**Contributor:** Sohan Shingade (UC San Diego, B.S. Data Science)
**Mentor:** Mohammad Firas Sada (San Diego Supercomputer Center)
**Organization:** National Research Platform
**Project:** VINE Track 2, AI/ML models for Iron Horse Vineyards
**Repository:** <https://github.com/sohan-shingade/VINE>

## What the project set out to do

Build three machine-learning tracks over one shared data pipeline for a working
vineyard in Sebastopol, California, and deploy them as inference services on
NRP Kubernetes: irrigation forecasting (D2), plant-health computer vision (D3),
and harvest timing (D4), on top of a shared pipeline (D1), a common evaluation
harness (D5), a serving layer (D6), and documentation (D7).

## What shipped

| | Deliverable | State |
|---|---|---|
| D1 | Shared data pipeline | Done, verified against live sensors and real imagery |
| D2 | Irrigation forecasting | Done, persistence plus a moisture threshold is served |
| D3 | Plant-health CV | Done in its label-free scope, all 39 blocks screened and ranked |
| D4 | Harvest timing | Descoped to a GDD phenology exploration, no harvest records exist |
| D5 | Evaluation report | Done, walk-forward harness regenerates offline from pinned snapshots |
| D6 | NRP deployment | Image built and smoke-tested, cluster live, pending registry push |
| D7 | Docs and devlog | Done, 13 reports, 12 ADRs, 4 model cards, 9 devlog posts |

By the numbers: 44 commits, roughly 13,000 lines of Python across `src/` and
`tests/`, 348 tests passing, MkDocs building under `--strict`.

## The result that mattered most

For this vineyard's sensor record, **the best 6 to 48 hour soil-moisture
forecast is the last observed value.** Sixteen challenger families were built
and scored against persistence under one walk-forward protocol with a horizon
aware `h - 1` label purge. Fifteen lost outright.

That is a negative result, and it is the honest one. Two challengers initially
appeared to win and both turned out to be evaluation bugs, caught by the D5
harness and fixed with regression tests: a causality leak in the ARIMA rung, and
a pooled metric hiding a single-fold artifact. The harness that caught them is
probably the most reusable thing built here.

The sixteenth family, a filtered historical simulation ensemble, is the only one
to pass the promotion gate in all twenty probe-horizon cells. It improves the
uncertainty band around the forecast and leaves the forecast center, which is the
number a grower acts on, identical to persistence. It is recorded as research
rather than promoted, and it is the starting recipe if a probabilistic product is
ever wanted.

A literature review placed the shipped policy in context: persistence plus a
measured-state threshold is event-triggered control with observation-based
triggering on a slow, directly measured, first-order plant, which is the
structure the control literature derives as near-optimal for this system class.
The best field-validated model predictive controller in the literature beats
soil-moisture-sensor control by roughly 5 percent water at comparable yield, so
the margin available above this baseline is small.

- [Irrigation model card](models/irrigation/persistence.md)
- [Skill ceiling and FHS ensemble](reports/2026-08-05-skill-ceiling.md)
- [Irrigation control policy review](reports/2026-08-05-irrigation-control-review.md)
- [Executed results notebook](notebooks/01-irrigation-results.md)

## The other tracks

**D1** pulls 1.04M sensor rows from InfluxDB onto an hourly grid with gaps
flagged rather than imputed, joins Open-Meteo weather and reference ET, indexes
34 flights of multispectral imagery, and maps 47 sensors to 39 vineyard blocks.
Every snapshot is pinned with DVC.
[Datasheet](data/index.md) · [executed notebook](notebooks/02-pipeline-datasheet.md)

**D3** ships label-free screening: all 39 blocks pass a corrected coverage gate
and are ranked by concern from NDVI and NDRE on the real June orthomosaics. A
pseudo-label CNN reaches 0.806 accuracy against its own weak labels, which
measures agreement with the screen rather than agreement with the field.
Supervised stress detection needs labels that do not exist yet.
[Screening report](reports/2026-08-05-d3-screening.md)

**D4** never unblocked. No harvest dates, yields, or irrigation logs exist in
InfluxDB, the National Data Platform, or any source reachable during the
program. What was built instead is a growing-degree-day phenology exploration
with a useful negative result: transplanted literature véraison bands land
implausibly late here because they accumulate from January 1 while the Winkler
window starts April 1. That is quantitative proof the bands need local
calibration.
[GDD exploration](reports/2026-08-04-d4-gdd-exploration.md)

**D6** serves persistence plus threshold over a typed FastAPI surface that
reports data freshness and suppresses advice on stale snapshots. Cluster access,
namespaces, storage, and seeded data are live.

## What is not finished, and why

- **D6 registry push.** The image is built and smoke-tested; it needs a GitLab
  project to push to.
- **Supervised D3.** Blocked on plant-health labels. A field check of the
  top-ranked blocks would be a usable first label set.
- **Full D4.** Blocked on historical harvest records.
- **Live sensor reads.** The InfluxDB token was rotated on 2026-08-05 and the
  replacement has not been handed off, so reads return 401. Every result here
  reproduces offline from DVC-pinned snapshots and does not depend on it.

## Reproducing the work

Every result is a YAML config plus a seed, logged to MLflow, with data pinned by
DVC. Nothing in the reports or notebooks contacts a network service.

```bash
make setup
uv run dvc pull
make check                      # 348 tests
uv run python scripts/generate_reports.py
uv run python scripts/render_notebooks.py
```

## What I would tell whoever picks this up

The instinct on a forecasting problem is to climb the model ladder. On this
record the ladder was the wrong axis; sixteen rungs bought nothing because soil
moisture at these horizons is close to a random walk and the state is measured
directly. What did buy something was fixing the evaluation, and the two bugs the
harness caught would each have shipped a model that looked better than
persistence and was not.

The open modeling question worth real effort is coverage, not accuracy. Five
probes cover 39 blocks, so 34 blocks receive irrigation decisions with no soil
data behind them. Spatial transfer from instrumented to uninstrumented blocks is
where the next meaningful gain lives.

## Future work

Multi-site generalization, digital-twin integration, an operator feedback loop,
and multi-year climate analysis once a second season of data exists.
