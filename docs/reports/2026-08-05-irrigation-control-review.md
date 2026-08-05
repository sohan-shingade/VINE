# Irrigation control policy: the existing literature, and where VINE sits in it

**Date:** 2026-08-05 · **Deliverable:** D2 (irrigation), D7 (docs) · **Status:** literature review, no code or model change

## Why this review exists

D2 shipped naive persistence plus a fixed threshold after fifteen challenger
families failed to beat it. That is an uncomfortable result to hand a mentor
without context, because it reads as a null finding: we tried a lot of models
and none worked. This review checks that reading against the control-theory and
agronomy literature, and the answer changes the framing. A threshold policy on a
directly measured, slowly varying state is the structure the control literature
derives as optimal for exactly this class of system, and it is also the
structure that California vineyard practice has converged on independently. Our
result is the expected one, and the interesting part of the work is the layers
sitting on top of the threshold rather than the forecast underneath it.

The review covers four bodies of work: control theory applied to irrigation,
current agronomic and regulatory practice for California wine grapes, the
machine-learning literature on irrigation scheduling, and the institutional
programs and testbeds actually running in the field. Sections 1 to 4 summarize
what exists. Section 5 maps VINE's components onto it. Section 6 states what the
fifteen-challenger campaign adds that is not already in the literature, and
section 7 connects the open questions to the roadmap.

## 1. Control theory applied to irrigation

### 1.1 Model predictive control is the dominant formulation

Nearly every control-theoretic irrigation paper since about 2014 is some form of
MPC: model the root-zone water balance, forecast the disturbances (weather),
optimize an irrigation sequence over a finite horizon, apply the first action,
and re-solve at the next step.

- **Delgoda, Saleem, Malano & Halgamuge (2016)** paired a bucket soil model with
  AquaCrop over a 5-day horizon. The headline is 45.9 to 49.0 percent water
  saved, but that comparison is against a fixed calendar schedule. Against a
  rule-based soil-moisture threshold, the same controller saved only 8.7 to 13.9
  percent. This gap between baselines recurs throughout the literature and is
  the single most important thing to hold onto when reading savings claims.
- **Mao et al. (2018)** controlled zone soil moisture to a band rather than a
  setpoint, which matters because a band is what a deficit-irrigation program
  actually wants.
- **McCarthy, Foley, Raine et al.** built VARIwise and ran the most credible
  field validation in the literature: a multi-season 2023 trial reporting +4.9
  percent cotton yield with 5.6 percent less water, and +8.5 percent ryegrass
  yield with 5.4 percent less water, both measured against soil-water-sensor
  control rather than a calendar. Those single-digit margins are what MPC is
  actually worth when the baseline is a sensor threshold.
- **Sahoo et al. (2021)** used a reduced Richards equation for a physically
  richer soil model.
- **Agyeman et al. (2023)** replaced the expensive soil physics with an LSTM
  surrogate inside a mixed-integer MPC, reporting 6.4 to 22.8 percent water
  reduction with a 2.3 to 4.7 percent yield gain over soil-moisture triggering.

The pattern across all of them: MPC beats calendar scheduling decisively and
beats sensor-threshold scheduling by low single digits to low double digits.

### 1.2 Stochastic and chance-constrained formulations

The deterministic MPC papers treat the weather forecast as truth. The stochastic
branch does not.

- **Shang, Chen, Stroock & You (2020, IEEE Transactions on Control Systems
  Technology)** is the most relevant paper in this branch. They build
  forecast-dependent uncertainty sets, so the controller's caution scales with
  how uncertain the forecast actually is, and report roughly 40 percent water
  reduction while beating both a tuned rule-based policy and certainty-equivalent
  MPC. The important structural claim is that modeling forecast uncertainty
  explicitly beats modeling it implicitly through a safety margin.
- **Guo et al. (2022)** framed the decision against 9-day ensemble rainfall,
  which is the ensemble analogue of the same idea.
- **Svensen et al. (2024)** and **Roy et al. (2021)** extend chance-constrained
  and robust formulations.

### 1.3 Why a threshold policy is the right answer here, not a fallback

This is the part that reframes D2's result, and it comes from the event-triggered
control literature rather than from agriculture.

- **Åström & Bernhardsson (1999, 2002)** proved that for first-order stochastic
  systems, event-based sampling (act when the state crosses a level) outperforms
  periodic sampling (act on a clock) at equal average rate. Soil moisture between
  irrigations is close to a first-order stochastic system, so a
  cross-the-threshold rule is the theoretically favored structure and a
  fixed-interval schedule is the theoretically disfavored one.
- **Lipsa & Martins (2011)** went further and proved that for a noisy first-order
  LTI system, the jointly optimal policy over both when to act and what to do
  *has threshold structure*. The threshold is not an approximation of the optimal
  policy; it is the optimal policy's shape.
- **Soleymani, Baras, Hirche & Johansson (2023)** proved global optimality of
  symmetric threshold triggering paired with a certainty-equivalent controller,
  and showed observation-based triggering dominates model-based triggering. That
  second half matters directly: when you can measure the state, triggering on the
  measurement beats triggering on a model of the state. VINE measures soil
  moisture at five probes.
- **Mania, Tu & Recht (2019)** showed certainty equivalence degrades only
  quadratically in model error, which explains why a crude model plus direct
  measurement stays competitive against a careful model.

Read together, these say that persistence plus a threshold is not the null
result it appears to be. On a slow, directly measured, first-order plant with a
one-directional actuator, it is close to the structure the theory prescribes.
The forecast horizon buys little because the state is measured and the dynamics
are slow.

### 1.4 Feedforward: real value, easily overstated

Adding weather forecast as feedforward is the obvious upgrade, and the evidence
is mixed in an informative way.

- **Cai, Hejazi & Wang (2011)** report 11 to 26.9 percent water saved from
  forecast-informed scheduling, but the baseline assumes zero future rain, which
  inflates the margin.
- **Bergez & Garcia (2010)** are the skeptical counterweight and find much less
  value.
- **Anupoju et al. (2021)** found a 5-day horizon optimal and, importantly, found
  value non-monotonic in horizon length. Longer forecasts are not uniformly
  better.
