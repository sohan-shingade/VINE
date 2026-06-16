"""National Data Platform (NDP) client — the source of VINE's data.

Iron Horse Vineyards data is published on the National Data Platform
(https://nationaldataplatform.org), a CKAN-based catalog. This module is a thin
wrapper over the standard CKAN Action API so the D1 pipeline can discover and
download datasets reproducibly instead of hand-copying files.

CKAN actions used: `package_search`, `package_show`, `organization_show`.
The base URL, org slug, and API key are configurable (see vine.common.config) —
set `VINE_NDP_API_KEY` for private/embargoed datasets.

⚠️ UNVERIFIED: as of 2026-06-16 the public NDP site serves a Next.js app and
does NOT expose a standard CKAN `/api/3` endpoint — these calls 404. This client
is a placeholder for when the real NDP catalog API + auth are confirmed with the
mentor, or when cleaned data is published there. The live source is InfluxDB
(`vine.d1_pipeline.influx`). Do not assume this works yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from vine.common.config import settings
from vine.common.logging import get_logger

log = get_logger(__name__)


class NDPClient:
    """Minimal CKAN Action API client for the National Data Platform."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = (base_url or settings.ndp_base_url).rstrip("/")
        self.api_key = api_key or settings.ndp_api_key
        self.timeout = timeout
        self._session = requests.Session()
        if self.api_key:
            self._session.headers["Authorization"] = self.api_key

    def _action(self, action: str, **params: Any) -> Any:
        """Call a CKAN action endpoint and return its `result` payload."""
        url = f"{self.base_url}/api/3/action/{action}"
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success", False):
            raise RuntimeError(f"NDP action {action} failed: {body.get('error')}")
        return body["result"]

    def search(self, query: str = "vineyard", rows: int = 50) -> list[dict[str, Any]]:
        """Search datasets. Returns the list of matching CKAN packages."""
        result = self._action("package_search", q=query, rows=rows)
        return result.get("results", [])

    def list_org_datasets(self, org: str | None = None) -> list[dict[str, Any]]:
        """List datasets belonging to an organization (default: Iron Horse)."""
        org = org or settings.ndp_org
        result = self._action("organization_show", id=org, include_datasets=True)
        return result.get("packages", [])

    def dataset(self, name: str) -> dict[str, Any]:
        """Fetch a single dataset's full metadata (incl. its resources)."""
        return self._action("package_show", id=name)

    def download_resource(self, url: str, dest: str | Path) -> Path:
        """Stream a CKAN resource (file) to a local path."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._session.get(url, stream=True, timeout=self.timeout) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        log.info("downloaded", url=url, dest=str(dest))
        return dest
