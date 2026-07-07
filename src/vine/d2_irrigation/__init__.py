"""D2 — irrigation scheduling: forecast soil moisture, recommend when to irrigate.

Models climb a complexity ladder, each compared against the one below
(see vine.d5_evaluation): persistence/seasonal/climatology -> ridge ->
ARIMA/Prophet -> LSTM. `experiment.run_experiment` scores a config's model
against all baselines walk-forward; `vine train irrigation <config>` runs it.
"""

from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.experiment import run_experiment

__all__ = ["IrrigationConfig", "run_experiment"]