- **NOAA precipitation verification** puts a number on why: the Threat Score for
  precipitation is roughly 0.37 at 24 h and drops to 0.28 at 48 h, and spatial
  displacement converts forecasts that were meteorologically correct into scored
  misses at a point location.
- **Frontiers in Agronomy (2025)** reports that cumulative multi-day rainfall
  totals are substantially more skillful than daily timing.

That last point is directly testable against our own gated-hybrid result and is
taken up in section 7.

### 1.5 First-passage: the unoccupied niche

First-passage time (the probability that a stochastic process crosses a level
within a window) appears in the soil-moisture literature only in the
*uncontrolled* case, as ecohydrology.

- **Rodríguez-Iturbe et al. (1999)** and **Porporato et al. (2001)** derived
  crossing rates below critical soil-moisture thresholds for natural vegetation.
- **Laio et al. (2001)** and **Tamea et al. (2011)** extend the stochastic
  soil-moisture framework.
- **Dralle & Thompson (2016)** give closed-form mean first-passage times for
  dry-season soil moisture.

No irrigation controller in the reviewed literature uses a finite-horizon
crossing probability as its constraint. Controllers use setpoints, bands, or
expected-value costs. This is the clearest open niche the review found, and it is
what VINE's first-passage layer computes.

### 1.6 Vineyard-specific control

- **Gips, Gutman, Linker & Netzer (2020, IFAC)** is the closest paper to a
  vineyard MPC: two-level MPC of stem water potential using STICS on Syrah, with
  twice-weekly actuation and a 7-day tactical horizon. It is simulation only,
  with no field validation.
- **Kang et al. (2023)** built a precision-RDI decision support system.
- **Romero et al. (2010, 2013)** established pre- and post-veraison stem
  water-potential threshold bands.
- **Acevedo-Opazo et al. (2010)** worked on spatial water-status modeling.
- **Suter et al. (2019)** found stem water potential confounded by same-day VPD,
  and identified pressure-chamber sensing as the practical bottleneck.

The vineyard control literature is thin, simulation-heavy, and bottlenecked on
plant-water-status sensing rather than on control algorithms.

## 2. What growers and regulators actually do

The control literature and the practice literature barely cite each other, and
practice is where the operative policies live.

### 2.1 The ET ledger (FAO-56)

**Allen, Pereira, Raes & Smith (FAO, 1998), Irrigation & Drainage Paper 56** is
the global standard. Irrigation demand is reference evapotranspiration ET₀
(Penman-Monteith on a standardized grass surface) times a crop coefficient Kc,
tracked against a root-zone depletion ledger. Chapter 8 defines total available
water (TAW), readily available water (RAW), depletion Dr, and a stress
coefficient Ks that equals 1 while Dr stays under RAW and then declines linearly
to zero at TAW. That is the mathematical form of what growers call maximum
allowable depletion.

FAO-56 gives wine grapes a rooting depth of 1.0 to 2.0 m, a depletion fraction
p = 0.45, and Kc of 0.30 initial, 0.70 mid-season, 0.45 late. One subtlety
matters: the wine-grape Kc_mid of 0.70 already embeds an implicit stress
coefficient of roughly 0.7, so it is a pre-deficited number. Using it as a
full-ET baseline and then applying a 50 percent deficit on top double-counts.

Almost nobody runs dual-Kc FAO-56 daily. The practiced form is the checkbook
method: weekly deposit-and-withdrawal accounting where ET is the withdrawal and
rain plus irrigation are the deposits, irrigating when cumulative depletion
reaches the allowable limit. Extension guidance from NDSU, Minnesota, Colorado
State, Oregon State, and Clemson all describe this same ledger. The conventional
allowable depletion is 50 percent for deep-rooted perennials, and WSU lists 50
percent specifically for grapes.

### 2.2 Soil-moisture threshold scheduling

Define field capacity and permanent wilting point for the soil, compute available
water over the effective root depth, pick a depletion band, irrigate when the
measured value crosses the lower bound.

**Prichard, Hanson, Schwankl, Verdegaal & Smith (UCCE, 2004)** is the definitive
California vineyard soil-water manual. It puts field capacity at 10 cb tension in
sand and 33 cb in other soils, wilting point at 1500 cb, and states the
physiological basis for the 50 percent convention directly: water deficits do not
begin until the vine has extracted about half the available soil water in the
root zone. **Peters (WSU, 2022)** gives the practical vineyard translation:
roughly 30 to 50 cb for minimal stress and 80 to 100+ cb for imposed stress.

The limitation named repeatedly across these sources is that a probe reports a
point, not a block, and calibration is site-specific. That is why California
vineyards lean on plant-based measurement instead.

### 2.3 Regulated deficit irrigation: the operative California policy

For wine grapes the goal is not to keep the vine well watered. Controlled stress
during specific phenological windows improves fruit quality, so the policy
deliberately runs the vine below the comfort threshold.

**Prichard, Smith & Verdegaal (UCCE)** give the reference two-parameter protocol.
A midday leaf water potential threshold decides *when* to start irrigating: −10
to −13 bars for whites, −13 to −15 bars for reds. Once triggered, apply a fixed
fraction of full potential ET: 50 to 60 percent is the successful range, and 35
to 40 percent produced delayed harvest and poor fruit quality. After harvest the
fraction resets to 100 percent to support the root flush and carbohydrate
reserves.

Full potential ET comes from canopy size, not from a generic table:
Kc = 1.7 × fractional midday shaded area (**Williams, 2002**, weighing lysimeter
at Kearney). The ledger then debits a soil contribution (about 2.5 in on deep
medium-textured soil, as little as 1 in on shallow soil) and effective rainfall
computed as (rainfall − 0.25 in) × 0.8.

The policy is staged by phenology:

| Stage | Policy |
|---|---|
| Budbreak to fruit set | No deficit. Stage I deficits cut berry cell number and cost yield outright. |
| Fruit set to veraison | The RDI sweet spot, especially the three weeks before veraison. Moderate deficit restrains shoot growth while photosynthesis continues. |
| Veraison to harvest | More severe deficit opens the fruit zone, but must be moderated. Too much water restarts lateral growth; too little causes defoliation and sunburn. Recent work supports easing the deficit in the final weeks. |
| Post-harvest | Return to 100 percent. |

