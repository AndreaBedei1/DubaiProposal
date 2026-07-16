"""Three-state uncertainty-aware screening: CLEAR / REVIEW / POSSIBLE EXCEEDANCE.

A binary PASS/FAIL is the wrong output when the reconstructed field sits
within its own uncertainty of the regulatory threshold — the baseline audit
showed exactly that failure mode (near-margin scenarios flip verdicts run to
run). The screening states are:

- ``POSSIBLE_EXCEEDANCE``: the worst-case exceedance probability outside the
  mixing zone reaches ``cfg.p_exceed_min`` (default 0.5 — i.e. the posterior
  mean itself exceeds the threshold somewhere, or comes close with enough
  uncertainty).
- ``CLEAR``: the worst-case exceedance probability is below ``cfg.p_clear_max``
  AND the posterior std outside the zone is everywhere below
  ``cfg.max_posterior_std_psu``. A low mean alone is NOT sufficient — an
  unsurveyed area must not be labelled compliant.
- ``REVIEW``: everything in between — the mission cannot support a clear
  conclusion; the recommended action is a follow-up survey.

This is *screening*, not certification: it prioritises where accredited
monitoring should look, it does not replace it.
"""
from __future__ import annotations

import enum
import math
from dataclasses import dataclass

from ..utils.config import ComplianceConfig
from .compliance import ComplianceVerdict


class ScreeningState(enum.Enum):
    CLEAR = "CLEAR"
    REVIEW = "REVIEW"
    POSSIBLE_EXCEEDANCE = "POSSIBLE_EXCEEDANCE"


@dataclass(frozen=True)
class ScreeningResult:
    state: ScreeningState
    reason: str
    prob_exceed_max: float
    max_exceedance_psu: float
    max_std_outside_psu: float
    threshold_psu: float

    @property
    def label(self) -> str:
        return self.state.value.replace("_", " ")

    @property
    def recommended_action(self) -> str:
        return {
            ScreeningState.CLEAR: "No follow-up required from this survey.",
            ScreeningState.REVIEW: "Inconclusive - schedule a follow-up survey "
                                   "(more budget or denser sampling near the boundary).",
            ScreeningState.POSSIBLE_EXCEEDANCE: "Likely anomaly outside the mixing zone - "
                                                "escalate to accredited monitoring.",
        }[self.state]


def screen(verdict: ComplianceVerdict, cfg: ComplianceConfig) -> ScreeningResult:
    """Classify a reconstruction's compliance verdict into the three states.

    For noiseless fields (ground truth, ``max_std_outside_psu`` NaN) the
    uncertainty requirement is treated as satisfied, so the result reduces to
    the binary rule (CLEAR iff compliant).
    """
    p = float(verdict.prob_exceed_max)
    # CLEAR uses the p95 of the outside-zone posterior std (a single small
    # sampling void must not invalidate a dense survey); fall back to the max
    # for verdicts produced before p95 existed.
    std_out = float(getattr(verdict, "p95_std_outside_psu", float("nan")))
    if math.isnan(std_out):
        std_out = float(verdict.max_std_outside_psu)
    std_known = not math.isnan(std_out)
    std_ok = (std_out <= cfg.max_posterior_std_psu) if std_known else True

    if p >= cfg.p_exceed_min:
        state = ScreeningState.POSSIBLE_EXCEEDANCE
        reason = (f"worst-case exceedance probability {p:.2f} >= "
                  f"{cfg.p_exceed_min:.2f} outside the mixing zone")
    elif p <= cfg.p_clear_max and std_ok:
        state = ScreeningState.CLEAR
        reason = (f"exceedance probability {p:.2f} <= {cfg.p_clear_max:.2f} and "
                  + (f"posterior std outside the zone {std_out:.2f} <= "
                     f"{cfg.max_posterior_std_psu:.2f} PSU" if std_known
                     else "field is noiseless (ground truth)"))
    else:
        state = ScreeningState.REVIEW
        if p > cfg.p_clear_max:
            reason = (f"exceedance probability {p:.2f} between the CLEAR bound "
                      f"{cfg.p_clear_max:.2f} and the exceedance bound {cfg.p_exceed_min:.2f}")
        else:
            reason = (f"posterior std outside the zone {std_out:.2f} PSU exceeds "
                      f"{cfg.max_posterior_std_psu:.2f} PSU - unsurveyed area cannot "
                      "be declared clear")
    return ScreeningResult(
        state=state,
        reason=reason,
        prob_exceed_max=p,
        max_exceedance_psu=float(verdict.max_exceedance_psu),
        max_std_outside_psu=std_out,
        threshold_psu=float(verdict.threshold_psu),
    )


def screening_outcome(result: ScreeningResult, gt_compliant: bool) -> str:
    """Score a screening result against the binary ground truth.

    Returns "correct" (conclusive and right), "wrong" (conclusive and wrong)
    or "inconclusive" (REVIEW). Benchmarks report all three fractions —
    REVIEW is the honest option at fine margins, not an error.
    """
    if result.state is ScreeningState.REVIEW:
        return "inconclusive"
    conclusive_clear = result.state is ScreeningState.CLEAR
    return "correct" if conclusive_clear == bool(gt_compliant) else "wrong"
