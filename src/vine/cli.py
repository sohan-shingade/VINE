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
        from vine.d1_pipeline.ingest import ingest_all

        summary = ingest_all(start=args.start)
        for device, rows in sorted(summary.items()):
            print(f"  {device:<24} {rows:>8} rows")
        print(f"total: {sum(summary.values())} rows across {len(summary)} devices")
        return 0

    seed = seed_everything()
    log.info("starting", command=args.command, seed=seed)
    # TODO: dispatch to vine.<track>.train / vine.d5_evaluation.run once implemented.
    log.warning("not implemented yet", command=args.command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