The quality-versus-yield numbers are concrete. Whites maximize yield near 60 to
70 percent of full seasonal ET. Reds lose 3 to 19 percent yield at the same
deficit, and a four-season Lodi Cabernet trial averaged −19 percent while a Galt
Syrah trial averaged −30 percent. Berry weight is still 97 percent of maximum at
0.75 of full potential water use, so the first quarter of the cut is nearly free.
Yield loss is also lagged: cumulative loss of fruitfulness shows up in years 2 to
5, which no scheduler models.

**Williams (UC Davis, 2019)** adds the calibration detail that matters most for
anyone building a threshold: non-stressed midday stem water potential is a
function of VPD at the time of measurement. Williams & Baeza (2007) predict −0.37
MPa at 2 kPa VPD against −0.57 MPa at 5 kPa. A fixed threshold is physically
wrong without VPD normalization, and no commercial system corrects for it. His
degree-day Kc curves also show max seasonal Kc spanning roughly 0.52 to 0.93
purely from trellis geometry and row spacing, which makes generic Kc values a
large error source for any specific block.

**UC ANR (2024)** gives the operational lookup, and the stem-versus-leaf offset of
about 2 bars is a live source of silent error because published thresholds are
mostly leaf while modern sensors report stem:

| Stem WP (neg. bars) | Leaf WP (neg. bars) | Vine status |
|---|---|---|
| −8.0 to 0 | −10.0 to 0 | Not water stressed |
| −12.0 to −8.1 | −14.0 to −10.1 | Some water stress |
| −16.0 to −12.1 | −18.0 to −14.1 | Extremely water stressed |

### 2.4 Public tools and regulation

- **CIMIS** (CA DWR) is the public ET₀ utility that makes the ledger method
  possible: over 150 automated stations, a 2 km Spatial CIMIS product fusing
  station data with GOES, and a REST API. Data arrives on a 1-day lag, which is
  why the Prichard method schedules on historical ET₀ prospectively and corrects
  retroactively.
- **OpenET** provides satellite-derived *actual* ET at roughly 30 m field scale,
  validated in Nature Water (2023). E. & J. Gallo uses it at commercial vineyard
  scale. It is retrospective, so it audits and validates rather than schedules.
- **USDA NRCS Conservation Practice Standard 449** is the federal definition and
  is deliberately method-agnostic: a written plan must specify when to irrigate
  and how much, using crop ET, soil-moisture monitoring, computerized scheduling,
  or plant monitoring.
- **SGMA** is the regulatory pressure that has turned irrigation efficiency from a
  cost question into a compliance question. There is no statewide pumping limit;
  allocations are set per groundwater sustainability agency. Concrete 2026
  examples include South Fork Kings at 0.86 AF/acre with a $500/AF overdraft
  penalty, and a UC ANR estimate of a 16 percent average pumping cutback needed
  across the San Joaquin Valley.
- **SWEEP** (CDFA) funds the hardware, explicitly including soil-moisture sensors,
  plant sensors, weather stations, and telemetry for vineyards, up to $200,000 per
  project. It is mid-transition to regional block grants, with producer
  applications projected to reopen in or after January 2027.
- **Certification** is where scheduling policy is actually mandated for a wine-grape
  grower. LODI RULES 4th Edition, SIP Certified, and Certified California
  Sustainable Winegrowing all require a documented water-management plan,
  distribution-uniformity testing, and soil or plant water-status monitoring.
  None of them prescribes a method or a threshold.

### 2.5 Commercial systems, and what they leave to the human

Adoption is partial. A 2021 Paso Robles survey of 91 vineyard managers found ET
monitoring at 43 percent, soil-moisture sensors at 41 percent, and plant-based
monitoring at 32 percent. Lambert et al. (2023) found over half of 155
Sacramento and San Joaquin growers used none of the formal methods.

| System | Sensing | Policy underneath |
|---|---|---|
| CropX (acquired Tule) | Surface-renewal actual ET, soil probes, canopy video for leaf WP | ET ledger with a plant-stress feedback loop; reports a measured Ks |
| Sentek | Multi-depth capacitance profile probes | Pure threshold and refill band |
| Semios | Soil probes, ET, dendrometers | Hybrid threshold plus ledger |
| FloraPulse | Microtensiometer in woody tissue | Continuous stem water potential threshold |
| Fruition Sciences | Sap flow | Transpiration-deficit ratio |
| Lumo | Smart valves | Actuation only, no policy |

Every commercial platform implements one of two control laws: a soil-moisture
threshold with a refill band, or an ET ledger with a stress-ratio setpoint. The
plant-based systems supply a better measurement of the state variable without
changing the control law. **None of them chooses the setpoint.** That decision is
negotiated between the viticulturist and the winemaker and entered by hand.


## 3. The machine-learning literature on irrigation scheduling

This is the section most directly relevant to whether the fifteen-challenger
result is a local disappointment or a reproduction of what the field already
knows. It is the latter.

### 3.1 Almost nobody compares against persistence

The single most important finding of this survey: in precision viticulture,
**no published study benchmarks a soil-moisture or plant-water model against a
persistence baseline.** Across the vineyard decision-support literature, one
paper (Stojanova et al. 2025, Sensors 25:3658) reports an explicit naive
baseline at all, and that baseline is linear regression rather than
last-observation-carried-forward.

Outside viticulture the picture is only slightly better, and where a real
persistence baseline does appear it behaves the way ours does. Deforce et al.
(2024) forecast soil water potential five days ahead against a true
last-observation baseline: the LSTM improved MAE by roughly half a percent and
was about 4.7 percent worse on RMSE. That is the closest published analogue to
our setup, and it reaches the same conclusion at a longer horizon than any we
tested.

This matters for how we report the fifteen challengers. The absence of a
comparator is total on the vineyard side, so we cannot say our persistence floor
is unusually high or unusually low relative to published work. What we can say
is that the studies reporting strong accuracy on this variable have not
established that they beat doing nothing.

### 3.2 High R-squared on soil moisture is close to free

