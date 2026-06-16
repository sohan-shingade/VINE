# Contributing to VINE

Full guide: [docs/guides/contributing.md](docs/guides/contributing.md).

Quick version:

1. Branch: `track/<deliverable>-<short-desc>` (e.g. `irrigation/d2-lstm-encoder`).
2. Explore → plan → implement. Small, shippable slices.
3. `make check` must pass before you push (CI runs the same gate).
4. A model isn't done until it beats its baseline on held-out data and has a
   [model card](docs/models/index.md).
5. Record significant decisions as [ADRs](docs/adr/index.md).

Conventions and code style live in [`CLAUDE.md`](CLAUDE.md).
