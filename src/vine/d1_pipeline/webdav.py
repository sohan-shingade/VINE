"""NextCloud public-share WebDAV client — transport for D1 imagery (input #2).

The IHV drone imagery lives on a NextCloud public share. The STAC catalog
indexes captures but its asset hrefs are stale (they point at flight subfolders
that no longer exist), so the reliable path is to walk the share's WebDAV tree
directly and download by real path:

    share:  https://nextcloud.nrp-nautilus.io/s/<token>          (public)
    webdav: https://nextcloud.nrp-nautilus.io/public.php/webdav  (Basic <token>:"")

The XML parsing is pure (unit-tested without network); `ShareClient` is the
thin I/O edge. `requests` is a core dependency — no new deps.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import requests

from vine.common.logging import get_logger

log = get_logger(__name__)

_DAV = {"d": "DAV:"}


@dataclass(frozen=True)
class Entry:
    """One file or folder in the share, path relative to the share root."""

    path: str  # e.g. "_sorted_data/BLOCKS/H5/2026-01-08/m3m/images/DJI_...JPG"
    is_dir: bool
    size: int  # bytes; 0 for folders


def share_token(share_url: str) -> str:
    """Extract the share token from a NextCloud public-share URL (…/s/<token>)."""
    parts = [p for p in urlsplit(share_url).path.split("/") if p]
    if len(parts) < 2 or parts[-2] != "s":
        raise ValueError(f"not a NextCloud public-share URL: {share_url}")
    return parts[-1]


def webdav_base(share_url: str) -> str:
    """Public-share WebDAV endpoint for the NextCloud instance hosting `share_url`."""
    u = urlsplit(share_url)
    return f"{u.scheme}://{u.netloc}/public.php/webdav"


def parse_propfind(xml_text: str) -> list[Entry]:
    """Parse a PROPFIND multistatus response into entries (pure, network-free).

    Paths are percent-decoded and made relative to the share root. The listed
    folder itself (first response) is excluded — only children are returned.
    """
    root = ET.fromstring(xml_text)
    entries = []
    for response in root.findall("d:response", _DAV):
        href = unquote(response.findtext("d:href", "", _DAV))
        rel = href.split("/public.php/webdav", 1)[-1].strip("/")
        prop = response.find("d:propstat/d:prop", _DAV)
        is_dir = prop is not None and prop.find("d:resourcetype/d:collection", _DAV) is not None
        size = int(prop.findtext("d:getcontentlength", "0", _DAV) or 0) if prop is not None else 0
        entries.append(Entry(path=rel, is_dir=is_dir, size=size))
    return entries[1:]  # drop the listed folder itself


class ShareClient:
    """Minimal read-only client for one NextCloud public share.

    Auth is HTTP Basic with the share token as username and empty password —
    the token is the public share id, not a secret.
    """

    def __init__(self, share_url: str, timeout: float = 60.0):
        self.base = webdav_base(share_url)
        self.auth = (share_token(share_url), "")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base}/{quote(path.strip('/'))}"

    def ls(self, path: str = "") -> list[Entry]:
        """List one folder (depth 1) as entries relative to the share root."""
        resp = requests.request(
            "PROPFIND",
            self._url(path),
            auth=self.auth,
            headers={"Depth": "1"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return parse_propfind(resp.text)

    def walk(self, path: str = "", max_depth: int = 10) -> list[Entry]:
        """Recursively list files under `path` (folders traversed, not returned)."""
        files: list[Entry] = []
        for entry in self.ls(path):
            if entry.is_dir:
                if max_depth > 0:
                    files += self.walk(entry.path, max_depth=max_depth - 1)
            else:
                files.append(entry)
        return files

    def download(self, path: str, dest: str | Path, skip_existing: bool = True) -> Path:
        """Download one file to `dest` (a file path); returns the local path.

        With `skip_existing`, a non-empty local file is reused — captures are
        immutable once uploaded, so size-on-disk is a sufficient cache key.
        """
        dest = Path(dest)
        if skip_existing and dest.exists() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(self._url(path), auth=self.auth, stream=True, timeout=self.timeout) as r:
            r.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.rename(dest)
        log.info("downloaded", path=path, bytes=dest.stat().st_size)
        return dest