Section 4.4 covers the Kang et al. weekly figure. The general mechanism is worth
stating once here: soil moisture at sub-daily to weekly horizons has an
autocorrelation high enough that a persistence forecast already explains most of
the variance, so R² and raw MAE reward a model for reproducing the input. Skill
relative to persistence is the only score that isolates what the model added.
Our ADR-0003 gate, which requires positive worst-fold skill in every
probe-horizon cell, is stricter than anything we found in the literature.

An additional caution applies to model validation that never becomes
recommendation validation. Kang et al. validated the network on held-out 2021
data, and the irrigation schedules it implies were never run against a control
block. King and Shellie (2023) logged four seasons of genuine operational use,
with validation that is correlational (significant association among crop water
stress index, leaf water potential, and available soil water) and no yield or
water controls. A validated predictor is a weaker claim than a validated policy.

### 3.3 Reinforcement learning has not left the simulator

Every RL irrigation result we found lives inside a crop-model simulator
(aquacrop-gym, WOFOSTGym, Alkaff et al. 2025). The WOFOSTGym authors state
plainly that field transfer is unvalidated. Since the simulator is itself a
calibrated water-balance model, an RL policy trained in it is learning the
model's dynamics rather than the field's, and the gap between those is exactly
the gap that made our own water-balance correction fail on real forecast
vintages.

### 3.4 Geospatial foundation models add nothing to this problem

Kontogiorgakis et al. (2026) regressed 10 m soil moisture over vegetated Europe
with spatial cross-validation at 113 ISMN stations. Prithvi embeddings scored
R² = 0.515 against 0.514 for handcrafted spectral features, and handcrafted
features with a 10-day ERA5 lookback reached 0.518. On the only regression task
in the PANGAEA benchmark, a from-scratch U-Net beat every foundation model
(Marsocci et al. 2025). Shang et al. (2026) found Prithvi, SpectralGPT, and
SatMAE all degrade sharply under regional shift on agricultural tasks.

For a project with one instrumented site and five probes, this closes off what
would otherwise look like an attractive direction.

### 3.5 The replication record in agricultural ML

The broader reliability picture is poor enough to justify our evaluation
discipline rather than treat it as excessive.

- Mohanty et al. (2016) reported 99.35 percent held-out accuracy on PlantVillage
  and 31.4 percent on images collected under different conditions, by the
  authors' own measurement.
- Noyan (2022) showed a classifier using only 8 background pixels of
  PlantVillage reaches 49.0 percent accuracy against 2.6 percent chance, so the
  field's most-used agricultural benchmark leaks class signal through image
  backgrounds.
- Ploton et al. (2020, Nature Communications 11:4540) found a forest-biomass
  model that random cross-validation credited with explaining over half the
  variance dropped to near-null skill under spatial validation.
- Kapoor and Narayanan (2023, Patterns 4(9):100804) documented leakage across at
  least 294 papers in 17 fields; correcting it erased complex ML's advantage over
  logistic regression in one well-known application.
- Corley et al. (2023) showed that resizing and normalization choices alone move
  benchmark results by up to 32 points, which exceeds most claimed architectural
  gains.

Two of our own results belong to this genre. The Kalman-filter causality leak
and the single-fold aggregation artifact each produced an apparent win that
dissolved under correction, and both are now guarded by regression tests. The
literature suggests those two were not unlucky.

### 3.6 What does work is a calibrated water balance plus in-situ sensors

The positive results at the 2025 to 2026 frontier are not deep learning.
Kisekka, Nicolas and Linker (Irrigation Science 43:1471, 2025) ran a Davis, CA
field trial where DSSAT simulation-optimization cut applied water 26 percent
with no yield or quality loss, and leaf-area-index data assimilation added
nothing over the calibrated model alone. Millán et al. (Agronomy 15(9):2132,
2025) ran a soil-moisture-plus-crop-model digital twin on a 15 ha commercial
tomato farm. Kivi et al. (HESS 27:1173, 2023) found in-situ soil-moisture
assimilation into APSIM cuts RMSE 17 to 28 percent while satellite data
constrains far more weakly.

The pattern is consistent: the value sits in a well-calibrated process model fed
by ground sensors, and the learned layer on top has repeatedly failed to add to
it. That is the shape of our own D2 result.

### 3.7 Verification status of this section

Figures verified by direct fetch: Kontogiorgakis et al., Marsocci et al., Shang
et al. Figures taken from abstracts or search summaries and not verified against
the full text: the Deforce et al. decimals, the Laroche-Pinel et al. (2024)
block-out and date-out R² values, and the Kang et al. weekly R². Publisher
paywalls returned 403 for each. None of the arguments above turn on a decimal
place, but anyone citing these numbers downstream should pull the PDFs first.

## 4. Programs and testbeds actually running in the field

Papers are one thing and deployments are another. Surveying institutional
programs from 2018 to 2026 gives a sharper picture of what has reached a working
vineyard, and the picture is humbling.

### 4.1 What is genuinely deployed at commercial scale

- **Satellite ET.** The GRAPEX campaign (USDA-ARS with E. & J. Gallo and UC
  Davis, Kustas et al. 2022 in Irrigation Science) underpins Gallo's ET Toolkit,
  which drives weekly irrigation decisions across more than 100,000 California
  vineyard acres. This is the only vineyard irrigation decision support operating
  at real commercial scale.
- **CropManage** (UC ANR with NASA Ames) reaches roughly 40,000 acres, but
  overwhelmingly cool-season vegetables. Its vineyard module is a research
  adaptation validated against eddy covariance and OpenET at a handful of coastal
  sites (Cahn et al. 2025, six seasons), with no published vineyard user count.
- **WSU Irrigation Scheduler Mobile** is a real soil-water-balance tool fed by
  AgWeatherNet, though it is multi-crop rather than vineyard-specific.
- **Vintel** (SAS ITK with INRAE) estimates predawn leaf water potential and has
  about 350 users in Occitanie.
