# 2026-07-06: D1 code-complete: the blockers were on the share all along

*Phase: D1 → D2 handoff (week 6). Previous post: project setup.*

## The short version

D1's imagery path had been blocked for two weeks. NextCloud had 503'd since
~June 21, and even with files back we believed we'd have to stitch raw
per-photo captures ourselves and had no vineyard-block polygons for the
per-block reporting contract. Today all three turned out to be non-problems:

1. **NextCloud came back** after the July 2 Ceph upgrade, verified by
   downloading a real 10.9 MB capture rather than by trusting a 200 on the
   front page.
2. A systematic walk of the share found `GIS/IHV-2026-05-26.kmz` with all 39
   block polygons (names matching `_sorted_data/BLOCKS/` 1:1) *plus* sensor
   locations, which is the sensor→block mapping D1 needed.
3. The same `GIS/` folder has stitched Pix4DFields orthomosaics, including
   pre-computed NDVI/NDRE layers, for the 2025-08-29 H-blocks and the whole
   vineyard on 2026-06-01. We don't need to stitch anything for those dates.

So D1 is now **code-complete and live-verified**: all three reachable inputs
(sensors, weather, imagery+geometry) flow end to end. 48 tests green.

## What got built

- **`d1_pipeline/webdav.py`**: a ~120-line NextCloud public-share client
  (PROPFIND parsing is pure and unit-tested; downloads are resume-safe).
  Zero new dependencies, since `requests` was already core.
- **`d1_pipeline/imagery.py`**: flight discovery + capture grouping +
  size-checked band downloads. The gotcha here is that **STAC's asset hrefs
  are stale.** The share tree was re-sorted after STAC indexing, with whole
  flights moved between block folders, so hrefs 404 and STAC's block
  attribution can't be trusted. Flight-folder names and filenames are the
  stable keys, so the reader indexes the tree (~60 cheap PROPFINDs) and treats
  the share's placement as authoritative.
- **`d1_pipeline/geo.py`**: block polygons from the KMZ (stdlib KML parsing:
  the tags are namespaced, so grep-for-`<Polygon>` finds nothing and KML
  drivers vary by install), windowed `zonal_stats` (the orthomosaics are
  10 to 18 GB; we read per-polygon windows, never whole files), and
  `assign_sensors_to_blocks` as a spatial join.
- **`vine imagery`** CLI to list flights on the share.

## Evidence (verify, then claim)

- Flight index: **34 flights** across 14 blocks, 2025-08-27 → 2026-06-12.
- One flight (`H5/2026-01-08`): grouped into **611 captures, 582 with all four
  bands**. That is 582×5 files + 4 PPK sidecars = 2,914, matching the folder
  exactly.
- Downloaded one capture's G/R/RE/NIR TIFs (each exactly 10,087,424 bytes,
  since the camera's fixed frame size doubles as an integrity check), read them
  with rasterio, and computed **NDVI mean 0.272**, plausible for a
  dormant-season vineyard.
- Loaded **39/39 block polygons**; joined **47 sensor placemarks** to blocks
  (e.g. the SE0X-LS-4 profile probe and its four depth sub-sensors → B North).
- Zonal stats on the real 1 m UgCS DSM: **all 39 blocks** returned pixels.

## Process notes

Two things made today fast. First, a **scout brief**: a disposable agent walked
the share (~24 tool calls) and wrote `docs/data/imagery-share-layout.md`, and
the implementation then read the brief instead of walking the tree again.
Second, **codemap shards** (`make codemap`): one generated markdown file per
package with every signature and import edge, so navigating the repo doesn't
require opening source files.

## Still open

- **Historical harvest/yield records** (input #3), the one remaining mentor
  question that gates D4.
- ~120 newer flights sit in `_unsorted/M3M/` (through 2026-07-03), not yet
  sorted into blocks; growing-season coverage is still thin.
- STAC re-indexing (its inventory ends 2026-01-08 and predates the re-sort).

## Next

**D2 irrigation** on the ready sensor+weather feature frame: persistence and
threshold baselines first, because per ADR-0003 nothing ships without beating
the rung below.
