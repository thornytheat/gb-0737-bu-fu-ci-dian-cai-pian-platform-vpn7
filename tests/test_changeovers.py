from app.modules.m4_fit.service import fit
from app.modules.m5_changeovers.service import changeovers


def test_sample_uses_three_rolls_and_counts_real_changes(dirty):
    plan = dirty["changeovers"]
    assert (plan["roll_sequence"], plan["changes"], plan["opened_unused_mm"]) == (["R-001", "R-002", "R-005"], 2, 363)
    assert {piece["roll"] for piece in plan["placements"]} == set(plan["roll_sequence"])


def test_dirty_sample_does_not_silently_complete_held_canvas_order(dirty):
    row = next(order for order in dirty["changeovers"]["orders"] if order["order"] == "C004")
    assert (row["requested"], row["planned"], row["remaining"], row["review"]["code"]) == (2, 1, 1, "CAPACITY_USED")
    assert row["review"]["rolls"] == ["R-003", "R-005"]


def test_global_search_beats_urgent_first_largest_span_greedy(dirty):
    left, right = dirty["zones"]["rolls"][:2]
    rolls = [{**left, "length": 1070, "blocked_mm": 0, "available": [{"start": 0, "end": 1070}]},
             {**right, "length": 625, "blocked_mm": 0, "available": [{"start": 0, "end": 625}]}]
    selected = [{**order, "quantity": 1 if order["id"] == "C001" else 2} for order in dirty["fit"]["orders"]
                if order["id"] in {"C001", "C002"}]
    summary, choices = fit(rolls, selected, 5)
    plan = changeovers(rolls, summary, choices)
    assert [(piece["roll"], piece["order"]) for piece in plan["placements"]] == [
        ("R-001", "C002"), ("R-001", "C002"), ("R-002", "C001"),
    ]
    assert plan["opened_unused_mm"] == 0


def test_prioritizes_urgent_count_over_more_normal_pieces(dirty):
    sample = dirty["zones"]["rolls"][0]
    rolls = [{**sample, "length": 650, "blocked_mm": 0, "available": [{"start": 0, "end": 650}]}]
    orders = [{**o, "quantity": 1 if o["id"] == "C001" else 2} for o in dirty["fit"]["orders"] if o["id"] in {"C001", "C003"}]
    cases, candidates = fit(rolls, orders, 5)
    planned = changeovers(rolls, cases, candidates)
    assert [item["order"] for item in planned["placements"]] == ["C001"]
    assert planned["orders"][1]["remaining"] == 2


def test_minimizes_roll_count_before_remainder(clean):
    selected = [item for item in clean["fit"]["orders"] if item["id"] == "C004"]
    rolls = clean["zones"]["rolls"]
    summary, choices = fit(list(reversed(rolls)), selected, 5)
    plan = changeovers(list(reversed(rolls)), summary, choices)
    assert plan["roll_sequence"] == ["R-003"]
    assert plan["changes"] == 0 and len(plan["placements"]) == 2


def test_all_compatible_rolls_held_returns_distinct_shortfall(dirty):
    rolls = [item for item in dirty["zones"]["rolls"] if item["id"] == "R-003"]
    selected = [item for item in dirty["fit"]["orders"] if item["id"] == "C004"]
    summary, choices = fit(rolls, selected, 5)
    result = changeovers(rolls, summary, choices)
    assert result["placements"] == []
    assert result["orders"][0]["review"]["code"] == "ROLLS_HELD"
