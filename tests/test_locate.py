import pytest

from app.modules.m2_locate.geometry import position
from app.reasons import FabricError


def marks(dirty):
    return {item["id"]: item for item in dirty["locate"]["located"]}


def test_reverse_origin_rebases_coordinates_before_allowance(dirty):
    row = marks(dirty)["D-002"]
    assert (row["start"], row["end"], row["origin"]) == (1110, 1140, "卷尾")
    assert (row["anchor"], row["expanded"]) == ([1060, 1090], [1050, 1100])


def test_zero_length_point_at_right_edge_occupies_final_millimeter(dirty):
    row = marks(dirty)["D-003"]
    assert (row["anchor"], row["footprint"], row["expanded"]) == ([2200, 2200], [2199, 2200], [2189, 2200])


def test_zero_coordinate_point_starts_first_mm_and_clamps_safely(dirty):
    row = marks(dirty)["D-004"]
    assert (row["anchor"], row["footprint"], row["expanded"]) == ([0, 0], [0, 1], [0, 11])


def test_zero_length_span_and_nonzero_point_are_separate_errors(dirty):
    invalid = {row["id"]: row for row in dirty["locate"]["isolated"]}
    assert invalid["D-009"]["code"] == "ZERO_SPAN"
    assert invalid["D-011"]["code"] == "POINT_WIDTH"
    assert invalid["D-011"]["related"] == ["dirty-rolls.csv:4"]


def test_reversed_outside_and_unknown_coordinates_quarantine(dirty):
    invalid = {row["id"]: row for row in dirty["locate"]["isolated"]}
    assert (invalid["D-005"]["code"], invalid["D-007"]["code"], invalid["D-006"]["code"]) == (
        "COORD_DESC", "COORD_OUTSIDE", "ROLL_UNKNOWN",
    )
    assert set(dirty["locate"]["holds"]) == {"R-003"}
    assert len(dirty["locate"]["holds"]["R-003"]) == 9


def test_outside_coordinates_reject_before_allowance_clamp():
    with pytest.raises(FabricError) as error:
        position({"start": 101, "end": 101, "origin": "卷尾", "kind": "点", "margin": 10}, 100)
    assert error.value.code == "COORD_OUTSIDE"
