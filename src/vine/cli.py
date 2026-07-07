"""`vine` command-line entrypoint.

Thin dispatcher over the tracks. Every subcommand takes a YAML config so runs
are reproducible from config + seed alone.

    vine version
    vine ingest --start=-7d
    vine train irrigation configs/d2_irrigation/lstm.yaml
"""

from __future__ import annotations

import argparse
import sys

from vine import __version__
from vine.common import get_logger, seed_everything

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vine", description="VINE agricultural ML CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print version")

    ing = sub.add_parser("ingest", help="D1: pull IHV sensors from InfluxDB to data/raw")
    ing.add_argument("--start", default="-7d", help="Flux range start (e.g. -7d, -1w)")
    ing.add_argument(
        "--weather-days",
        type=int,
        default=0,
        help="also snapshot the last N days of Open-Meteo weather (0 = skip)",
    )

    img = sub.add_parser("imagery", help="D1: index drone flights on the NextCloud share")
    img.add_argument("--flight", default="", help="also list one flight's capture summary")

    train = sub.add_parser("train", help="train a model track")
    train.add_argument("track", choices=["irrigation", "vision", "harvest"])
    train.add_argument("config", help="path to YAML experiment config")

    ev = sub.add_parser("eval", help="run the cross-track evaluation")
    ev.add_argument("config", help="path to YAML eval config")

    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"vine {__version__}")
        return 0

    if args.command == "ingest":
        from vine.d1_pipeline.ingest import ingest_all, ingest_weather

        summary = ingest_all(start=args.start)
        for device, rows in sorted(summary.items()):
            print(f"  {device:<24} {rows:>8} rows")
        print(f"total: {sum(summary.values())} rows across {len(summary)} devices")
        if args.weather_days > 0:
            rows = ingest_weather(days=args.weather_days)
            print(f"weather: {rows} daily rows (last {args.weather_days}d)")
        return 0

    if args.command == "imagery":
        from vine.common.config import settings
        from vine.d1_pipeline.imagery import group_captures, index_flights
        from vine.d1_pipeline.webdav import ShareClient

        client = ShareClient(settings.imagery_share_url)
        index = index_flights(client)
        for f in sorted(index.values(), key=lambda f: (f.date, f.block)):
            print(f"  {f.date}  {f.block:<12} {f.camera:<5} {f.folder}")
        print(f"total: {len(index)} flights")
        if args.flight:
            captures = group_captures(client.ls(index[args.flight].path))
            full = sum(1 for c in captures if len(c.bands) == 4)
            print(f"{args.flight}: {len(captures)} captures, {full} with all 4 bands")
        return 0

    if args.command == "train" and args.track == "irrigation":
        from pathlib import Path

        import yaml

        from vine.d1_pipeline.ingest import load_snapshot, load_weather_snapshot
        from vine.d1_pipeline.pipeline import attach_weather, build_sensor_features
        from vine.d2_irrigation import IrrigationConfig, run_experiment
        from vine.d2_irrigation.experiment import log_to_mlflow

        cfg = IrrigationConfig(**yaml.safe_load(Path(args.config).read_text()))
        seed = seed_everything()
        try:
            raw = load_snapshot(cfg.device)
        except FileNotFoundError:
            print(
                f"no snapshot for device {cfg.device!r} — run `vine ingest` first "
                "(needs VINE_INFLUX_TOKEN in .env)"
            )
            return 1
        frame = build_sensor_features(raw, value_cols=cfg.features)
        weather = load_weather_snapshot()
        if weather is not None:
            frame = attach_weather(frame, weather)
        results = run_experiment(frame, cfg)
        print(results.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        log_to_mlflow(cfg, results, seed)
        return 0

    seed = seed_everything()
    log.info("starting", command=args.command, seed=seed)
    # TODO: dispatch to vine.d3_vision/.d4_harvest train + vine.d5_evaluation.run.
    log.warning("not implemented yet", command=args.command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
