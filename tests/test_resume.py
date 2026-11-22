import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import build_application
from app.modules.m8_resume.planning import accept, build_sheet, derive, layout, span_of
from app.pipeline import plan_batch
from app.source import inputs


def archive(client):
    return client.post("/api/runs", json={"sample": "dirty", "kerf_mm": 5}).json()["manifest"]["id"]


def cut(client, run_id, receipt, roll, cuts):
    return client.post(f"/api/resume/{run_id}/receipts",
                       json={"receipt_id": receipt, "roll": roll, "cuts": cuts})


def sheet(client, run_id):
    response = client.get(f"/api/resume/{run_id}")
    assert response.status_code == 200
    return response.json()


def row(document, roll):
    return next(item for item in document["rolls"] if item["roll"] == roll)


@pytest.fixture
def dirty_snapshot(dirty_files):
    return plan_batch(dirty_files, 5)


def snapshot_sheet(snapshot, events=()):
    document = {"manifest": {"id": "preview", "result_sha256": "x", "created_at": "t"}, "snapshot": snapshot}
    return build_sheet(document, list(events), [], len(events), "t")


# 初始确认单

def test_unstarted_sheet_lists_every_piece_as_pending_and_names_first_cut(dirty):
    document = snapshot_sheet(dirty)
    assert document["totals"] == {"planned": 8, "completed": 0, "kerf_open": 0, "scrapped": 0, "pending": 8}
    first = row(document, "R-001")
    assert first["state"] == "待裁" and first["release"]["ready"] is False
    assert first["resume"]["kind"] == "piece" and first["resume"]["next_cut_mm"] == 535
    assert row(document, "R-003")["state"] == "封存"
    assert row(document, "R-004")["state"] == "留存"
    assert row(document, "R-004")["release"] == {"ready": True, "unused_mm": 1200, "reasons": []}


def test_preview_route_is_available_without_archive(client):
    response = client.get("/api/resume?sample=dirty")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "preview" and body["version"] == 0 and body["totals"]["planned"] == 8
    assert client.get("/api/runs").json()["runs"] == []


# 回执幂等

def test_same_receipt_replayed_does_not_add_pieces_kerfs_or_versions(client):
    run_id = archive(client)
    first = cut(client, run_id, "夜班-001", "R-001", [535, 860])
    assert first.status_code == 201
    assert first.json()["totals"]["completed"] == 2
    version = first.json()["version"]
    retry = cut(client, run_id, "夜班-001", "R-001", [535, 860])
    assert retry.status_code == 200 and retry.json()["replayed"] is True
    assert retry.json()["version"] == version
    assert retry.json()["totals"] == first.json()["totals"]
    assert len(retry.json()["receipts"]) == 1
    history = client.get(f"/api/resume/{run_id}/history").json()
    assert [item["version"] for item in history["versions"]] == [0, 1]
    assert history["versions"][1]["receipt_count"] == 1


def test_same_receipt_with_different_cuts_is_rejected_and_keeps_old_version(client):
    run_id = archive(client)
    original = cut(client, run_id, "夜班-001", "R-001", [535, 860]).json()
    before = client.get(f"/api/resume/{run_id}").json()
    conflict = cut(client, run_id, "夜班-001", "R-001", [860])
    assert (conflict.status_code, conflict.json()["error"]["code"]) == (409, "RECEIPT_CONFLICT")
    after = client.get(f"/api/resume/{run_id}").json()
    assert after["version"] == before["version"] == original["version"]
    assert after["totals"] == before["totals"]
    assert len(after["receipts"]) == 1
    old = client.get(f"/api/resume/{run_id}/versions/{original['version']}")
    assert old.status_code == 200 and old.json()["document"]["totals"] == original["totals"]


def test_duplicate_cut_in_new_receipt_is_refused_without_new_version(client):
    run_id = archive(client)
    cut(client, run_id, "夜班-001", "R-001", [535])
    duplicate = cut(client, run_id, "夜班-002", "R-001", [535])
    assert (duplicate.status_code, duplicate.json()["error"]["code"]) == (409, "CUT_DUPLICATE")
    history = client.get(f"/api/resume/{run_id}/history").json()
    assert [item["version"] for item in history["versions"]] == [0, 1]
    assert len(client.get(f"/api/resume/{run_id}").json()["receipts"]) == 1


# 半片与刀口未闭合

