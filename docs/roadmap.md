# Roadmap

350 hours over 13 weeks. The coding period ends **2026-08-16**; the final
contributor submission is due **2026-08-24, 18:00 UTC**, and mentor evaluations
close 2026-08-31. Each phase ends with a working, testable artifact instead of a
big-bang integration. Mirrors the proposal timeline.

| Weeks | Dates | Phase | Deliverables |
|------:|-------|-------|--------------|
| 1 to 3 | May 25 to Jun 14 | Community Bonding | Setup NRP env, explore datasets, confirm sensor/imagery schema (light: UCSD finals) |
| 3 to 5 | Jun 8 to Jun 28 | **D1** Data Pipeline | Ingestion (sensors + imagery + history), feature engineering, vegetation indices, validation |
| 5 to 7 | Jun 22 to Jul 12 | **D2** Irrigation | ARIMA/Prophet baselines + LSTM, irrigation decision layer, walk-forward eval |
| 7 to 9 | Jul 6 to Jul 26 | **D3** CV | Multispectral preprocessing, CNN fine-tuning for stress + pest, spatial health maps |
| — | ~Jul 12 | **Midterm** | D1, D2 complete; D3 in progress |
| 9 to 10 | Jul 27 to Aug 9 | **D4 + D5** | Harvest timing models + cross-model evaluation report with ablations |
| 11 to 12 | Aug 3 to Aug 16 | **D6** Deployment | Dockerize models, deploy as K8s inference services on NRP with FastAPI |
| 12 to 13 | Aug 10 to Aug 24 | **D7** Docs + Polish | API docs, final blog post, code cleanup, handoff notes |

## Status legend
`☐ planned · ◐ in progress · ☑ done`

Status as of **2026-08-06 (week 11 of 13, 10 days of coding left)**:

| Deliverable | Status |
|-------------|--------|
| D1 Data pipeline | ☑ done + live-verified |
| D2 Irrigation | ☑ persistence shipped; water balance validated on real forecast vintages → gate fails, stays research |
| D3 Plant-health CV | ☑ label-free scope: corrected 39-block screen complete (39/39 pass coverage); supervised CV blocked on labels |
| D4 Harvest timing | ☑ descoped to exploratory per ADR-0003: label-free GDD context built (it is not a model and does not ship); full D4 blocked on historical records |
| D5 Evaluation report | ☑ walk-forward harness with `h−1` purge; final report regenerates offline from pinned snapshots |
| D6 NRP deployment | ◐ local API + non-root container verified; cluster access, storage, and seeded data all live; blocked only on a GitLab project to push the image to |
| D7 Docs & devlog | ☑ cards, reports, ADRs, devlog, and executed notebook renders current; MkDocs builds strict |

Honest read at week 11: every deliverable that can be finished without a human
input is finished. D6 is one `docker push` from done once the registry project
exists, and full D4 never unblocked. Its exploratory slice is the deliverable
unless harvest records appear before Aug 16. Remaining effort goes to handoff
docs and the final GSoC submission.

## Future work (post-GSoC)
Multi-site generalization (transfer learning to other vineyards), digital-twin
integration, operator feedback loop, multi-year climate analysis.
