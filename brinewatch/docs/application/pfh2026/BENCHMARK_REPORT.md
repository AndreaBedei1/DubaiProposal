# Planner benchmark report — PFH 2026 evidence

All numbers below come from the **held-out evaluation seed set (100–119,
20 seeds per planner per family)** on the kinematic backend; the adaptive
planner's weights were chosen earlier on development seeds (0–4) and were
not tuned on these seeds. Equal total travel budget (1600 m); LOCATE and
BASELINE phases identical; strategies differ only in SURVEY. Metrics are
computed at budget checkpoints by refitting a fresh GP on only the samples
collected within that budget.

Raw records: `outputs/brinewatch_benchmark_static_*/benchmark_records.csv`
and `outputs/brinewatch_benchmark_dynamic_*/benchmark_records.csv` (copied
under `docs/application/pfh2026/assets/results/`).

## Family A — static primary benchmark (tide frozen)

The ground truth is constant during sampling and evaluation: the cleanest
measurement of the sampling strategy itself.

| Budget | RMSE in plume (PSU) — lawnmower | — adaptive | Boundary F1 — lawnmower | — adaptive |
|---|---|---|---|---|
| 25 % (400 m) | 1.26 ± 0.37 | **1.12 ± 0.45** | 0.57 | 0.57 |
| 50 % (800 m) | 1.18 ± 0.34 | **1.00 ± 0.42** | 0.60 | **0.70** |
| 75 % (1200 m) | **0.59 ± 0.11** | 0.65 ± 0.20 | 0.67 | **0.71** |
| 100 % (1600 m) | **0.38 ± 0.06** | 0.50 ± 0.08 | **0.79** | 0.74 |

Screening outcomes (three-state, fraction of seeds):

| Budget | lawnmower correct/inconclusive/wrong | adaptive correct/inconclusive/wrong |
|---|---|---|
| 25 % | 0.80 / 0.20 / **0.00** | 0.90 / 0.10 / **0.00** |
| 50 % | 0.75 / 0.25 / **0.00** | 0.60 / 0.40 / **0.00** |
| 75 % | 0.90 / 0.10 / **0.00** | 0.50 / 0.50 / **0.00** |
| 100 % | 0.85 / 0.15 / **0.00** | 0.40 / 0.60 / **0.00** |

## Family B — dynamic stress test (tidal advection ±2.5 m, period 2400 s)

Same protocol with the plume pattern oscillating while it is sampled;
reconstruction scored against the t=0 field. Full-budget RMSE degrades by
~+1 % (lawnmower, 0.383 vs 0.381) and ~+12 % (adaptive, 0.557 vs 0.498)
relative to Family A; adaptive's mid-budget advantage persists
(RMSE 0.92 vs 1.26 at 50 %; F1 0.69 vs 0.57). A spatio-temporal GP kernel
is the documented next step for strongly tidal sites.

## Honest interpretation

1. **The three-state screening never produced a wrong conclusive result** —
   0 of 320 planner-seed-checkpoint evaluations across both families. Where
   the legacy binary verdict flipped at the fine exceedance margin of this
   scenario, the screening correctly answered REVIEW instead. This is the
   central claim the benchmark supports.
2. **Adaptive sampling is most useful when the available survey distance is
   insufficient to densely cover the whole area**: at 25–50 % budget it cuts
   plume RMSE by ~11–15 % and improves boundary F1 by up to +17 % (0.70 vs
   0.60 at half budget, static family). Once 1600 m suffices for full 10 m
   line-spacing coverage, the lawnmower matches or beats it — as expected,
   and reported as such.
3. **Trade-off discovered**: the boundary-focused adaptive planner leaves
   more residual posterior uncertainty in far-field areas, so it ends in
   REVIEW more often at high budgets (uniform coverage reaches CLEAR more
   often). Sharper boundaries vs more conclusive screening is a real
   operational choice; both behaviours are correct under their objectives.
4. Coverage: adaptive 0.90 vs lawnmower 0.80 at full budget (fraction of
   grid within 8 m of a sample) — adaptive spreads transit segments while
   concentrating dwell near the boundary.

Figures: `assets/results/learning_curves_static.png`,
`assets/results/learning_curves_dynamic.png` (RMSE / F1 / coverage vs
budget, mean ±1σ over 20 seeds).