def test_cut_inside_piece_body_scraps_whole_piece_instead_of_counting_it_complete(client, dirty):
    run_id = archive(client)
    cut(client, run_id, "夜班-001", "R-001", [535, 860])
    half = cut(client, run_id, "夜班-002", "R-001", [1300]).json()
    roll = row(half, "R-001")
    assert roll["state"] == "中断待决"
    assert [item["piece"] for item in roll["completed"]] == ["C002/01", "C003/01"]
    assert [item["piece"] for item in roll["interrupted"]] == ["C002/02"]
    assert roll["interrupted"][0]["cut_mm"] == 1300 and roll["interrupted"][0]["discarded_mm"] == 200
    assert roll["release"]["ready"] is False and "SCRAPPED" in roll["release"]["reasons"]
    amounts = roll["reconciliation"]["amounts"]
    assert amounts["written_off_mm"] == 535 and amounts["delta"] == 0
    assert half["totals"]["completed"] == 2 and half["totals"]["scrapped"] == 1
    # 下一刀先在片首重建前缘，不能直接跳到下一片刀口终点
    assert roll["resume"]["kind"] == "realign" and roll["resume"]["next_cut_mm"] == 1635


def test_jumping_to_next_piece_kerf_after_scrap_is_refused_until_front_edge_is_cut(client):
    run_id = archive(client)
    cut(client, run_id, "夜班-001", "R-001", [535, 860, 1300])
    skip = cut(client, run_id, "夜班-002", "R-001", [1960])
    assert (skip.status_code, skip.json()["error"]["code"]) == (409, "CUT_EDGE")
    assert "重建前缘" in skip.json()["error"]["message"]
    assert cut(client, run_id, "夜班-003", "R-001", [1635]).status_code == 201
    finished = cut(client, run_id, "夜班-004", "R-001", [1960]).json()
    roll = row(finished, "R-001")
    assert roll["state"] == "中断待决" and roll["pending"] == []
    assert roll["reconciliation"]["amounts"]["written_off_mm"] == 535
    assert roll["release"]["ready"] is False and roll["release"]["reasons"] == ["SCRAPPED"]


def test_cut_between_piece_end_and_kerf_end_leaves_kerf_open_and_blocks_release(client):
    run_id = archive(client)
    half = cut(client, run_id, "夜班-001", "R-001", [535, 860, 1633]).json()
    roll = row(half, "R-001")
    assert roll["state"] == "续裁中"
    assert [item["piece"] for item in roll["kerf_open"]] == ["C002/02"]
    assert roll["kerf_open"][0]["cut_mm"] == 1633 and roll["kerf_open"][0]["open_kerf_mm"] == 2
    assert [item["piece"] for item in roll["completed"]] == ["C002/01", "C003/01"]
    assert roll["release"]["ready"] is False and "KERF_OPEN" in roll["release"]["reasons"]
    assert roll["resume"]["kind"] == "kerf_finish" and roll["resume"]["next_cut_mm"] == 1635
    closed = cut(client, run_id, "夜班-002", "R-001", [1635]).json()
    roll = row(closed, "R-001")
    assert [item["piece"] for item in roll["completed"]] == ["C002/01", "C003/01", "C002/02"]
    assert roll["kerf_open"] == [] and roll["release"]["reasons"] == ["PENDING"]
    assert roll["reconciliation"]["amounts"]["kerf_mm"] == 15


def test_kerf_band_cut_after_scrap_still_requires_front_edge(client):
    run_id = archive(client)
    assert cut(client, run_id, "夜班-001", "R-001", [535, 860, 1300]).status_code == 201
    # 半片作废后前缘停在 1300，下一片片首 1635 未对齐；直接切它的刀口带仍是超长条
    jumped = cut(client, run_id, "夜班-002", "R-001", [1958])
    assert (jumped.status_code, jumped.json()["error"]["code"]) == (409, "CUT_EDGE")
    # 先在片首 1635 重建前缘，才能按片长落刀到 1960
    assert cut(client, run_id, "夜班-003", "R-001", [1635]).status_code == 201
    finished = cut(client, run_id, "夜班-004", "R-001", [1960]).json()
    assert [item["piece"] for item in row(finished, "R-001")["completed"]] == [
        "C002/01", "C003/01", "C003/02"]


# 刀口与禁切区对平

