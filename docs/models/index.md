# Models

Every trained model gets a **model card** (after
[Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993), Mitchell et
al.). A card is required before a model is considered done — use the `/model-card`
command, starting from [`_template.md`](_template.md).

## Registry

| Model | Track | Status | Card |
|-------|-------|--------|------|
| Persistence + threshold | D2 irrigation | Shipped champion | [Card](irrigation/persistence.md) |
| Water-balance correction | D2 irrigation | Active experiment; not promoted | [Persistence card evidence](irrigation/persistence.md#evaluation) |
| NDVI/NDRE stress screening | D3 plant health | Engineering MVP; corrected live rerun pending | [Card](plant-health/stress-screening.md) |

Cards will be added here as models are trained, e.g.:

- `irrigation/lstm` — soil-moisture forecaster (D2)
- `cv/resnet50-stress` — plant-stress classifier (D3)
- `harvest/xgboost` — harvest-readiness regressor (D4)
