
import pytest

from app.modules.m4_fit.service import fit
from app.pipeline import plan_batch
from app.reasons import FabricError


def options(data, roll):
    return next(item for item in data["fit"]["roll_options"] if item["roll"] == roll)


# TRAP-15

def test_seam_is_counted_at_both_ends_and_width_normalized(dirty):
    patterns = {row["id"]: row for row in dirty["fit"]["orders"]}
    assert (patterns["C001"]["width"], patterns["C001"]["length"], patterns["C003"]["length"]) == (1450, 620, 320)
    assert options(dirty, "R-004")["compatible"] == []


def test_segment_enumeration_covers_multiple_legal_roll_combinations(dirty):
    row = options(dirty, "R-001")
    assert (row["usable_spans"], row["options"], row["best_piece_count"]) == (2, 22, 4)
    assert row["best_by_order"] == {"C001": 2, "C004": 0, "C002": 0, "C003": 2}


# TRAP-23

def test_kerf_exact_fit_succeeds_when_right_edge_is_exclusive(dirty):
    fit_canvas = options(dirty, "R-005")
    assert fit_canvas["options"] == 2 and fit_canvas["best_piece_count"] == 1
    cut = next(row for row in dirty["changeovers"]["placements"] if row["roll"] == "R-005")
    assert (cut["start"], cut["end"], cut["kerf_end"]) == (0, 620, 625)


def test_one_more_mm_turns_exact_fit_into_shortfall(dirty_files):
    adjusted = plan_batch(dirty_files, 6)
    assert options(adjusted, "R-005")["best_piece_count"] == 0
    row = next(item for item in adjusted["changeovers"]["orders"] if item["order"] == "C004")
    assert (row["planned"], row["review"]["code"]) == (0, "SEGMENT_TOO_SHORT")


def test_aggregate_length_cannot_bridge_forbidden_gap(dirty):
    original = dirty["zones"]["rolls"][0]
    roll = {**original, "available": [{"start": 0, "end": 500}, {"start": 550, "end": 1050}]}
    sole = next(item for item in dirty["fit"]["orders"] if item["id"] == "C001")
    summary, choices = fit([roll], [sole], 5)
    assert list(choices["R-001"]) == [(0,)]
    assert summary["roll_options"][0]["best_piece_count"] == 0


def test_large_demand_has_explicit_ceiling(dirty):
    orders = [{**row, "quantity": 4} for row in dirty["fit"]["orders"]]
    with pytest.raises(FabricError) as error:
        fit(dirty["zones"]["rolls"], orders, 5)
    assert error.value.code == "PLAN_LIMIT"
