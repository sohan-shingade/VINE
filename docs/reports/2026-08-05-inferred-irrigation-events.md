# D2 report: inferred irrigation events from soil-moisture rises

**Deliverable:** D2 irrigation · **Date:** 2026-08-05 · **Status:** exploratory
catalog, unvalidated. For the mentor to check against real irrigation logs.

During the dry season soil moisture only rises when water arrives, from rain
or from irrigation. We have daily rain totals, so any sharp sustained rise on
a dry day is a candidate irrigation event. This report catalogs those
candidates across the five soil probes in the pinned snapshots
(2026-01-22 to 2026-07-08).

## Method

1. Regularize each probe's `soil_water` to the hourly grid; missing hours stay
   NaN (the shared multi-day outages of Feb 16 to 17, May 8 to 19, and
   Jun 24 to Jul 8 are never filled).
2. A rise event is a run of consecutive hours each increasing, kept when the
   cumulative rise is at least 0.5 sensor units within at most 12 hours. Any
   event whose window spans or abuts a NaN hour is discarded, so nothing is
   detected across or next to a data gap.
3. An event is attributed to rain when daily precipitation on its start day or
   the previous day is at least 1.0 mm. Everything else is inferred
   irrigation.

Parameter note: with the initial min_jump of 1.0 every detected event was
rain. Rain rises span 0.6 to 36.6 units, while the sustained rises on
zero-rain days sit between 0.5 and 1.0 units, so min_jump was lowered to 0.5.
Below that (0.3) the catalog starts admitting sub-0.5 wiggles that are hard to
tell from noise. Code: `vine.d2_irrigation.events`, runner
`scripts/d2_irrigation_events.py`, full catalog
`assets/d2_inferred_irrigation_events.csv` (55 events).

## Per-probe counts

| Probe | Rise events | Rain | Inferred irrigation |
|---|---|---|---|
| SE01-LS-1 | 11 | 9 | 2 |
| SE01-LS-2 | 15 | 15 | 0 |
| SE01-LS-3 | 16 | 16 | 0 |
| SE01-LS-4 | 7 | 5 | 2 |
| SE0X-LS-1 | 6 | 6 | 0 |
| **Total** | **55** | **51** | **4** |

Median jump: 0.62 units for inferred irrigation, 2.47 units for rain. Typical
spacing between successive rise events on one probe is 1 to 5 days (all inside
the February and April storm windows plus mid-March); the two irrigation
events on each probe are 4.1 days apart on SE01-LS-1 and 5.8 days apart on
SE01-LS-4.

## The inferred irrigation events

| Probe | Start (UTC) | End (UTC) | Trough | Peak | Jump | Hours |
|---|---|---|---|---|---|---|
| SE01-LS-1 | 2026-03-11 21:00 | 2026-03-12 04:00 | 29.61 | 30.28 | 0.67 | 7 |
| SE01-LS-1 | 2026-03-16 00:00 | 2026-03-16 08:00 | 28.95 | 29.46 | 0.51 | 8 |
| SE01-LS-4 | 2026-03-12 04:00 | 2026-03-12 13:00 | 23.76 | 24.72 | 0.96 | 9 |
| SE01-LS-4 | 2026-03-18 00:00 | 2026-03-18 11:00 | 24.04 | 24.61 | 0.57 | 11 |

All four fall in a rain-free stretch (zero recorded precipitation
2026-03-08 to 2026-03-20). SE01-LS-1 and SE01-LS-4 both rise overnight on
March 11 to 12, which reads like one watering pass reaching two probes. The
overnight timing and the multi-hour ramp shape are consistent with drip
irrigation.

## Limitations

- Jumps are in raw sensor units. No calibration to water volume exists, so a
  jump size says nothing quantitative about how much water was applied.
- The events are inferred and unvalidated. This catalog is a checklist for the
  mentor to compare against real irrigation logs; agreement or disagreement
  would itself be useful ground truth.
- Probe placement relative to drip emitters strongly affects jump size. A
  probe between emitters can miss an irrigation entirely, so zero events on a
  probe does not mean zero irrigation near it.
- The peak irrigation months are poorly observed: the snapshots end July 8 and
  the May 8 to 19 and Jun 24 to Jul 8 outages remove most of the late dry
  season. The one sub-threshold candidate in June (SE01-LS-2, June 5,
  +0.38 units) suggests summer irrigation may sit below the 0.5 detection
  threshold at these probes.
- Rain attribution uses one Open-Meteo grid cell for the whole vineyard at
  daily resolution. Light rain under 1 mm counts as dry, so a drizzle-day rise
  could be mislabeled as irrigation.
