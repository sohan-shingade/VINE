# Glossary

| Term | Meaning |
|------|---------|
| **VINE** | Vineyard Intelligence Network & Environment — this project. |
| **NRP / Nautilus** | National Research Platform; its Kubernetes cluster (Nautilus) at SDSC. All compute runs here. |
| **Iron Horse** | Iron Horse Vineyards, Sebastopol CA — the demonstration site / living lab. |
| **LoRaWAN** | Low-power, long-range wireless network for distributed sensors across the vineyard. |
| **Multispectral imagery** | Drone images in multiple bands (RGB + NIR + Red-edge) used to compute vegetation indices. |
| **NDVI** | Normalized Difference Vegetation Index = (NIR − Red)/(NIR + Red). High = healthy canopy. |
| **NDRE** | Normalized Difference Red-Edge = (NIR − RedEdge)/(NIR + RedEdge). More sensitive to chlorophyll. |
| **Orthomosaic** | A georeferenced, stitched aerial image with consistent scale. |
| **GeoTIFF** | Raster image format carrying georeferencing metadata. |
| **GDD** | Growing Degree-Days — cumulative heat units driving crop development; a key harvest-timing feature. |
| **Brix** | Sugar content of grape juice; a ripeness signal for harvest timing. |
| **Block** | A management unit of the vineyard; predictions are reported per block. |
| **Walk-forward validation** | Time-series eval that trains on past, validates on future — no random shuffling. |
| **Baseline** | A naive or rule-based model every ML model must beat (e.g. persistence, threshold rule). |
| **MLflow** | Experiment tracking: logs params, metrics, artifacts per run. |
| **DVC** | Data Version Control: versions large data/model files outside git. |
| **ADR** | Architecture Decision Record — a short doc capturing one significant decision. |
| **Digital twin** | A separate VINE subproject; an interactive 3D model of the vineyard our predictions feed. |
