"""Read Iron Horse Vineyards sensor data from InfluxDB.

This is the **primary** D1 sensor source (confirmed from the NRP starter repo
`nrp-precision-agriculture/iron-horse-vineyards/jupyter-notebooks`). Sensors
report over LoRaWAN into ThingsBoard, which writes to an InfluxDB bucket. Data
is queried with Flux and pivoted into tidy time-indexed frames.

    InfluxDB: https://nrp-thingsboard-influxdb.nrp-nautilus.io/
    org=Iron Horse Vineyards · bucket=ihv

The token is read from `VINE_INFLUX_TOKEN` (NRP secret) — **never hardcoded**.
Requires the `sensors` extra (`influxdb-client`); imported lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from vine.common.config import settings
from vine.common.logging import get_logger

if TYPE_CHECKING:
    import influxdb_client

log = get_logger(__name__)

# Device catalog from the IHV deployment (device_name -> kind).
DEVICES: dict[str, str] = {
    "SE01-LS-1": "soil",  # conductivity, temperature, water content
    "SE01-LS-2": "soil",
    "SE01-LS-3": "soil",
    "SE01-LS-4": "soil",
    "SE0X-LS-1": "soil_profile",  # multi-depth SOIL1..SOIL4
    "EM500-CO2-915M-1": "air",  # co2, humidity, temperature, pressure
    "EM500-CO2-915M-2": "air",
    "EM500-CO2-915M-3": "air",
    "EM500-CO2-915M-4": "air",
    "SenseCAP-S2103-CO2-1": "air",
    "SenseCAP-S2103-CO2-2": "air",
}

# Friendly aliases for the raw ThingsBoard measurement names.
MEASUREMENTS: dict[str, str] = {
    "soil_conductivity": "device_frmpayload_data_conduct_SOIL",
    "soil_temperature": "device_frmpayload_data_temp_SOIL",
    "soil_water": "device_frmpayload_data_water_SOIL",
    "co2": "device_frmpayload_data_co2",
    "humidity": "device_frmpayload_data_humidity",
    "temperature": "device_frmpayload_data_temperature",
    "pressure": "device_frmpayload_data_pressure",
}


# Flux query bookkeeping columns (always dropped).
_DROP_COLS = ("result", "table", "_start", "_stop")
# ThingsBoard metadata columns (dropped when tidy=True). device_name kept.
_META_COLS = ("_field", "application_name", "dev_eui", "f_port")
# Reverse of MEASUREMENTS so output columns read like `soil_temperature`.
_RAW_TO_FRIENDLY = {v: k for k, v in MEASUREMENTS.items()}


def build_flux(
    device_name: str,
    measurements: list[str],
    bucket: str,
    start: str = "-1w",
) -> str:
    """Build a Flux query for one device's measurements, pivoted by time.

    `measurements` are raw `_measurement` names (see MEASUREMENTS for aliases).
    """
    meas_filter = " or ".join(f'r["_measurement"] == "{m}"' for m in measurements)
    return f"""
from(bucket: "{bucket}")
  |> range(start: {start})
  |> filter(fn: (r) => r["device_name"] == "{device_name}")
  |> filter(fn: (r) => {meas_filter})
  |> pivot(rowKey:["_time"], columnKey: ["_measurement"], valueColumn: "_value")
"""


class InfluxReader:
    """Thin InfluxDB reader for IHV sensor data. Token must come from config."""

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        org: str | None = None,
        bucket: str | None = None,
    ) -> None:
        self.url = url or settings.influx_url
        self.token = token or settings.influx_token
        self.org = org or settings.influx_org
        self.bucket = bucket or settings.influx_bucket
        if not self.token:
            raise ValueError(
                "No InfluxDB token. Set VINE_INFLUX_TOKEN (from the NRP secret) — "
                "never hardcode it."
            )

    def _client(self) -> influxdb_client.InfluxDBClient:
        import influxdb_client

        return influxdb_client.InfluxDBClient(url=self.url, token=self.token, org=self.org)

    def read(
        self,
        device_name: str,
        measurements: list[str],
        start: str = "-1w",
        tidy: bool = True,
    ) -> pd.DataFrame:
        """Fetch one device's measurements into a time-indexed DataFrame.

        `measurements` accept friendly aliases (see MEASUREMENTS) or raw names.
        With `tidy=True`, drop InfluxDB/ThingsBoard metadata columns and rename
        raw `device_frmpayload_data_*` columns back to friendly names.
        """
        raw = [MEASUREMENTS.get(m, m) for m in measurements]
        query = build_flux(device_name, raw, self.bucket, start)
        client = self._client()
        try:
            df = client.query_api().query_data_frame(org=self.org, query=query)
        finally:
            client.close()
        if isinstance(df, list):
            df = pd.concat(df)
        df = df.drop(columns=[c for c in _DROP_COLS if c in df])
        if "_time" in df:
            df["_time"] = pd.to_datetime(df["_time"])
            df = df.set_index("_time")
        if tidy:
            df = df.drop(columns=[c for c in _META_COLS if c in df])
            df = df.rename(columns=_RAW_TO_FRIENDLY)
        log.info("influx read", device=device_name, rows=len(df))
        return df
