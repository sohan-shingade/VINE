# IHV NextCloud Share: Layout & Implementation Brief

> Scouted 2026-07-06 over the public share (read-only, no secrets). WebDAV base:
> `https://nextcloud.nrp-nautilus.io/public.php/webdav` with HTTP Basic user
> `ieAqEKDDKeYq9q4`, **empty password**. All paths below are relative to that base.
> Top level: `GIS/`, `_sorted_data/`, `_unsorted/`, `_misc/`, `research papers/`,
> `sensor reference/`.

## Q1. Block geometry: YES, polygons exist (two sources)

**`GIS/IHV-2026-05-26.kmz`** (14 MB; KMZ = zip: `doc.kml` 476 KB + `files/*.jpg` photos).
The KML uses namespaced tags (`<ns0:Polygon>` etc.), so a plain `<Polygon>` grep finds
nothing. Contents:

- **39 polygon placemarks = vineyard block boundaries**, names exactly:
  `1, 2, B North, B South, C1, C3, C4, C5, C8, Ca, Cb, Cc, Cd, Ce, Cf, E, F, G,
  H1, H2, H3, H4, H5, H6, I, J1, J2, L, M, N, O, P, P2, P6, P7, P9, Q,
  Train Barn, Triangle A`. These names match `_sorted_data/BLOCKS/<name>/` 1:1.
- **182 point placemarks**, incl. **sensor locations** (`EM500-CO2-915M-*`,
  `SE0X-LS-*`, `SDI-12-LS-US915-4`, per-probe sub-points) → gives the
  sensor→block spatial mapping D1 needs. Also georeferenced field photos per block.
- Parse with `zipfile` + any KML reader (`geopandas.read_file(..., driver='KML')`
  on the extracted `doc.kml`, or fastkml). Coordinates are lon/lat WGS84.

**`GIS/_archive/BLOCKS/`** (older, simpler to consume):
- `iron-horse.shp/.shx/.dbf/.prj/.cpg`, a tiny block shapefile (shp 2.3 KB).
- Per-block KML files: `Cd.kml`, `H5.kml`, … (one per block, ~4 KB each), plus
  combined `IHV-Blocks.kml` (84 KB) and `ihv.kml`; QGIS projects `Iron-Horse.qgz`.
- `GIS/_archive/Parcels_Public_Shapefile/` holds the Sonoma county parcel shapefile
  (235 MB; context only). `GIS/_archive/IHV 2026-03-25.kmz` = earlier KMZ rev.

`GIS/IHV-2026-06-01/` is orthomosaic layers (no vectors); `GIS/ugcs-export-2026-06-24/`
is 9 UgCS mission-plan JSONs (flight routes, e.g. `Mission of 1_8_2026 213 PM.json`,
`Jake Summer Flights Final.json`), useful for flight metadata rather than block polygons.

**Recommendation:** use the KMZ (newest, all 39 blocks + sensors); keep
`_archive/BLOCKS/iron-horse.shp` as cross-check.

## Q2. Orthomosaics: YES, stitched Pix4D(Fields) GeoTIFFs

Convention: Pix4DFields exports `<Layer>.data.tif` (float GeoTIFF, real values) +
`<Layer>.rgb.tif` (colorized render) + `<Layer>.legend.png`. Names contain spaces
(`Surface model.data.tif`), so URL-encode them as `%20`.