- **Athena IR-Tech** (spun out of Vinay Pagay's Adelaide program) sells proximal
  infrared canopy sensing to roughly 40 customers in Australia and New Zealand,
  with 15 of 17 subsidized trial growers converting to paying customers.

### 4.2 Strong agronomy, no shipped software

Several programs produce well-validated prescriptions and no decision-support
system at all. UC Davis Oakville (Torres, Kurtural et al. 2021, Frontiers in
Plant Science) established that 50 percent ETc maintains yield and flavonoid
composition in Cabernet Sauvignon. OSU's Levin established post-veraison deficit
targets for warm-climate Pinot noir. Adelaide's Wine Australia project UA
1803-1.3 reported 3 to 6 times higher water use efficiency in Cabernet
Sauvignon. These tell a grower what to prescribe, and nobody has shipped the
prescriber.

### 4.3 Sensor-network and ML vineyard DSS is pilot-stage everywhere

The survey found no exceptions to this worldwide. WSU's Kang et al. (2023) ran
on one Riesling block. Kisekka's soil-moisture ML ran on one vineyard.
Brillante's variable-rate work (AVF 2023-2718) covered 48 zones over two
seasons. Tardaguila's thermal imaging is a research platform. The Portuguese
UTAD and ADVID deployments cover one or two quintas. The EU projects VITIGEOSS,
VISCA, and MED-GOLD all ended without published performance numbers or confirmed
commercial continuation.

**Iron Horse and the NRP program sit squarely in this category.** The CENIC and
NRP precision-agriculture work at Iron Horse is a real sensor deployment with
real network and compute behind it, and as of August 2026 it has no published ML
result, no validated irrigation recommendation, and no peer-reviewed output. The
digital twin is described as being developed rather than existing. VINE is the
first attempt to put a validated model result behind that program, which raises
the value of getting the evaluation right and lowers the value of claiming a win
we cannot defend.

One correction this implies for our own documentation: the "~10 percent water
reduction" figure that appears on the VINE home page traces to CENIC and NRP
program material, where it is stated as a potential with no baseline, design, or
sample size given. It should be attributed as a program target rather than a
measured result, and it has been corrected accordingly.

### 4.4 The R-squared trap, and why our metric choice matters

The most useful methodological finding in this survey is a comparison between two
published accuracy numbers.

| Study | Target variable | Reported accuracy |
|---|---|---|
| Kang et al. (2023), WSU | Weekly soil moisture, 1 week ahead | R² = 0.9325 |
| Laroche-Pinel, Brillante et al. (2024) | Stem water potential | R² = 0.54, 74 percent stress classification |

A weekly soil-moisture R² of 0.93 at a single instrumented block is close to what
autocorrelation alone delivers. Soil moisture is a slow, strongly persistent
variable, so a model that predicts next week roughly equals this week will score
extremely well on R² while adding no decision value. That is precisely the
failure mode our skill-vs-persistence metric exists to catch, and it is why our
fifteen challengers report skill rather than R² or raw MAE. The honest 0.54 on
stem water potential is the more informative number, because stem water potential
is the variable that is genuinely hard to predict and is the one the operative
irrigation policy actually triggers on.

A caveat on that table: the Kang et al. figures were extracted from secondary
sources because the publisher pages returned 403 during this review, so treat
the exact value as indicative and verify against the DOI before citing it
elsewhere. The qualitative point does not depend on the third decimal place.

The survey also flags that essentially every water-savings percentage in the
commercial and program layer is unbacked by a controlled comparison, including
the 20 to 25 percent attributed to the Gallo toolkit, Vintel's 15 percent and 30
to 40 percent figures, and the 10 percent attributed to the Iron Horse program.
Where a controlled comparison against sensor-threshold scheduling does exist, the
margin is the low single digits discussed in section 1.

## 5. Where VINE sits in this landscape

Mapping the D2 stack onto the vocabulary above, component by component.

| VINE component | Control-theory name | Practice analogue | Status |
|---|---|---|---|
| Five soil probes at hourly cadence | Direct state measurement | Sentek-style capacitance profile monitoring | Shipped (D1) |
| Persistence forecast | Certainty-equivalent state estimate on a slow first-order plant | The implicit assumption in any probe-triggered rule | Shipped (D2) |
| Fixed 25.0 threshold alert | Event-triggered (Lebesgue) switching, bang-bang with hysteresis | Maximum allowable depletion trigger | Shipped, precision/recall 0.95 to 0.99 |
| Water balance with archived forecast vintages | Feedforward disturbance compensation | The FAO-56 checkbook ledger | Research |
| Rain-gated hybrid | Gated feedforward, switching on predicted disturbance magnitude | No practice analogue; growers gate by eye | Research |
| First-passage crossing probabilities | Chance constraint on a finite-horizon level crossing | No analogue in either literature | Research |
| CRPS wrapper with adaptive spread | Uncertainty quantification for a stochastic controller | No analogue in commercial systems | Research |

Three observations follow from that table.

**The shipped stack is the theoretically supported one.** Persistence plus a
measured-state threshold is event-triggered control with observation-based
triggering on a directly measured first-order system. Åström & Bernhardsson,
Lipsa & Martins, and Soleymani et al. between them establish that this structure
is optimal or near-optimal for this system class, and that triggering on the
measurement beats triggering on a model. We arrived at it by elimination; the
theory says it was the destination.

**Our water balance is the FAO-56 checkbook method.** It was built as a physical
challenger without reference to the agronomy literature, and it reproduces the
structure of the reference method that California extension has recommended for
decades: debit ET, credit effective rainfall, track depletion. That it fails to
beat persistence at 24 h on real forecast vintages is a statement about forecast
quality at that horizon, not about the ledger.

**The layers with no practice analogue are where the contribution is.** No
commercial vineyard system reports a crossing probability or a calibrated
predictive distribution. Every one of them reports a level and a threshold.

Equally important is what VINE does **not** have, measured against what the
practice literature says the policy requires:

- **No plant water status.** The operative California RDI policy triggers on
  midday leaf or stem water potential, not on soil moisture. We have no pressure
  chamber readings, no microtensiometer, and no sap flow. Soil moisture is the
  sanity-check layer in the practice stack, not the trigger layer.
- **No phenology staging.** The real policy changes setpoint at budbreak, fruit
  set, veraison, and harvest. Our threshold is one constant for the whole season.
- **No canopy-derived Kc.** Williams' work puts the max seasonal Kc spread from
  trellis geometry alone at roughly 0.52 to 0.93. Our water balance uses a
  generic coefficient.
- **No VPD normalization**, which the literature says makes any fixed
  water-potential threshold physically wrong. This applies to our soil threshold
  only indirectly, but it applies squarely to any plant-based extension.
- **Sparse spatial coverage.** Five probes against 39 blocks. Variable-rate
  irrigation in vineyards is still at the research-trial stage even with far
  denser instrumentation.
- **No setpoint selection.** Like every commercial system reviewed, VINE serves a
  threshold it was given. The 25.0 value is an experimental rule that still needs
  operator calibration by block and sensor depth.

## 6. What the fifteen-challenger campaign adds

The literature already contains the claim that soil moisture is hard to forecast
better than persistence at short horizons. What it mostly does not contain is
per-cell evidence under a stated promotion gate. Five things here are worth
publishing.

**A negative result with an auditable protocol.** Fifteen model families across
five probes and four horizons, all under expanding walk-forward validation with
an h−1 training-label purge, scored against a pre-registered gate (worst-fold
skill above zero in every probe-horizon cell). Two apparent wins were traced to
evaluation bugs, a Kalman-filter causality leak and a single-fold aggregation
artifact, and both now have regression tests. Most published irrigation-ML work
reports aggregate metrics on a single split. The gap between our aggregate
results and our worst-fold results is large enough that the distinction is the
finding.

**The baseline-choice problem, quantified on our own data.** Delgoda et al. saved
45.9 to 49.0 percent against a calendar and 8.7 to 13.9 percent against a
threshold rule. That is the same phenomenon we hit repeatedly: a challenger looks
strong until the comparison is against a properly tuned naive policy. Our fifteen
rejections are fifteen instances of the second number.

**Event-conditioned error accounting.** Scoring only the hours inside a detected
rise event plus a trailing 24 h, those hours are 2.2 to 4.6 percent of the SE01
holdout yet carry 17.3 to 39.8 percent of persistence's total absolute error. On
those hours the water balance beats persistence at 24 h (+0.030 to +0.283) and at
48 h (+0.224 to +0.626). The literature does not report this decomposition, and
it changes what an aggregate MAE comparison means: a model can win on aggregate
by improving quiet hours it was never needed for. That is exactly what the
diurnal-drift challenger turned out to be doing.

**First-passage probabilities as an irrigation signal.** The ecohydrology
literature computes crossing statistics for uncontrolled soil moisture, and the
control literature uses expected-value or setpoint constraints. Framing the
irrigation decision as "probability of crossing 25.0 within 48 h" sits in the gap
between them, and it beat persistence on Brier score at 12, 24, and 48 h.

**The metric ladder.** Point MAE was unbeatable across all fifteen families. Once
the scoring rule changed to CRPS, a Gaussian centered on the same persistence
value with a causal EWMA spread beat the persistence point mass in all 20
probe-horizon cells (+0.094 to +0.266), with 90 percent intervals covering 87 to
96 percent of actuals. The forecast center did not improve; the honest
uncertainty around it was worth something. That distinction is the practical
answer to whether ML helps here: it does not help you guess the number, and it
does help you say how sure you are. Given that stochastic MPC (Shang et al.) is
the branch of the control literature reporting the strongest results, and that it
runs on exactly this kind of calibrated uncertainty, the CRPS layer is the piece
of D2 with the clearest path into a real controller.

Two honest caveats on all of the above. Every scored event hour comes from a
single April 20 to 22 storm, so the event-study numbers rest on one weather
event. And the rain-gated hybrid's 48 h aggregate wins (+0.051 to +0.122 on all
five probes) sit alongside negative worst folds, so weak dominance still fails.

