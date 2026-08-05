# Architecture Decision Records

We record significant technical/tooling decisions as ADRs
([MADR](https://adr.github.io/madr/)-style). Each is immutable once accepted;
to change a decision, add a new ADR that supersedes the old one. Create one with
the `/adr` Claude command or copy [`0000-template.md`](0000-template.md).

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-monorepo-src-layout.md) | Monorepo with `src/` layout, one package, subpackage per track | Accepted |
| [0002](0002-uv-package-manager.md) | `uv` for environment & dependency management | Accepted |
| [0003](0003-track-priority.md) | Strict track priority + baseline-first methodology | Accepted |
| [0004](0004-config-management.md) | YAML + pydantic configs (defer Hydra) | Accepted |
| [0005](0005-experiment-tracking.md) | MLflow for tracking + DVC for data/model versioning | Accepted |
| [0006](0006-ndp-data-access.md) | NDP as discovery catalog (CKAN API under `/catalog`) | Accepted |
| [0007](0007-nrp-infrastructure.md) | NRP.ai infrastructure mapping (S3, CephFS, registry, LLM) | Accepted |
| [0008](0008-sensor-source-influxdb.md) | Sensor data from InfluxDB/ThingsBoard (not files) | Accepted |
| [0009](0009-weather-data-sources.md) | Weather: reanalysis archive + forecast (not AWIPS for history) | Accepted |
| [0010](0010-economic-value-for-alert-rules.md) | Cost-loss economic value for D2 irrigation alert rules | Accepted |