| Folder | Date | Coverage | Key files (size) |
|---|---|---|---|
| `GIS/h-blocks-pix4d-LAYERS-2025-08-29/` | 2025-08-27/29 | H blocks | `Orthomosaic.data.tif` **10.2 GB**, `Orthomosaic.rgb.tif` 353 MB; `NDVI.data.tif` 2.37 GB; `GNDVI/LCI/MCARI/NDRE/SIPI2 .data+.rgb.tif`; `Surface model.data.tif` 1.37 GB. 26 GB total |
| `GIS/DSM-2025-08-27/` | 2025-08-27 | H blocks | `Surface model.data.tif` 1.37 GB (+20 MB rgb) |
| `GIS/creek-rgb-pix4d-2025-10-03/` | 2025-10-03 | creek | `IHV-10-3-2025.png` 3.6 GB (PNG, not GeoTIFF) |
| `GIS/h4-rgb-pix4dfields-2025-12-16/Data/` | 2025-12-16 | H4 | Pix4DFields project internals: `img_<uuid>.tif` 4.9 GB, 2.8 GB (+`.ovr`), usable but unlabeled |
| `GIS/n-ndvi-2026-03-03/` | 2026-03-03 | N block | **NOT a mosaic** despite name: flat dump of 2,309 raw M3M files (23.6 GB, same naming as Q3) + PPK files |
| `GIS/dsm-2026-03-16/` | 2026-03-16 | (H?) | `Surface model.data.tif` 1.37 GB, byte-identical size to DSM-2025-08-27 (likely a copy); `reexport3.tif` 432 KB (valid little-endian TIFF, verified) |
| `GIS/all-blocks-pix4d-2026-05-28/` | 2026-05-28 | all blocks, DSM | `Surface model.data.tif` **9.3 GB** (merged) + split `Surface model 1/2-3/4.data.tif` (0.6 to 1.6 GB); `ugcs_dsm_3857_1m_int16*.tif` 9.7 MB (EPSG:3857 1 m DSM); 2 `.qgz` |
| `GIS/h4-dsm-pix4d-2026-05-29/` | 2026-05-29 | H4 DSM | `Surface model.data.tif` 1.8 GB; `h4_dsm_3857_1m_int16_max.tif` 398 KB |
| `GIS/sonoma-dem-1m-2026-05-29/` | 2013 LiDAR | site clip | `sonoma_dem_site_meters_1m.tif` 22 MB, county bare-earth DEM |
| `GIS/pix4d-rgb-2026-06-01/` | 2026-06-01 | whole vineyard RGB | `Orthomosaic.data.tif` **8.4 GB**, `.rgb.tif` 2.1 GB; `IHV tiles/` = XYZ web-tile pyramid z0 to z20 (+`IHV tiles.json`) |
| `GIS/IHV-2026-06-01/` | 2026-06-01 | whole vineyard, full index set | `Orthomosaic.data.tif` **17.7 GB**; `NDVI.data.tif` 4.1 GB; `GNDVI/LCI/MCARI/NDRE/SIPI2.data.tif` (2.5 to 4.2 GB each) + rgb + legends; `Surface model.data.tif` 2.9 GB. **46 GB total** |

**Bottom line:** stitched orthomosaics + NDVI/NDRE exist and D1 does *not* have to
stitch for 2025-08-27 (H blocks) and 2026-06-01 (whole vineyard). GIS/ totals ~128 GB.
The `.data.tif` files are huge, so read them windowed/masked per block polygon
instead of whole.

## Q3. Raw capture layout (`_sorted_data/`)

Depth 1: `BLOCKS/`, `CREEK/` (only `2025-10-03/`), `OFFICE/` (one flight folder
`DJI_202512171652_016 office circling/`).

`_sorted_data/BLOCKS/` has **39 block folders** (names = KMZ polygon names, plus a
`.gitkeep` in each). Blocks with date folders (rest are empty):

- `B North`: 2026-02-08, 2026-06-05, 2026-06-12 · `Ca`: 2026-02-08 · `Cb`: 2026-05-29
- `Cd`: 2025-12-13, -15, -16, -17 · `Ce`: 2025-12-15, -16 · `E`: 2025-12-13
- `F`: 2026-03-03, 2026-06-05 · `G`: 2026-03-03 · `H2`: 2025-08-28, -29
- `H4`: 2025-12-15, -16, 2026-01-07, -08, 2026-05-29 · `H5`: 2025-08-27, 2025-12-16, 2026-01-08
- `I`: 2025-12-15, 2026-01-08 · `P`: 2025-10-02, 2026-02-08

Structure: `BLOCKS/<Block>/<YYYY-MM-DD>/{m3m,mini}/` (either or both; e.g.
`Cd/2025-12-15/` has only `mini/`, `H5/2025-08-27/` only `m3m/`).

Inside `m3m/` (Mavic 3 Multispectral): one or more flight folders
`DJI_<YYYYMMDDHHMM>_<NNN>/` (start-time + take number), sometimes plus an
`images/` folder holding **copies of only the `_D` RGB JPGs** (e.g.
`H5/2026-01-08/m3m/` = `DJI_202601081523_001/` + `images/` with 570 JPGs).
Inside `mini/`: `images/` (RGB JPGs) or bare flight folders.