## 7. What this means for the roadmap

The review turns a vague "future work" list into a ranked one, separated by what
actually blocks each item.

### 7.1 Testable now, on data already pinned

**The cumulative-total versus daily-timing hypothesis.** The gated hybrid wins at
48 h and loses at 24 h, and the threshold sweep is flat, which says the losses
sit on forecast-rain windows rather than on quiet hours. The Frontiers in
Agronomy (2025) finding that cumulative multi-day rainfall totals are more
skillful than daily timing offers a specific explanation: the forecast may have
the total roughly right while placing it in the wrong hour, which a 24 h window
scores as a bust and a 48 h window absorbs. This is checkable against the
archived forecast vintages already in DVC by scoring forecast rain totals against
realized totals at both windows and correlating the error with our per-window
skill. It is the single highest-value open experiment in D2 because it would
either explain the 24 h failure or rule out the explanation.

**Threshold calibration against the agronomic conventions.** The 25.0 value is
currently an experimental constant. The practice literature says it should be
derived from field capacity, wilting point, and an allowable-depletion fraction
(0.45 per FAO-56 for wine grapes, 50 percent by extension convention). Comparing
our observed soil_water range of roughly 18 to 45 against a texture-derived
available-water calculation would show whether 25.0 sits near the conventional
depletion point or somewhere arbitrary. This needs soil texture per probe, which
is a question for the mentor rather than a data pull.

### 7.2 Blocked on the new InfluxDB token

The token was rotated on the mentor side and every sensor read now returns 401.
Three items wait on it, and all three are the same request:

- **Second wet season validation.** Every scored event hour in the event study
  comes from one April storm. The 48 h gated-hybrid result and the event-error
  decomposition both need a second wet season before they mean anything general.
- **Extended event catalog.** More detected rise events would let the event study
  report per-event rather than pooled behavior.
- **Arrival-time (hazard) modeling of irrigation events.** Currently unstarted.

### 7.3 Needs agronomy input from the mentor, not code

This review makes the mentor questions sharper than "confirm the threshold":

- **Is Iron Horse running a deficit program, and at what stage targets?** The
  entire California policy is phenology-staged, and a single season-long
  threshold is inconsistent with how a wine-grape block is actually managed. If
  there is an RDI percentage and a stress target, the alert layer should be
  staged to match.
- **Is any plant-water-status measurement being taken?** Pressure-chamber
  readings, even weekly and by hand, would connect our soil-moisture layer to the
  variable the operative policy actually triggers on. This is the largest single
  gap between VINE and the practice stack, and the literature is explicit that
  plant-based sensing is the real bottleneck.
- **Soil texture and effective rooting depth per probe**, which the threshold
  calibration above needs.
