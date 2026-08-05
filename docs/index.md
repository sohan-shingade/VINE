# VINE: Vineyard Intelligence Network & Environment

> AI/ML models for agricultural analytics, running on the National Research
> Platform (NRP/Nautilus). Google Summer of Code 2026.

VINE turns raw vineyard data into predictions for **Iron Horse Vineyards**
(Sebastopol, CA), a working vineyard that is a living laboratory for CENIC,
UC San Diego, and partners. The inputs are LoRaWAN sensor streams and
multispectral drone imagery.

## What this subproject builds

Three ML model tracks and one shared data pipeline, deployed as inference
services on NRP Kubernetes:

| Track | Deliverable | Question it answers |
|-------|-------------|---------------------|
| **Irrigation** | D2 | When will soil moisture drop too low, and when should we irrigate? |
| **Plant health (CV)** | D3 | Which vineyard blocks are stressed or pest-damaged? |
| **Harvest timing** | D4 | When is each block ready to harvest? |

Supporting deliverables: **D1** shared data pipeline, **D5** evaluation report,
**D6** NRP deployment, **D7** docs + devlog (this wiki).

## Why it matters

California agriculture faces water scarcity, climate variability, labor
shortages, and rising costs. The CENIC and NRP precision-agriculture program at
Iron Horse states a target of roughly 10% water reduction through data-driven
irrigation; that figure is a program goal rather than a measured result, since
no baseline or experimental design has been published for it (see the
[irrigation control policy review](reports/2026-08-05-irrigation-control-review.md)).
VINE's contribution is to put validated model evidence behind that program, and
to publish open models + pipelines for the precision-agriculture research
community.

## Start here

- New to the repo? → [Getting started](guides/getting-started.md)
- Want the big picture? → [Architecture](architecture.md)
- Where it runs / where data lives? → [Infrastructure: NRP & NDP](infrastructure.md)
- What's the data? → [Data datasheet](data/index.md)
- Why is it built this way? → [Decisions (ADRs)](adr/index.md)
- Progress over time → [Devlog](devlog/index.md) · [Roadmap](roadmap.md)

## Project facts

| | |
|---|---|
| Contributor | Sohan Shingade (UC San Diego, B.S. Data Science) |
| Mentor | Mohammad Firas Sada (UCSD) |
| Compute | NRP/Nautilus Kubernetes (A100 / L40 / RTX A6000 GPU pods) |
| Timeline | 350 hours, 13 weeks (May 25 to Aug 24, 2026) |
| Repo | `gitlab.nrp-nautilus.io` (public), mirrored to GitHub |
| License | MIT |
