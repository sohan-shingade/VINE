"""D2 — irrigation scheduling: forecast soil moisture, recommend when to irrigate.

Models climb a complexity ladder, each compared against the one below
(see vine.d5_evaluation): naive -> threshold rule -> ARIMA/Prophet -> LSTM.
"""
