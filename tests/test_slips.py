import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

from fastapi.testclient import TestClient

from app.main import build_application


def submit(client, sample="dirty", kerf=5):
    return client.post("/api/runs", json={"sample": sample, "kerf_mm": kerf})


def test_receipt_distinguishes_held_reserved_and_cut_rolls(dirty):
    slips = {item["roll"]: item for item in dirty["slips"]}
    assert [(key, slips[key]["state"], slips[key]["sequence"]) for key in ("R-001", "R-003", "R-004", "R-005")] == [
        ("R-001", "待裁", 1), ("R-003", "封存", None), ("R-004", "留存", None), ("R-005", "待裁", 3),
    ]
    assert slips["R-003"]["hold_refs"] and slips["R-003"]["pieces"] == []
    assert slips["R-005"]["pieces"][0]["kerf_end"] == 625


def test_home_to_download_proves_complete_snapshot(client):
    home = client.get("/")
    assert home.status_code == 200
    assert all(word in home.text for word in ("排版归档", "卷布轴", "打印签条", "导出卷宗"))
    assert client.get("/api/preview").json()["manifest"] is None
    write = submit(client)
    assert write.status_code == 201
    manifest = write.json()["manifest"]
    run_id = manifest["id"]
    assert manifest["piece_count"] == 8 and len(manifest["inputs"]) == 3
    download = client.get(f"/api/export/{run_id}")
    assert download.headers["content-disposition"] == f'attachment; filename="fabric-{run_id[:12]}.json"'
    document = json.loads(download.content)
    assert document == client.get(f"/api/runs/{run_id}").json()
    assert document["snapshot"]["ledger"]["totals"]["delta"] == 0
    assert document["snapshot"]["locate"]["holds"].keys() == {"R-003"}


def test_replay_recomputes_and_preserves_bytes_no_duplicate_runs(client, settings):
    manifest = submit(client).json()["manifest"]
    run_id = manifest["id"]
    before = client.get(f"/api/export/{run_id}").content
    extra = submit(client)
    assert extra.status_code == 200 and extra.json() == {"manifest": manifest, "reused": True}
    verified = client.post(f"/api/runs/{run_id}/rerun")
    assert verified.json() == {"manifest": manifest, "verified": True}
    assert client.get("/api/runs").json()["runs"] == [manifest]
    assert client.get(f"/api/export/{run_id}").content == before
    with closing(sqlite3.connect(settings.database)) as db:
        assert db.execute("SELECT action FROM reviews ORDER BY seq").fetchall() == [("committed",), ("replayed",)]


# TRAP-26

def test_stale_source_replay_is_rejected_without_rewriting_archive(client, settings):
    run_id = submit(client).json()["manifest"]["id"]
    before = client.get(f"/api/export/{run_id}").content
    path = settings.samples / "dirty-defects.csv"
    path.write_bytes(path.read_bytes() + b"\r\n")
    response = client.post(f"/api/runs/{run_id}/rerun")
    assert (response.status_code, response.json()["error"]["code"]) == (409, "STALE_RUN")
    assert client.get(f"/api/export/{run_id}").content == before
    assert submit(client).json()["manifest"]["id"] != run_id


def test_archive_remains_available_after_source_removed_and_server_restarted(client, settings):
    original = submit(client).json()["manifest"]
    run_id = original["id"]
    (settings.samples / "dirty-orders.csv").unlink()
    with TestClient(build_application(settings)) as restarted:
        assert restarted.get(f"/api/export/{run_id}").json()["manifest"] == original
        assert len(restarted.get(f"/api/slips?run_id={run_id}").json()["data"]) == 5
        bounce = restarted.post(f"/api/runs/{run_id}/rerun")
        assert (bounce.status_code, bounce.json()["error"]["code"]) == (422, "FILE_MISSING")


def test_source_failure_leaves_no_archive_or_receipt_then_reruns_successfully(client, settings):
    path = settings.samples / "dirty-orders.csv"
    original = path.read_bytes()
    path.write_bytes(original + b'"truncated\n')
    missing = submit(client)
    assert (missing.status_code, missing.json()["error"]["code"]) == (422, "CSV_SYNTAX")
    assert client.get("/api/runs").json()["runs"] == []
    path.write_bytes(original)
    assert submit(client).status_code == 201


def test_failure_of_receipt_event_rolls_back_already_inserted_archive(client, settings):
    with closing(sqlite3.connect(settings.database)) as db:
        db.executescript("""
            CREATE TRIGGER refuse BEFORE INSERT ON reviews
            BEGIN SELECT RAISE(ABORT, 'receipt storage unavailable'); END;
        """)
    with TestClient(client.app, raise_server_exceptions=False) as no_exceptions:
        assert submit(no_exceptions).status_code == 500
    assert client.get("/api/runs").json()["runs"] == []


def test_concurrent_equal_runs_use_one_transaction_result(client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: submit(client), range(4)))
    assert sorted(response.status_code for response in responses) == [200, 200, 200, 201]
    assert len({response.json()["manifest"]["id"] for response in responses}) == 1
    assert len(client.get("/api/runs").json()["runs"]) == 1


def test_archives_bind_kerf_and_invalid_kerf_cannot_sneak_through(client):
    first, second = (submit(client, kerf=kerf).json()["manifest"] for kerf in (5, 6))
    assert first["id"] != second["id"]
    assert (first["piece_count"], second["piece_count"], second["totals"]["kerf"]) == (8, 7, 42)
    for bad in (0, 21, 5.5, "5", True):
        result = submit(client, kerf=bad)
        assert (result.status_code, result.json()["error"]["code"]) == (422, "FORM_INVALID")


def test_all_seven_module_endpoints_can_run_with_fresh_database(client):
    for name in ("intake", "locate", "zones", "fit", "changeovers", "ledger", "slips"):
        reply = client.get(f"/api/{name}?sample=dirty")
        assert reply.status_code == 200
        assert reply.json()["run_id"] is None and reply.json()["data"]
    assert client.get("/api/runs").json()["runs"] == []
    failure = client.get("/api/export/missing")
    assert (failure.status_code, failure.json()["error"]["code"]) == (404, "RUN_UNKNOWN")
