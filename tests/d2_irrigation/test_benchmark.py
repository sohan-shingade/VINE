"""Tests for the frozen mentor-notebook benchmark manifest."""

from pathlib import Path

import pandas as pd
import pytest

from vine.d2_irrigation.benchmark import BenchmarkSpec, load_benchmark_spec, run_benchmark


def test_repository_benchmark_has_seven_unique_challengers():
    spec = load_benchmark_spec("configs/d2_irrigation/notebook_benchmark.yaml")
    assert len(spec.challengers) == 7
    assert len({c.family for c in spec.challengers}) == 7


def test_benchmark_rejects_wrong_family_count(tmp_path: Path):
    path = tmp_path / "benchmark.yaml"
    path.write_text("challengers:\n- {family: one, model: ridge, config: x.yaml}\n")
    with pytest.raises(ValueError, match="exactly seven"):
        load_benchmark_spec(path)


def test_run_benchmark_deduplicates_baselines(monkeypatch: pytest.MonkeyPatch):
    challengers = [{"family": f"f{i}", "model": f"m{i}", "config": "unused.yaml"} for i in range(7)]
    spec = BenchmarkSpec(challengers=challengers, horizons_h=[6])

    def fake_load_config(path):
        return {"model": Path(path).stem or "naive"}

    calls = 0

    def fake_run(frame, cfg):
        nonlocal calls
        model = f"m{calls}"
        calls += 1
        return pd.DataFrame(
            [
                {
                    "model": "persistence",
                    "horizon_h": 6,
                    "mae": 1.0 + calls / 10,
                    "skill_vs_persistence": 0.0,
                },
                {
                    "model": "seasonal_naive",
                    "horizon_h": 6,
                    "mae": 1.1,
                    "skill_vs_persistence": -0.1,
                },
                {
                    "model": "climatology",
                    "horizon_h": 6,
                    "mae": 2.0,
                    "skill_vs_persistence": -1.0,
                },
                {
                    "model": model,
                    "horizon_h": 6,
                    "mae": 1.2,
                    "skill_vs_persistence": -0.2,
                },
            ]
        )

    monkeypatch.setattr("vine.d2_irrigation.benchmark.load_config", fake_load_config)
    monkeypatch.setattr("vine.d2_irrigation.benchmark.run_experiment", fake_run)
    table = run_benchmark(pd.DataFrame({"soil_water": [1.0]}), spec)
    assert len(table[table.family.eq("baseline")]) == 3
    challengers_table = table[~table.family.eq("baseline")]
    assert len(challengers_table) == 7
    assert challengers_table["matched_persistence_mae"].nunique() == 7
