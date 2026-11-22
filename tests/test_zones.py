from app.modules.m3_zones.intervals import complement, union


def roll(dirty, identifier):
    return next(row for row in dirty["zones"]["rolls"] if row["id"] == identifier)


# TRAP-19

def test_overlapping_allowances_are_counted_once(dirty):
    first = roll(dirty, "R-001")
    assert first["blocked"] == [
        {"start": 990, "end": 1100, "refs": ["dirty-defects.csv:2–3", "dirty-defects.csv:4"]},
        {"start": 2189, "end": 2200, "refs": ["dirty-defects.csv:5"]},
    ]
    assert (first["blocked_mm"], first["overlap"]) == (121, 20)


def test_available_spans_respect_holes_and_endpoints(dirty):
    assert roll(dirty, "R-001")["available"] == [{"start": 0, "end": 990}, {"start": 1100, "end": 2189}]
    assert roll(dirty, "R-002")["available"] == [{"start": 11, "end": 1800}]


def test_identified_defect_without_safe_geometry_freezes_whole_roll(dirty):
    held = roll(dirty, "R-003")
    assert held["held"] and held["available"] == []
    assert [(item["start"], item["end"]) for item in held["blocked"]] == [(0, 2800)]
    assert "dirty-defects.csv:9" in held["blocked"][0]["refs"]


def test_unmarked_roll_and_small_clean_defect_use_same_complement(clean):
    assert roll(clean, "R-001")["available"] == [{"start": 0, "end": 2200}]
    assert roll(clean, "R-004")["available"] == [{"start": 0, "end": 100}, {"start": 110, "end": 1200}]


def test_touching_and_nested_intervals_form_single_monotone_union():
    inputs = [(2, 6, "a"), (3, 4, "b"), (6, 11, "c")]
    assert union(reversed(inputs)) == ([{"start": 2, "end": 11, "refs": ["a", "b", "c"]}], 1)


def test_union_and_complement_exhaust_domain_without_zero_length_gap():
    blocked, _ = union([(0, 3, "a"), (3, 6, "b"), (6, 9, "c")])
    assert complement(9, blocked) == []
    assert complement(10, blocked) == [{"start": 9, "end": 10}]
