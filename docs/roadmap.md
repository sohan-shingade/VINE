# Roadmap

350 hours over 13 weeks (May 25 – Aug 24, 2026). Each phase ends with a working,
testable artifact — no big-bang integration. Mirrors the proposal timeline.

| Weeks | Dates | Phase | Deliverables |
|------:|-------|-------|--------------|
| 1–3 | May 25 – Jun 14 | Community Bonding | Setup NRP env, explore datasets, confirm sensor/imagery schema (light — UCSD finals) |
| 3–5 | Jun 8 – Jun 28 | **D1** Data Pipeline | Ingestion (sensors + imagery + history), feature engineering, vegetation indices, validation |
| 5–7 | Jun 22 – Jul 12 | **D2** Irrigation | ARIMA/Prophet baselines + LSTM, irrigation decision layer, walk-forward eval |
| 7–9 | Jul 6 – Jul 26 | **D3** CV | Multispectral preprocessing, CNN fine-tuning for stress + pest, spatial health maps |
| — | ~Jul 12 | **Midterm** | D1, D2 complete; D3 in progress |
| 9–10 | Jul 27 – Aug 9 | **D4 + D5** | Harvest timing models + cross-model evaluation report with ablations |
| 11–12 | Aug 3 – Aug 16 | **D6** Deployment | Dockerize models, deploy as K8s inference services on NRP with FastAPI |
| 12–13 | Aug 10 – Aug 24 | **D7** Docs + Polish | API docs, final blog post, code cleanup, handoff notes |

## Status legend
`☐ planned · ◐ in progress · ☑ done`

| Deliverable | Status |
|-------------|--------|
| D1 Data pipeline | ☑ done + live-verified |
| D2 Irrigation | ☑ persistence shipped; water balance active experiment |
| D3 Plant-health CV | ◐ label-free screening MVP; labels pending |
| D4 Harvest timing | ☐ blocked on historical records |
| D5 Evaluation report | ◐ walk-forward harness used by D2 |
| D6 NRP deployment | ◐ local API built; cluster deploy blocked on kubeconfig |
| D7 Docs & devlog | ◐ ongoing |

## Future work (post-GSoC)
Multi-site generalization (transfer learning to other vineyards), digital-twin
integration, operator feedback loop, multi-year climate analysis.