Flight-folder contents are flat, with no subfolders. For example,
`H5/2026-01-08/m3m/DJI_202601081523_001/` has **2,914 files** = 4 PPK/RTK files +
582 captures × 5 files (exactly: 582×5+4=2,914). `H4/2026-01-08/m3m/DJI_202601081557_002/`
= 1,724 files (344 captures). Naming, sampled:

```
DJI_202601081523_001_PPKNAV.nav / _PPKRAW.bin / _PPKOBS.obs / _Timestamp.MRK
DJI_20260108152708_0001_D_point1.JPG          # RGB visual, ~9-12 MB
DJI_20260108152708_0001_MS_G_point1.TIF       # Green band
DJI_20260108152708_0001_MS_NIR_point1.TIF     # NIR
DJI_20260108152708_0001_MS_RE_point1.TIF      # RedEdge
DJI_20260108152708_0001_MS_R_point1.TIF       # Red
```

Pattern: `DJI_<YYYYMMDDHHMMSS>_<seq 4-digit>_<D|MS_G|MS_R|MS_RE|MS_NIR>_point<K>.<JPG|TIF>`.
Every `MS_*` TIF is exactly 10,087,424 bytes. `point<K>` = mission waypoint id
(K restarts per flight; ties captures to the UgCS plan). Filenames are globally
unique (timestamp+seq), so a filename index is a safe join key.

## Q4. STAC reconciliation: hrefs are STALE (glob, don't rewrite)

STAC (`https://ndp-test.sdsc.edu/stac/collections/IHV_DJI_MULTISPECTRAL_DCIM/items`)
asset hrefs look like:
`https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4/download?path=_sorted_data/BLOCKS/<Block>/<date>/[m3m/]DJI_<flight>/<file>`.
Verified against WebDAV (PROPFIND Depth 0 on the exact `path=`):

| STAC href path | Exists? | Actual location |
|---|---|---|
| `H5/2025-08-27/m3m/DJI_202508271720_002/..._0072_MS_NIR_point39.TIF` | ✅ 207 | same, matches exactly |
| `H5/2026-01-08/m3m/DJI_202601081557_002/..._0343_MS_NIR_point85.TIF` | ❌ 404 | `H4/2026-01-08/m3m/DJI_202601081557_002/` (✅ 207): **flight re-sorted to a different block** |
| `H4/2025-12-16/DJI_202512161645_010/..._0059_MS_NIR_point7.TIF` | ❌ 404 (also 404 with `m3m/` inserted under H4) | `H5/2025-12-16/m3m/DJI_202512161645_010/`: **block changed AND `m3m/` level added** |

Mismatch pattern: the tree has been re-sorted since STAC indexing. Flights moved
between block folders and the `m3m/` level was inserted where hrefs lack it. The
flight-folder name `DJI_YYYYMMDDHHMM_NNN` and the filename are stable; the
block and the presence of `m3m/` are not. STAC's block attribution is therefore
untrustworthy, and its inventory (ends 2026-01-08) is behind the share, which now
has sorted flights through 2026-06-12 and unsorted ones through 2026-07-03.

**No deterministic URL rewrite works** (block segment changed). Reader strategy:
1. One-time PROPFIND sweep of `_sorted_data/BLOCKS/*/*/{m3m,mini}/` (≈40 blocks ×
   a few dates, ~60 cheap requests) → index `{flight_folder → (block, date, prefix)}`.
2. Resolve any STAC item by taking `DJI_..._NNN` + filename from its href and
   looking up the flight folder in the index. Date in filename == date folder.
3. Prefer trusting the *share's* block placement over STAC's, and re-derive
   block membership from capture GPS (EXIF) vs. KMZ polygons for ground truth.

## Q5. `_unsorted/` and `_misc/` (depth 1)

- `_unsorted/M3M/` holds ~120 flight folders `DJI_YYYYMMDDHHMM_NNN/`, 2026-01-17 →
  2026-07-03 (plus `probably dupes - m3m/`): the not-yet-sorted multispectral
  backlog, same leaf layout as Q3; none of it is in STAC. Likely >1 TB.
- `_unsorted/I360/` holds Insta360 field videos: paired `VID_*.insv` (many 20 to 28 GB) +
  `LRV_*.lrv` previews, Aug 2025 → Jun 2026; subfolders `Toms Insta 360 MP4s/`,
  `no_gps/`. Roughly ~0.8 to 1 TB. Irrelevant to D1/D3 models.
