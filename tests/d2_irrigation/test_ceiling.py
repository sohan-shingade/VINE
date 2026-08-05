"""CRPS skill ceiling (D2): GMD identities, closed forms, attainment, runner."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vine.d2_irrigation.ceiling import (
    GAUSSIAN_CEILING,
    gini_mean_difference,
    run_ceiling_experiment,
    shape_sample,
    shape_sample_weighted,
    skill_ceiling,
    weighted_gini_mean_difference,
)
from vine.d2_irrigation.config import IrrigationConfig
from vine.d2_irrigation.probabilistic import empirical_crps, gaussian_crps

CEILING_COLUMNS = [
    "device",
    "model",
    "horizon_h",
    "n",
    "crps",
    "crps_skill",
    "crps_skill_fold_median",
    "crps_skill_fold_min",
    "ceiling",
    "efficiency",
    "efficiency_fold_min",
    "ceiling_oracle",
    "efficiency_oracle",
    "cov50",
    "cov90",
]

MODELS = {"persistence-point", "gaussian-ewma", "fhs-ewma", "fhs-adaptive"}


def _idx(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")


def _random_walk(n: int = 3000, step: float = 0.2, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(30.0 + np.cumsum(rng.normal(0.0, step, n)), index=_idx(n))


# --- gini_mean_difference ---


def test_gini_mean_difference_matches_brute_force():
    # Definition: mean |z_i - z_j| over all n^2 ordered pairs, diagonal
    # included in the denominator (same convention as empirical_crps spread).
    rng = np.random.default_rng(0)
    for n in (2, 3, 7, 25):
        z = rng.normal(0.0, 2.0, n)
        brute = float(np.mean(np.abs(z[:, None] - z[None, :])))
        assert abs(gini_mean_difference(z) - brute) < 1e-12


def test_gini_mean_difference_empty_and_singleton():
    with pytest.raises(ValueError):
        gini_mean_difference(np.array([]))
    assert gini_mean_difference(np.array([3.0])) == 0.0


def test_weighted_gini_mean_difference_matches_brute_force():
    rng = np.random.default_rng(20)
    for n in (2, 5, 30):
        z = rng.normal(0.0, 2.0, n)
        w = rng.uniform(0.1, 3.0, n)
        brute = float(np.sum(w[:, None] * w[None, :] * np.abs(z[:, None] - z[None, :])))
        brute /= float(w.sum()) ** 2
        assert abs(weighted_gini_mean_difference(z, w) - brute) < 1e-12


def test_weighted_gini_mean_difference_reduces_to_unweighted():
    rng = np.random.default_rng(21)
    z = rng.laplace(0.0, 1.0, 200)
    w = np.full_like(z, 0.7)
    assert abs(weighted_gini_mean_difference(z, w) - gini_mean_difference(z)) < 1e-12


def test_weighted_gini_mean_difference_rejects_bad_weights():
    z = np.array([1.0, 2.0])
    with pytest.raises(ValueError):
        weighted_gini_mean_difference(np.array([]), np.array([]))
    with pytest.raises(ValueError):
        weighted_gini_mean_difference(z, np.array([1.0]))
    with pytest.raises(ValueError):
        weighted_gini_mean_difference(z, np.array([1.0, -0.5]))
    with pytest.raises(ValueError):
        weighted_gini_mean_difference(z, np.zeros(2))


# --- skill_ceiling closed forms ---


def test_skill_ceiling_gaussian_closed_form():
    # Gaussian: 1 - 1/sqrt(2), roughly 0.292893.
    rng = np.random.default_rng(1)
    z = rng.standard_normal(200_000)
    assert abs(skill_ceiling(z) - GAUSSIAN_CEILING) < 0.005
    assert abs(GAUSSIAN_CEILING - (1.0 - 1.0 / np.sqrt(2.0))) < 1e-15


def test_skill_ceiling_laplace_closed_form():
    # Laplace: E|X| = b, GMD = 3b/2, ceiling = 1/4 exactly. Heavy tails
    # converge slower, so the tolerance is looser.
    rng = np.random.default_rng(2)
    z = rng.laplace(0.0, 1.0, 200_000)
    assert abs(skill_ceiling(z) - 0.25) < 0.01


def test_skill_ceiling_uniform_closed_form():
    # Uniform on -1 to 1: E|X| = 1/2, GMD = 2/3, ceiling = 1/3 exactly.
    rng = np.random.default_rng(3)
    z = rng.uniform(-1.0, 1.0, 200_000)
    assert abs(skill_ceiling(z) - 1.0 / 3.0) < 0.005


def test_heavier_tails_lower_the_ceiling():
    rng = np.random.default_rng(4)
    t3 = rng.standard_t(3, 200_000)
    gauss = rng.standard_normal(200_000)
    assert skill_ceiling(t3) < skill_ceiling(gauss)


def test_skill_ceiling_nan_cases():
    assert np.isnan(skill_ceiling(np.zeros(50)))  # mean |z| below the floor
    assert np.isnan(skill_ceiling(np.array([1.0])))  # fewer than 2 points


def test_skill_ceiling_scale_invariance():
    rng = np.random.default_rng(5)
    z = rng.laplace(0.0, 1.0, 500)
    assert abs(skill_ceiling(z) - skill_ceiling(3.7 * z)) < 1e-12


# --- shape_sample ---


def test_shape_sample_sorted_capped_and_deterministic():
    rng = np.random.default_rng(6)
    z = rng.normal(0.0, 1.0, 2000)
    a = shape_sample(z, max_sample=512)
    b = shape_sample(z, max_sample=512)
    np.testing.assert_array_equal(a, b)
    assert len(a) == 512
    assert np.all(np.diff(a) >= 0)
    # linspace endpoints hit index 0 and n-1 of the sorted array
    assert a[0] == z.min()
    assert a[-1] == z.max()


def test_shape_sample_small_input_returns_all_sorted():
    rng = np.random.default_rng(7)
    z = rng.normal(0.0, 1.0, 100)
    out = shape_sample(z, max_sample=512)
    np.testing.assert_array_equal(out, np.sort(z))
    with pytest.raises(ValueError):
        shape_sample(np.array([]))


def test_shape_sample_weighted_equal_weights_close_to_unweighted():
    rng = np.random.default_rng(22)
    z = rng.normal(0.0, 1.0, 5000)
    a = shape_sample_weighted(z, np.ones_like(z), max_sample=256)
    b = shape_sample(z, max_sample=256)
    assert np.all(np.diff(a) >= 0)
    # Different quantile conventions, same law: interior quantile points nearly
    # agree; the extremes differ because linspace hits the exact min and max
    # while cumulative-weight midpoints never reach probability 0 or 1.
    assert float(np.abs(a[10:-10] - b[10:-10]).max()) < 0.1


def test_shape_sample_weighted_tilts_toward_heavy_rows():
    rng = np.random.default_rng(23)
    z = np.concatenate([rng.normal(-2.0, 0.1, 500), rng.normal(2.0, 0.1, 500)])
    w = np.concatenate([np.full(500, 1e-6), np.ones(500)])
    out = shape_sample_weighted(z, w, max_sample=64)
    # Essentially all mass sits on the heavily weighted positive cluster.
    assert float(np.median(out)) > 1.5


def test_shape_sample_weighted_rejects_bad_weights():
    z = np.array([1.0, 2.0])
    with pytest.raises(ValueError):
        shape_sample_weighted(np.array([]), np.array([]))
    with pytest.raises(ValueError):
        shape_sample_weighted(z, np.array([1.0]))
    with pytest.raises(ValueError):
        shape_sample_weighted(z, np.array([1.0, -0.5]))
    with pytest.raises(ValueError):
        shape_sample_weighted(z, np.zeros(2))


# --- attainment: the FHS recipe reaches the theoretical ceiling ---


def test_fhs_ensemble_attains_the_laplace_ceiling():
    # Martingale theorem: max CRPS skill vs the persistence point mass equals
    # 1 - 0.5 * GMD(Z) / E|Z| for the standardized innovation Z. Score a
    # 512-member Laplace shape against independent Laplace observations and
    # check the realized skill lands on the ceiling, which sits below the
    # Gaussian ceiling because Laplace tails are heavier.
    rng = np.random.default_rng(8)
    u = rng.laplace(0.0, 1.0, 20_000)
    shape = shape_sample(rng.laplace(0.0, 1.0, 20_000), max_sample=512)
    crps = empirical_crps(shape, u)
    skill = 1.0 - float(crps.mean()) / float(np.abs(u).mean())
    ceiling = skill_ceiling(rng.laplace(0.0, 1.0, 500_000))
    assert abs(skill - ceiling) < 0.02
    assert skill < GAUSSIAN_CEILING + 0.02
    # A variance-matched Gaussian closed form is the wrong shape for these
    # heavy tails and must score worse than the ensemble.
    sigma = float(u.std())
    crps_gauss = gaussian_crps(u, np.zeros_like(u), np.full_like(u, sigma))
    assert crps_gauss.mean() > crps.mean()


# --- run_ceiling_experiment ---


def test_run_ceiling_experiment_schema_and_invariants():
    frames = {"a": pd.DataFrame({"soil_water": _random_walk(2000, seed=9)})}
    cfg = IrrigationConfig(model="probabilistic", horizons_h=[3], n_folds=3)
    results = run_ceiling_experiment(frames, cfg)
    assert list(results.columns) == CEILING_COLUMNS
    for (_, _), block in results.groupby(["device", "horizon_h"]):
        assert set(block.model) == MODELS
        assert block.n.nunique() == 1  # every model scored on identical rows
        assert block.ceiling.nunique() == 1  # the ceiling is a property of the cell
    # A point mass's CRPS is its MAE, so persistence has zero self-skill and
    # zero efficiency by construction.
    pers = results[results.model == "persistence-point"]
    assert np.allclose(pers.crps_skill, 0.0)
    assert np.allclose(pers.efficiency, 0.0)
    assert ((results.ceiling > 0.0) & (results.ceiling < 1.0)).all()
    spread = results[results.model.isin({"gaussian-ewma", "fhs-ewma", "fhs-adaptive"})]
    assert (spread.crps > 0.0).all()
    assert results.cov50.between(0.0, 1.0).all()
    assert results.cov90.between(0.0, 1.0).all()
    # The oracle ceiling is the realized per-fold hindsight optimum over
    # sigma-scaled single-shape laws, so no such model, both FHS variants
    # included, can exceed it: efficiency_oracle <= 1 holds deterministically.
    fhs = results[results.model.isin({"fhs-ewma", "fhs-adaptive"})]
    assert (fhs.efficiency_oracle <= 1.0 + 1e-9).all()
    assert (fhs.crps_skill <= fhs.ceiling_oracle + 1e-9).all()


# Note: no runner-level causality guard here. test_probabilistic.py has no
# poison-tail test on run_probabilistic_experiment either; its causality tests
# target ewma_sigma_series and fixed_sigma_series directly, and the EWMA sigma
# reused by this runner is already covered there.
