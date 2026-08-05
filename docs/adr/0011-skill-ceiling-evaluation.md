# ADR-0011: Skill ceiling and efficiency as the D2 probabilistic evaluation lens

- **Status:** Accepted
- **Date:** 2026-08-05
- **Deciders:** Sohan Shingade (+ mentor)

## Context
Rung 14 showed that with the forecast center fixed at persistence, a
calibrated spread earns positive CRPS skill in every probe/horizon cell.
Skill against persistence has no natural scale, though: nothing says
whether +0.19 is most of what this record allows or a small fraction of it,
and a challenger tuned hard enough to look good on aggregate skill can
still be overfit. For a near-martingale state the maximum attainable CRPS
skill over the persistence point mass has a closed form, ceiling =
1 - 0.5 * GMD(Z) / E|Z|, a pure shape functional of the standardized
innovation Z (Gaussian: 1 - 1/sqrt(2), about 0.2929; heavier tails lower
it). A second, exactly computable bound comes from propriety plus positive
homogeneity: per evaluation fold, the best sigma-scaled single-shape law in
hindsight realizes total CRPS 0.5 * weighted_GMD(u, sigma) * sum(sigma), so
no such forecaster can beat it on the record.

## Decision
Probabilistic D2 forecasters are evaluated as a fraction of attainable
skill, not on raw skill alone. Every probabilistic rung reports, per
probe/horizon cell: the training-shape ceiling (causal estimate of the
population functional), the oracle ceiling (exact per-fold hindsight bound),
and efficiency against each, alongside the existing aggregate and worst-fold
skill columns. The ADR-0003 worst-fold gate is unchanged and remains the
promotion hurdle. Efficiency against the oracle is the headline attainment
number because it is deterministically bounded by one and cannot be inflated
by tuning; the training-shape ceiling is reported as an estimate only, since
a holdout calmer than training can push realized skill above it.

## Considered options
- **Ceiling and efficiency columns plus the existing gate (chosen)**: gives
  skill a denominator, separates "model is weak" from "record has no more
  skill to give", and the oracle bound is immune to overfitting by
  construction.
- **Raw CRPS skill only**: leaves the frontier question unanswerable and
  invites endless challenger rungs with no stopping criterion.
- **Compare against literature benchmarks**: irrigation-ML papers do not
  benchmark probabilistic skill against persistence at all, so there is no
  external number to compare to.

## Consequences
- **Good:** the probabilistic ladder now has a stopping criterion: when
  efficiency against the oracle stops improving, the remaining gap is
  conditional-shape information, not model capacity.
- **Good:** the heavy-tail finding (every training ceiling below the
  Gaussian 0.2929) is quantified once and reusable by any future rung.
- **Tradeoff:** the oracle bound applies to sigma-scaled single-shape laws
  sharing the persistence center; a forecaster that improves the center or
  the sigma path is judged against a bound it could in principle exceed.
- **Cost:** each probabilistic runner computes per-fold weighted GMDs; both
  GMD identities are O(n log n), so runtime impact is negligible.

Evidence: [skill-ceiling report](../reports/2026-08-05-skill-ceiling.md);
code `vine.d2_irrigation.ceiling`.