- `_unsorted/Mini/` holds DJI Mini RGB by date (`2025-12-15/`, `2026-01-08/`,
  `2026-06-01/`, `DJI_001 2026-06-02/`, `DJI_001 2026-06-08/`).
- `_unsorted/Salmon/` is empty.
- `_misc/` holds `3dgs/` (Gaussian-splat `.ply`, 0.6 to 0.9 GB, incl. block P & Cd),
  `pics/`, `presentations/`, `ugcs/` (mission JSONs, dup of GIS export).

## Implementer notes

- **Direct download**: `GET https://nextcloud.nrp-nautilus.io/public.php/webdav/<url-encoded path>`
  with `-u "ieAqEKDDKeYq9q4:"`, confirmed by downloading a 432 KB GeoTIFF (valid TIFF
  magic `II*\0`). **Range requests work** (`-r 0-1023` → 206), so partial/resumable
  reads of the giant orthomosaics are possible.
- The STAC-style URL `https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4/download?path=<path>`
  also works (no auth): it 303-redirects to `/public.php/dav/files/ieAqEKDDKeYq9q4/<path>`,
  so use `curl -L`. Same stale-path caveat as Q4.
- **Listing**: PROPFIND Depth 1 only (don't rely on Depth infinity). Parse `<d:href>`
  + `<d:getcontentlength>`; entries without a length are directories; first entry is
  the folder itself. URL-encode spaces (`Train%20Barn`, `Surface%20model.data.tif`).
- **Latency**: ~0.5 to 1 s per request; a 2,900-entry folder PROPFIND takes a few
  seconds. ~50 requests in a session drew no rate limiting or errors.
- **Volume**: GIS/ ≈ 128 GB; `_sorted_data` raw ≈ 0.5 TB (9,295 STAC captures ×
  ~50 MB/capture, plus newer sorted flights); `_unsorted` M3M backlog + I360 video
  likely ≈ 2 TB more. **Never bulk-mirror; pull per block/date, DVC-pin snapshots.**
- Empty-but-expected quirks: `N/` block folder is empty even though the N-block
  flight exists (as `GIS/n-ndvi-2026-03-03/` flat dump and in `_unsorted/M3M/
  DJI_20260303*`); `Cc`, `Q` (blocks previously seen in STAC) are now empty too;
  their flights presumably live under other blocks or `_unsorted`.
- MS TIFs' fixed 10,087,424-byte size is a handy integrity check after download.

## Evidence appendix (commands used, 2026-07-06)

```bash
B=https://nextcloud.nrp-nautilus.io/public.php/webdav
U='-u ieAqEKDDKeYq9q4:'
# list a folder (repeat per path; parse d:href + d:getcontentlength)
curl -s -X PROPFIND $U -H "Depth: 1" "$B/GIS/"
curl -s -X PROPFIND $U -H "Depth: 1" "$B/_sorted_data/BLOCKS/H5/2026-01-08/m3m/"
# KMZ polygons (tags are namespaced: grep ns0:Polygon, not <Polygon>)
curl -s $U -o /tmp/IHV.kmz "$B/GIS/IHV-2026-05-26.kmz"
python3 -c "import zipfile,re;k=zipfile.ZipFile('/tmp/IHV.kmz').read('doc.kml').decode();print(k.count('<ns0:Polygon'))"  # -> 39
# STAC items (retry on empty: replicas flap)
curl -s "https://ndp-test.sdsc.edu/stac/collections/IHV_DJI_MULTISPECTRAL_DCIM/items?limit=8"
curl -s ".../items?limit=5&datetime=2025-12-16T00:00:00Z/2025-12-17T00:00:00Z"
# existence check of an exact STAC path (207 = exists, 404 = gone)
curl -s -o /dev/null -w "%{http_code}" -X PROPFIND $U -H "Depth: 0" \
  "$B/_sorted_data/BLOCKS/H4/2026-01-08/m3m/DJI_202601081557_002/DJI_20260108161554_0343_MS_NIR_point85.TIF"
# download forms
curl -s $U -r 0-1023 -o /dev/null -w "%{http_code}" "$B/GIS/dsm-2026-03-16/reexport3.tif"   # 206
curl -sI "https://nextcloud.nrp-nautilus.io/s/ieAqEKDDKeYq9q4/download?path=_sorted_data/BLOCKS/H5/2025-08-27/m3m/DJI_202508271720_002/DJI_20250827172729_0072_MS_NIR_point39.TIF"  # 303 -> public.php/dav
```