- **Which blocks the five probes are meant to represent.** Five probes against 39
  blocks is a spatial-inference problem the current stack does not address, and
  variable-rate irrigation research suggests it is not a small one.

### 7.4 Documented future directions, with evidence attached

These belong in the handoff notes rather than in the remaining two weeks.

- **Stochastic MPC on the CRPS layer.** The strongest results in the control
  literature come from chance-constrained MPC built on calibrated forecast
  uncertainty (Shang et al. 2020). D2 already produces calibrated predictive
  distributions. That is the input such a controller needs, and it is the most
  natural continuation of this work.
- **First-passage as the chance constraint.** No reviewed irrigation controller
  uses a finite-horizon crossing probability as its constraint. Our first-passage
  layer computes one. Publishing that framing is a small contribution the
  literature does not currently have.
- **Expect small margins.** The best field-validated MPC result against
  sensor-threshold control is roughly 5 percent water with a comparable yield
  gain. Any future controller built on this stack should be evaluated against
  that expectation rather than against the 40 percent numbers that come from
  calendar baselines.
- **Constrained seasonal allocation is the unsolved problem.** Under a SGMA
  allocation, the grower's question inverts from "how much does the vine need" to
  "how do I spend a fixed annual budget across phenology stages and blocks." No
  public or commercial tool solves this. It is well outside GSoC scope and is the
  most valuable thing on this list.

- **Multi-site generalization is a data-standardization problem first.**
  Federated learning is the technique usually reached for here, and the evidence
  says it is not ready. Two systematic reviews (Žalik & Žalik 2023, n=11;
  Shawon et al. 2026, PRISMA over 90 studies) find essentially all work runs on
  simulated clients with curated datasets, and neither identifies a real
  multi-farm deployment. The canonical paper splits PlantVillage randomly and
  equally across simulated clients, which makes them IID and erases the
  heterogeneity federation exists to handle. The practical move for VINE is to
  standardize sensor schemas, placement, and calibration now, since that is what
  actually blocks generalization. If a future project controls all its sites,
  centralizing the data remains simpler and better.

The existing post-GSoC roadmap entries (multi-site generalization, digital-twin
integration, operator feedback loop, multi-year climate analysis) all survive
this review unchanged. What the review adds is a reason to rank the operator
feedback loop higher: every commercial system reviewed leaves setpoint selection
to the human, so the feedback loop is not a convenience feature. It is where the
policy actually gets decided.

## Sources

### Control theory

Åström & Bernhardsson (1999, 2002), comparison of Riemann and Lebesgue sampling ·
Lipsa & Martins (2011), remote state estimation with communication costs ·
Soleymani, Baras, Hirche & Johansson (2023), optimality of symmetric
event-triggered control · Mania, Tu & Recht (2019), certainty equivalence is
efficient for LQR · Delgoda, Saleem, Malano & Halgamuge (2016), irrigation
control through MPC · Mao et al. (2018), zone-level MPC · McCarthy, Foley &
Raine, VARIwise and the multi-season field trial (2023) · Sahoo et al. (2021),
reduced Richards-equation MPC · Agyeman et al. (2023), LSTM-surrogate
mixed-integer MPC · Shang, Chen, Stroock & You (2020), IEEE TCST,
data-driven robust MPC for irrigation · Guo et al. (2022), ensemble-rainfall
scheduling · Svensen et al. (2024) · Roy et al. (2021) · Cai, Hejazi & Wang
(2011), forecast-informed scheduling · Bergez & Garcia (2010) · Anupoju et al.
(2021), forecast horizon value · Rodríguez-Iturbe et al. (1999) and Porporato et
al. (2001), stochastic soil-moisture crossing statistics · Laio et al. (2001) ·
Tamea et al. (2011) · Dralle & Thompson (2016), closed-form mean first-passage
time · Gips, Gutman, Linker & Netzer (2020, IFAC), two-level vineyard MPC ·
Kang et al. (2023), precision-RDI decision support · Romero et al. (2010, 2013),
stem water-potential threshold bands · Acevedo-Opazo et al. (2010) · Suter et al.
(2019), VPD confounding of stem water potential.

### FAO-56 and the water-balance ledger

- <https://www.fao.org/4/x0490e/x0490e00.htm> FAO-56 (Allen, Pereira, Raes & Smith, 1998)
- <https://www.fao.org/4/x0490e/x0490e0b.htm> Ch. 6, single Kc (Table 12 grape values)
- <https://www.fao.org/4/x0490e/x0490e0e.htm> Ch. 8, Ks / TAW / RAW (Table 22 depletion fractions)
- <https://www.fao.org/4/x0490e/x0490e0p.htm> Annex 8, worked daily scheduling example
- <https://www.ndsu.edu/agriculture/extension/publications/irrigation-scheduling-checkbook-method> NDSU checkbook method
- <https://lgpress.clemson.edu/publication/irrigation-scheduling-methods-checkbook-vs-fao-56/> Clemson, checkbook vs FAO-56
- <https://irrigation.wsu.edu/Content/Fact-Sheets/FS083E.pdf> WSU FS083E, 50 percent depletion for grapes
- <https://alfalfasymposium.ucdavis.edu/+symposium/2022/powerpoints/Troy-Peters-2022-Principles-of-Scheduling-Irrigation-Soil-Moisture-Monitoring.pdf> Peters (2022), vineyard tension triggers

### California vineyard RDI

- <https://www.vineyardteam.org/files/Regulated_Deficit_Irrigation_Mgmt.pdf> Prichard, Smith & Verdegaal, RDI management for winegrapes
- <https://ucanr.edu/sites/default/files/2011-04/89518.pdf> Prichard et al. (2004), deficit irrigation of quality winegrapes
- <https://wineserver.ucdavis.edu/sites/g/files/dgvnsk2676/files/inline-files/1%20LEW%20Irrigation%20Shortcourse%20Napa%202019.pdf> Williams, UC Davis irrigation short course (2019)
- <https://www.ajevonline.org/content/58/2/173.short> Williams & Baeza (2007), VPD dependence of water potential
- <https://ucanr.edu/sites/default/files/2024-06/398346.pdf> UC ANR (2024), water use efficiency in vineyards (stem vs leaf thresholds)
- <https://advancedvit.com/plant_stress_measurements/> Advanced Viticulture, phenology-staged stem water-potential targets

