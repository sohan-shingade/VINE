"""VINE — Vineyard Intelligence Network & Environment.

AI/ML models for agricultural analytics on the National Research Platform.
Packages are ordered by proposal deliverable (D1–D6); the three model tracks
share one data pipeline (`vine.d1_pipeline`) and `vine.common` utilities:

    vine.d1_pipeline    D1  ingestion, vegetation indices, feature engineering
    vine.d2_irrigation  D2  soil-moisture forecasting (ARIMA/Prophet/LSTM)
    vine.d3_vision      D3  plant-health computer vision (ResNet/EfficientNet)
    vine.d4_harvest     D4  harvest-timing forecasting (XGBoost/LSTM)
    vine.d5_evaluation  D5  cross-track evaluation against baselines
    vine.d6_serving     D6  FastAPI inference services
"""

__version__ = "0.1.0"
