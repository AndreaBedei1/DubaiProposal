"""Engine-free tests for the self-contained digital-twin dashboard."""
import json

from brinewatch.visualization.dashboard import (
    build_dashboard, load_history, load_mission_card, _svg_line_chart,
)


def _write_mission(d, state="review", extra=None):
    s = {"n_samples": 400, "budget_used_m": 220.0, "budget_max_m": 260.0,
         "screening": state, "rmse_plume": 2.31, "boundary_f1": 0.78,
         "localization_error_m_vs_diffuser_centre": 4.1,
         "collisions": 0, "min_structure_clearance_m": 3.4,
         "survey_backend": "holoocean_custom (in-engine)", "localized_by_sonar": True,
         "notes": ["collision-safe nav: 2 detour(s), min clearance 3.4 m"]}
    if extra:
        s.update(extra)
    d.mkdir(parents=True, exist_ok=True)
    (d / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    return d


def test_load_mission_card_reads_summary(tmp_path):
    card = load_mission_card(_write_mission(tmp_path / "m1", "possible_exceedance"))
    assert card is not None
    assert card.screening_state == "possible_exceedance"
    labels = {k for k, _ in card.kpis}
    assert "Collisions" in labels and "Min structure clearance" in labels
    assert any("localization" in k.lower() for k in labels)


def test_load_mission_card_missing_summary_returns_none(tmp_path):
    assert load_mission_card(tmp_path / "empty") is None


def test_state_normalization_and_unknown(tmp_path):
    card = load_mission_card(_write_mission(tmp_path / "m", "CLEAR"))
    assert card.screening_state == "clear"
    card2 = load_mission_card(_write_mission(tmp_path / "m2", "banana"))
    assert card2.screening_state == "unknown"


def test_load_history(tmp_path):
    led = tmp_path / "history.jsonl"
    led.write_text("\n".join(json.dumps(r) for r in [
        {"campaign_mission": 1, "max_exceedance_psu": -1.0, "prob_exceed_max": 0.01,
         "n_cells_exceeding": 0, "screening": "clear"},
        {"campaign_mission": 2, "max_exceedance_psu": 2.0, "prob_exceed_max": 0.7,
         "n_cells_exceeding": 40, "screening": "possible_exceedance"},
    ]), encoding="utf-8")
    rows = load_history(led)
    assert len(rows) == 2 and rows[1]["screening"] == "possible_exceedance"


def test_svg_chart_handles_empty_and_data():
    assert "no data" in _svg_line_chart([], [], title="t", ylabel="y")
    svg = _svg_line_chart([1, 2, 3], [0.1, 0.5, 0.3], title="t", ylabel="y",
                          threshold=0.4)
    assert "<polyline" in svg and "threshold" in svg


def test_build_dashboard_is_self_contained(tmp_path):
    cards = [load_mission_card(_write_mission(tmp_path / "latest", "review")),
             load_mission_card(_write_mission(tmp_path / "prev", "clear"))]
    history = [
        {"campaign_mission": i, "max_exceedance_psu": i * 0.5 - 1,
         "prob_exceed_max": min(0.9, i * 0.15), "n_cells_exceeding": i * 5,
         "screening": ("clear" if i < 3 else "possible_exceedance")}
        for i in range(1, 6)]
    out = build_dashboard(cards, history, tmp_path / "dash" / "index.html",
                          site_name="Test site", generated="2026-07-21")
    doc = out.read_text(encoding="utf-8")
    # self-contained: no external hrefs/srcs
    assert "http://" not in doc and "https://" not in doc
    assert "src=\"data:image/png;base64" not in doc  # no fig files in this test
    # verdict banner + both missions + trend charts present
    assert "REVIEW" in doc
    assert "m-latest" in doc and "m-prev" in doc
    assert "Max anomaly outside mixing zone" in doc
    assert "Screening verdict per mission" in doc
    assert "simulation surrogate" in doc          # honesty footer