def test_all_kerfs_closed_releases_exactly_the_unused_remainder(client, dirty):
    run_id = archive(client)
    for receipt, cuts in (("夜班-001", [535, 860]), ("夜班-002", [1635, 1960])):
        assert cut(client, run_id, receipt, "R-001", cuts).status_code == 201
    document = sheet(client, run_id)
    roll = row(document, "R-001")
    assert roll["state"] == "已完成" and roll["release"]["ready"] is True
    assert roll["release"]["unused_mm"] == roll["reconciliation"]["amounts"]["unused_mm"] == 359
    assert roll["resume"] is None and roll["reconciliation"]["balanced"] is True
    assert roll["reconciliation"]["amounts"]["delta"] == 0
    for receipt, cuts in (("夜班-003", [636, 1261, 1796]), ("夜班-004", [625])):
        roll_id = "R-002" if receipt == "夜班-003" else "R-005"
        assert cut(client, run_id, receipt, roll_id, cuts).status_code == 201
    final = sheet(client, run_id)
    assert final["release"]["release_ready_rolls"] == ["R-001", "R-002", "R-004", "R-005"]
    assert final["release"]["waiting_rolls"] == [] and final["release"]["sealed_rolls"] == ["R-003"]
    assert final["release"]["ready"] is True
    assert final["totals"] == {"planned": 8, "completed": 8, "kerf_open": 0, "scrapped": 0, "pending": 0}


def test_held_roll_never_releases_and_blocks_batch_release(client):
    run_id = archive(client)
    held = cut(client, run_id, "夜班-001", "R-003", [100])
    assert (held.status_code, held.json()["error"]["code"]) == (422, "CUT_BLOCKED")
    document = sheet(client, run_id)
    roll = row(document, "R-003")
    assert roll["state"] == "封存" and roll["release"] == {"ready": False, "unused_mm": 0, "reasons": ["HELD"]}
    assert document["release"]["ready"] is False and document["release"]["sealed_rolls"] == ["R-003"]


# 落刀位置校验

def test_out_of_range_and_forbidden_cuts_are_rejected(client):
    run_id = archive(client)
    cases = [([9999], 422, "CUT_OUTSIDE"), ([1000], 422, "CUT_BLOCKED"), ([990], 422, "CUT_UNPLANNED")]
    for cuts, status, code in cases:
        response = cut(client, run_id, f"bad-{cuts[0]}", "R-001", cuts)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    assert sheet(client, run_id)["version"] == 0


def test_receipt_requires_positive_monotonic_integer_cuts(client):
    run_id = archive(client)
    for body in ({"receipt_id": "", "roll": "R-001", "cuts": [535]},
                 {"receipt_id": "x", "roll": "", "cuts": [535]},
                 {"receipt_id": "x", "roll": "R-001", "cuts": []},
                 {"receipt_id": "x", "roll": "R-001", "cuts": [535, 535]},
                 {"receipt_id": "x", "roll": "R-001", "cuts": [860, 535]},
                 {"receipt_id": "x", "roll": "R-001", "cuts": [0]}):
        response = client.post(f"/api/resume/{run_id}/receipts", json=body)
        assert response.status_code == 422, body
    assert sheet(client, run_id)["version"] == 0


def test_unknown_run_and_version_are_not_found(client):
    run_id = archive(client)
    assert client.get("/api/resume/missing").status_code == 404
    assert cut(client, "missing", "x", "R-001", [535]).status_code == 404
    assert client.get(f"/api/resume/{run_id}/versions/9").status_code == 404


def test_receipt_with_a_bad_cut_anywhere_writes_nothing(client):
    run_id = archive(client)
    failed = cut(client, run_id, "夜班-001", "R-001", [535, 9999])
    assert (failed.status_code, failed.json()["error"]["code"]) == (422, "CUT_OUTSIDE")
    document = sheet(client, run_id)
    assert document["version"] == 0 and document["receipts"] == []
    assert row(document, "R-001")["completed"] == []
    assert cut(client, run_id, "夜班-001", "R-001", [535, 860]).status_code == 201


# 旧版签条与只追加

def test_failed_recovery_keeps_previous_version_and_receipts(client):
    run_id = archive(client)
    cut(client, run_id, "夜班-001", "R-001", [535])
    before = sheet(client, run_id)
    for receipt, cuts, status in (("夜班-001", [860], 409), ("夜班-002", [535], 409), ("夜班-003", [9999], 422)):
        assert cut(client, run_id, receipt, "R-001", cuts).status_code == status
    after = sheet(client, run_id)
    assert after["version"] == before["version"] == 1
    assert after["totals"] == before["totals"]
    assert [item["receipt"] for item in after["receipts"]] == ["夜班-001"]
    assert client.get(f"/api/resume/{run_id}/versions/1").json()["document"]["totals"] == before["totals"]


