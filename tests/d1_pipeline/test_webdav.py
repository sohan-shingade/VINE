"""NextCloud WebDAV client tests — URL/XML helpers (no network)."""

import pytest

from vine.d1_pipeline import webdav

SHARE = "https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4"

# Trimmed real-shaped PROPFIND multistatus: the folder itself + a subfolder
# + a file with a size and a percent-encoded space.
_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/public.php/webdav/GIS/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/webdav/GIS/all-blocks-pix4d-2026-05-28/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
  <d:response>
    <d:href>/public.php/webdav/GIS/IHV%202026.kmz</d:href>
    <d:propstat><d:prop><d:resourcetype/><d:getcontentlength>12345</d:getcontentlength></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
</d:multistatus>"""


def test_share_token_and_base():
    assert webdav.share_token(SHARE) == "ieAqEKDDKeYq9q4"
    assert webdav.webdav_base(SHARE) == "https://nextcloud.nrp-nautilus.io/public.php/webdav"


def test_share_token_rejects_non_share_url():
    with pytest.raises(ValueError, match="public-share"):
        webdav.share_token("https://nextcloud.nrp-nautilus.io/apps/files")


def test_parse_propfind_children_only():
    entries = webdav.parse_propfind(_XML)
    # the listed folder itself is dropped
    assert [e.path for e in entries] == ["GIS/all-blocks-pix4d-2026-05-28", "GIS/IHV 2026.kmz"]
    folder, file = entries
    assert folder.is_dir and folder.size == 0
    assert not file.is_dir and file.size == 12345


def test_walk_recurses_and_returns_files_only(monkeypatch):
    client = webdav.ShareClient(SHARE)
    tree = {
        "": [webdav.Entry("GIS", True, 0), webdav.Entry("readme.txt", False, 1)],
        "GIS": [webdav.Entry("GIS/a.tif", False, 10)],
    }
    monkeypatch.setattr(client, "ls", lambda path="": tree[path])
    files = client.walk()
    assert {e.path for e in files} == {"readme.txt", "GIS/a.tif"}


def test_download_skips_existing(tmp_path, monkeypatch):
    client = webdav.ShareClient(SHARE)
    dest = tmp_path / "x.jpg"
    dest.write_bytes(b"cached")

    def _boom(*a, **k):  # any network call is a failure
        raise AssertionError("network hit despite cached file")

    monkeypatch.setattr(webdav.requests, "get", _boom)
    assert client.download("some/path.jpg", dest) == dest
    assert dest.read_bytes() == b"cached"
