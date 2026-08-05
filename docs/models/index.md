# Models

Every trained model gets a **model card** (after
[Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993), Mitchell et
al.). A card is required before a model is considered done. Use the `/model-card`
command, starting from [`_template.md`](_template.md).

## Registry

| Model | Track | Status | Reference |
|-------|-------|--------|------|
| Persistence + threshold | D2 irrigation | Shipped champion | [Card](irrigation/persistence.md) |
| Water-balance correction | D2 irrigation | Research; rejected by the worst-fold gate on real forecast vintages. No card, because it did not ship | [Vintage validation report](../reports/2026-08-04-d2-vintage-validation.md) |
| NDVI/NDRE stress screening | D3 plant health | Engineering artifact; corrected 39-block screen current | [Card](plant-health/stress-screening.md) |
| GDD phenology exploration | D4 harvest | **Not a model**: label-free exploratory context; does not ship | [Card](harvest/gdd-exploration.md) |

Cards will be added here as models are trained, e.g.:

- `irrigation/lstm`, a soil-moisture forecaster (D2)
- `cv/resnet50-stress`, a plant-stress classifier (D3)
- `harvest/xgboost`, a harvest-readiness regressor (D4)