### Public tools, regulation, certification

- <https://www.cimis.water.ca.gov/> CIMIS · <https://et.water.ca.gov/rest/index> CIMIS REST API
- <https://etdata.org/> OpenET · <https://www.nature.com/articles/s44221-023-00181-7> OpenET validation, Nature Water (2023)
- <https://www.usgs.gov/centers/eros/news/landsat-work-conserving-water-and-growing-high-quality-grapes> USGS EROS, Gallo vineyard case
- <https://www.nrcs.usda.gov/publications/nhcp-notice-179/449-cps-irrigation-water-management-2026.pdf> NRCS CPS 449 (2026)
- <https://water.ca.gov/programs/groundwater-management/sgma-groundwater-management> CA DWR, SGMA
- <https://ucanr.edu/sites/default/files/2026-04/GSDM_April%202026_Final_3.pdf> UC ANR (2026), groundwater markets and the San Joaquin cutback estimate
- <https://www.cdfa.ca.gov/oars/sweep/block_grant.html> CDFA SWEEP block-grant transition
- <https://lodigrowers.com/wp-content/uploads/2025/01/LODI-RULES-Binder-Standards-4th-Edition-with-Intro-2025.pdf> LODI RULES 4th Edition, Ch. 5
- <https://app.sipcertified.org/standards/all/current/preview> SIP Certified 2026 standards

### Adoption and commercial systems

- <https://ives-openscience.eu/wp-content/uploads/2023/07/Lambert_Survey-of-winegrape-irrigation.pdf> Lambert et al. (2023), winegrape irrigation survey
- <https://www.academia.edu/75658029/Understanding_and_promoting_adoption_of_irrigation_efficiency_practices_in_Paso_Robles_California_vineyards> Paso Robles adoption survey (2021)
- <https://tule.ag/how-to-videos/> Tule / CropX, measured stress coefficient
- <https://sentektechnologies.com/> Sentek · <https://semios.com/solutions/water-management/> Semios
- <https://florapulse.com/for-scientists/> FloraPulse continuous stem water potential
- <https://fruitionsciences.com/en/sap-flow-irrigation-sensors> Fruition Sciences
- <https://avf.org/research-summary/variable-rate-irrigation-scheduling-based-on-high-resolution-short-wave-infrared-sensing-and-internet-of-things-avf-project-2023-2718/> AVF variable-rate irrigation trial (2025)

### Machine learning for soil moisture and irrigation

Deforce et al. (2024), soil water potential forecasting against a persistence
baseline, arXiv:2405.18913 · Kontogiorgakis et al. (2026), 10 m soil moisture
with spatial cross-validation at 113 ISMN stations, arXiv:2602.18083 · Marsocci
et al. (2025), PANGAEA benchmark, IEEE Geoscience and Remote Sensing Magazine
14:245 · Shang, Das & Eldawy (2026), regional shift in geospatial foundation
models, arXiv:2606.29664 · Kisekka, Nicolas & Linker (2025), DSSAT
simulation-optimization field trial, Irrigation Science 43:1471 · Millán et al.
(2025), Irri_DesK digital twin, Agronomy 15(9):2132 · Kivi, Vergopolan &
Dokoohaki (2023), soil-moisture assimilation into APSIM, HESS 27:1173 · de Roos
et al. (2024), Sentinel-1 assimilation into AquaCrop, JGR Biogeosciences ·
Stojanova et al. (2025), Sensors 25:3658, the one vineyard study with an explicit
naive baseline · Kang et al. (2023), Computers and Electronics in Agriculture
208:107777 · King & Shellie (2023), four-season operational CWSI scheduling ·
Laroche-Pinel, Brillante et al. (2024), stem water potential from remote sensing ·
Žalik & Žalik (2023), Sensors 23(23):9566, and Shawon et al. (2026), IEEE Access
14:30513, federated learning in agriculture · Mamba Kabala et al. (2023),
Scientific Reports 13:19220.

### Reliability and replication in agricultural ML

Mohanty et al. (2016), Frontiers in Plant Science, PlantVillage generalization
gap · Noyan (2022), arXiv:2206.04374, background leakage in PlantVillage ·
Ploton et al. (2020), Nature Communications 11:4540, spatial validation ·
Meyer & Pebesma (2022), Nature Communications 13:2208, area of applicability ·
Kapoor & Narayanan (2023), Patterns 4(9):100804, leakage across fields · Corley
et al. (2023), arXiv:2305.13456, preprocessing sensitivity · Xu et al. (ICLR
2025), arXiv:2411.02796, simple baselines against foundation models · Lacoste et
al. (NeurIPS 2023 Datasets and Benchmarks), GEO-Bench · Wadoux, Heuvelink, de
Bruin & Brus (2021), Ecological Modelling 457:109692, the counterargument on
spatial cross-validation.

### Programs and testbeds

Kustas et al. (2022), Irrigation Science, GRAPEX · Anderson et al. (2021),
Remote Sensing of Environment 252:112189 · Cahn et al. (2025), CropManage
vineyard validation, IVES · Torres, Kurtural et al. (2021), Frontiers in Plant
Science 12:712622, 50 percent ETc at Oakville · Levin (2025), AJEV 76(2),
post-veraison deficit in Pinot noir · Pagay, Wine Australia project UA 1803-1.3,
University of Adelaide · <https://nrp.ai/cenic-precision-agriculture-2025> CENIC
and NRP precision agriculture at Iron Horse (source of the 10 percent target).

### VINE's own results referenced above

- [Event-conditioned evaluation](2026-08-05-event-study.md) · `assets/d2_event_study_results.csv`
- [Probabilistic CRPS forecasts](2026-08-05-crps-probabilistic.md) · `assets/d2_crps_results.csv`
- [Rain-gated water balance](2026-08-05-gated-water-balance.md) · `assets/d2_gated_results.csv`
- [First-passage alert probabilities](2026-08-05-first-passage-alerts.md)
- [Vintage validation](2026-08-04-d2-vintage-validation.md) · [Model card](../models/irrigation/persistence.md)
