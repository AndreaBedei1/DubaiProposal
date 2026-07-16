"""Tests for the three-state uncertainty-aware screening."""
from __future__ import annotations

import math

import pytest

from brinewatch.evaluation.compliance import ComplianceVerdict
from brinewatch.evaluation.screening import (
    ScreeningState,
    screen,
    screening_outcome,
)
from brinewatch.utils.config import ComplianceConfig


def _verdict(prob: float, std_out: float, compliant: bool = True,
             exceed: float = -0.5) -> ComplianceVerdict:
    return ComplianceVerdict(
        compliant=compliant, threshold_psu=41.65, max_exceedance_psu=exceed,
        worst_point=(10.0, 0.0), prob_exceed_max=prob, n_cells_exceeding=0,
        mixing_zone_radius_m=40.0, max_std_outside_psu=std_out,
    )


@pytest.fixture()
def cfg() -> ComplianceConfig:
    return ComplianceConfig()  # p_exceed_min=0.5, p_clear_max=0.1, max_std=0.75


def test_possible_exceedance_on_high_probability(cfg):
    res = screen(_verdict(prob=0.62, std_out=0.4, compliant=False, exceed=0.3), cfg)
    assert res.state is ScreeningState.POSSIBLE_EXCEEDANCE
    assert "0.62" in res.reason


def test_clear_requires_low_prob_and_low_uncertainty(cfg):
    res = screen(_verdict(prob=0.05, std_out=0.4), cfg)
    assert res.state is ScreeningState.CLEAR


def test_low_mean_but_high_uncertainty_is_review_not_clear(cfg):
    """The key honesty rule: an unsurveyed area must not be declared clear."""
    res = screen(_verdict(prob=0.05, std_out=2.2), cfg)
    assert res.state is ScreeningState.REVIEW
    assert "std" in res.reason


def test_intermediate_probability_is_review(cfg):
    res = screen(_verdict(prob=0.34, std_out=0.3), cfg)
    assert res.state is ScreeningState.REVIEW


def test_boundaries_are_inclusive_exclusive(cfg):
    assert screen(_verdict(prob=0.50, std_out=0.3), cfg).state \
        is ScreeningState.POSSIBLE_EXCEEDANCE
    assert screen(_verdict(prob=0.10, std_out=0.3), cfg).state is ScreeningState.CLEAR
    assert screen(_verdict(prob=0.101, std_out=0.3), cfg).state is ScreeningState.REVIEW


def test_ground_truth_nan_std_reduces_to_binary(cfg):
    gt_fail = _verdict(prob=1.0, std_out=float("nan"), compliant=False, exceed=0.4)
    gt_pass = _verdict(prob=0.0, std_out=float("nan"), compliant=True)
    assert screen(gt_fail, cfg).state is ScreeningState.POSSIBLE_EXCEEDANCE
    assert screen(gt_pass, cfg).state is ScreeningState.CLEAR


def test_outcome_scoring(cfg):
    clear = screen(_verdict(prob=0.05, std_out=0.3), cfg)
    review = screen(_verdict(prob=0.3, std_out=0.3), cfg)
    exceed = screen(_verdict(prob=0.9, std_out=0.3, compliant=False, exceed=1.0), cfg)
    assert screening_outcome(clear, gt_compliant=True) == "correct"
    assert screening_outcome(clear, gt_compliant=False) == "wrong"
    assert screening_outcome(review, gt_compliant=False) == "inconclusive"
    assert screening_outcome(exceed, gt_compliant=False) == "correct"
    assert screening_outcome(exceed, gt_compliant=True) == "wrong"


def test_result_metadata(cfg):
    res = screen(_verdict(prob=0.05, std_out=0.3), cfg)
    assert res.label == "CLEAR"
    assert "follow-up" in res.recommended_action.lower() or \
           "no follow-up" in res.recommended_action.lower()
    assert not math.isnan(res.threshold_psu)
