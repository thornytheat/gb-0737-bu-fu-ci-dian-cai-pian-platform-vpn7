import pytest

from app.modules.m6_ledger.partition import partition


def test_dirty_exact_balance_with_per_cut_kerf(dirty):
    totals = dirty["ledger"]["totals"]
    assert totals == {"piece": 4090, "blocked": 2932, "kerf": 40, "unused": 1563, "length": 8625, "delta": 0}
    assert totals["kerf"] == 5 * len(dirty["changeovers"]["placements"])


def test_every_axis_spans_domain_without_gaps_or_double_count(dirty):
    for entry in dirty["ledger"]["rolls"]:
        spans = entry["spans"]
        assert spans[0]["start"] == 0 and spans[-1]["end"] == entry["length"]
        assert all(a["end"] == b["start"] for a, b in zip(spans, spans[1:]))
        assert sum(item["end"] - item["start"] for item in spans) == entry["length"]


def test_source_accounts_split_rows_by_final_disposition(dirty):
    assert dirty["ledger"]["records"] == {
        "rolls": {"raw": 7, "accepted": 5, "duplicates": 1, "isolated": 1, "delta": 0},
        "orders": {"raw": 5, "accepted": 4, "duplicates": 0, "isolated": 1, "delta": 0},
        "defects": {"raw": 15, "accepted": 4, "duplicates": 1, "isolated": 10, "delta": 0},
    }


def test_clean_balance_accounts_for_nine_cuts(clean):
    assert clean["ledger"]["totals"] == {"piece": 4710, "blocked": 10, "kerf": 45, "unused": 3860, "length": 8625, "delta": 0}
    assert len(clean["changeovers"]["placements"]) == 9


def test_partition_rejects_cut_penetrating_blocked_zone(dirty):
    roll = dirty["zones"]["rolls"][0]
    invented = {"id": "bad", "order": "C001", "start": 365, "end": 985, "kerf_start": 985, "kerf_end": 995}
    with pytest.raises(RuntimeError, match="跨区"):
        partition(roll, [invented], 10)


def test_partition_rejects_missing_kerf_for_even_one_piece(dirty):
    roll = dirty["zones"]["rolls"][0]
    piece = {**dirty["changeovers"]["placements"][0]}
    piece["kerf_end"] -= 5
    with pytest.raises(RuntimeError, match="切口长度"):
        partition(roll, [piece], 5)