def test_versions_are_append_only_and_readable_after_restart(client, settings):
    run_id = archive(client)
    cut(client, run_id, "夜班-001", "R-001", [535])
    cut(client, run_id, "夜班-002", "R-001", [860])
    history = client.get(f"/api/resume/{run_id}/history").json()
    assert [(item["version"], item["receipt_count"]) for item in history["versions"]] == [(0, 0), (1, 1), (2, 2)]
    first = client.get(f"/api/resume/{run_id}/versions/0").json()["document"]
    with TestClient(build_application(settings)) as restarted:
        assert restarted.get(f"/api/resume/{run_id}/versions/0").json()["document"] == first
        assert [item["version"] for item in restarted.get(f"/api/resume/{run_id}/history").json()["versions"]] == [0, 1, 2]
    with closing(sqlite3.connect(settings.database)) as db:
        rows = db.execute("SELECT version FROM resume_versions WHERE run=? ORDER BY version", (run_id,)).fetchall()
    assert rows == [(0,), (1,), (2,)]


def test_receipts_are_scoped_per_roll(client):
    run_id = archive(client)
    assert cut(client, run_id, "夜班-001", "R-001", [535]).status_code == 201
    moved = cut(client, run_id, "夜班-001", "R-002", [636])
    assert (moved.status_code, moved.json()["error"]["code"]) == (409, "RECEIPT_CONFLICT")


def test_concurrent_identical_receipts_record_one_receipt(client):
    from concurrent.futures import ThreadPoolExecutor
    run_id = archive(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(
            lambda _: cut(client, run_id, "夜班-001", "R-001", [535, 860]), range(4)))
    assert sorted(response.status_code for response in responses) == [200, 200, 200, 201]
    document = sheet(client, run_id)
    assert len(document["receipts"]) == 1 and document["totals"]["completed"] == 2
    history = client.get(f"/api/resume/{run_id}/history").json()
    assert [(item["version"], item["receipt_count"]) for item in history["versions"]] == [(0, 0), (1, 1)]


# 归档不受影响

def test_resume_does_not_rewrite_archived_document_or_slip(client):
    run_id = archive(client)
    before = client.get(f"/api/export/{run_id}").content
    cut(client, run_id, "夜班-001", "R-001", [535, 860])
    cut(client, run_id, "夜班-002", "R-001", [1300])
    assert client.get(f"/api/export/{run_id}").content == before
    slips = client.get(f"/api/slips?run_id={run_id}").json()["data"]
    assert {item["roll"]: item["state"] for item in slips}["R-001"] == "待裁"
    assert len(next(item for item in slips if item["roll"] == "R-001")["pieces"]) == 4


# 纯函数边界

def test_derive_replays_only_appended_events(dirty):
    zones, by_roll = layout(dirty)
    roll, pieces = next(item for item in zones if item["id"] == "R-001"), by_roll["R-001"]
    events, states = [], derive(pieces, [])
    for sequence, position in ((0, 535), (1, 860)):
        draft, _, _ = accept(position, roll, pieces, states, events[-1]["cut"] if events else None)
        events.append({**draft, "seq": sequence, "receipt": "r", "roll": "R-001", "time": None})
        states = derive(pieces, events)
    assert [state["status"] for state in states] == ["complete", "complete", "pending", "pending"]
    # 同一批事件以任意顺序重新推导结果一致（按 seq 排序）
    assert derive(pieces, list(reversed(events))) == states


def test_second_available_span_starts_at_a_natural_edge(dirty):
    zones, by_roll = layout(dirty)
    roll, pieces = next(item for item in zones if item["id"] == "R-001"), by_roll["R-001"]
    events = []
    for sequence, cut in ((0, 535), (1, 860)):
        draft, _, _ = accept(cut, roll, pieces, derive(pieces, events),
                             events[-1]["cut"] if events else None)
        events.append({**draft, "seq": sequence, "receipt": "r", "roll": "R-001", "time": None})
    states = derive(pieces, events)
    assert [state["status"] for state in states] == ["complete", "complete", "pending", "pending"]
    # 第二段从禁切区结束处 1100 起算，是天然前缘，不需要额外空走齐刀
    assert span_of(roll, pieces[2]) == {"start": 1100, "end": 2189}
    assert pieces[2]["start"] == 1100
    draft, index, hit = accept(1635, roll, pieces, states, 860)
    assert (draft["kind"], index, hit) == ("complete", 2, "hit_complete")
    # 第一段里停在 990 的刀远在第二段段首之前，依然算天然前缘
    assert roll["available"][1] == {"start": 1100, "end": 2189}
