import json
from contextlib import closing

from app.archive import lookup
from app.manifest import hash_payload, timestamp
from app.modules.m8_resume.planning import accept, build_sheet, derive, layout
from app.reasons import FabricError

MAX_RECEIPT_TEXT = 80
MAX_CUTS = 200
MAX_RECEIPTS = 2000


def preview(snapshot, version=0):
    document = {"manifest": {"id": "preview", "result_sha256": hash_payload(snapshot)}, "snapshot": snapshot}
    return {**build_sheet(document, [], [], version, timestamp()), "latest_version": version,
            "stored_versions": 0, "replayed": False}


def events(db, run_id):
    rows = db.execute("SELECT receipt, time, body FROM resume_receipts WHERE run=? ORDER BY seq", (run_id,)).fetchall()
    result = []
    for row in rows:
        body = json.loads(row["body"])
        for event in body["events"]:
            result.append({"seq": len(result), "receipt": row["receipt"], "time": row["time"],
                           "roll": body["roll"], "cut": event["cut"], "kind": event["kind"],
                           "piece": event["piece"]})
    return result


def stored_versions(db, run_id):
    return [{"version": row["version"], "time": row["time"], "document": json.loads(row["document"])}
            for row in db.execute("SELECT version, time, document FROM resume_versions WHERE run=? ORDER BY version",
                                  (run_id,))]


def stored_receipts(db, run_id):
    return [{"receipt": row["receipt"], "time": row["time"], **json.loads(row["body"])}
            for row in db.execute("SELECT receipt, time, body FROM resume_receipts WHERE run=? ORDER BY seq",
                                  (run_id,))]


def current(document, db, run_id):
    """当前续裁确认单：取最后已存版本；没有回执时按第 0 版即席生成。"""
    stored = stored_versions(db, run_id)
    recorded = stored_receipts(db, run_id)
    if stored:
        latest = stored[-1]
        return {**latest["document"], "latest_version": latest["version"], "stored_versions": len(stored),
                "receipts": recorded, "replayed": False}
    return {**build_sheet(document, [], recorded, 0, document["manifest"]["created_at"]),
            "latest_version": 0, "stored_versions": 0, "replayed": False}


def sheet(archive, run_id):
    document = archive.read(run_id)
    with closing(archive.connect()) as db:
        return current(document, db, run_id)


def history(archive, run_id):
    """旧版签条只读清单；已存版本只增不删。"""
    archive.read(run_id)
    with closing(archive.connect()) as db:
        stored = stored_versions(db, run_id)
        recorded = stored_receipts(db, run_id)
    return {"run_id": run_id,
            "latest_version": stored[-1]["version"] if stored else 0,
            "versions": [{"version": item["version"], "time": item["time"],
                          "receipt_count": len(item["document"].get("receipts", [])),
                          "totals": item["document"].get("totals"),
                          "release": item["document"].get("release")} for item in stored],
            "receipts": recorded}


def version(archive, run_id, number):
    archive.read(run_id)
    with closing(archive.connect()) as db:
        row = db.execute("SELECT version, time, document FROM resume_versions WHERE run=? AND version=?",
                         (run_id, number)).fetchone()
    if row is None:
        raise FabricError("RESUME_VERSION_UNKNOWN", 404)
    return {"run_id": run_id, "version": row["version"], "time": row["time"],
            "document": json.loads(row["document"])}


def _normalize(payload):
    receipt = payload.get("receipt_id", "")
    if not isinstance(receipt, str):
        raise FabricError("BAD_VALUE")
    receipt = receipt.strip()
    if not receipt or len(receipt) > MAX_RECEIPT_TEXT:
        raise FabricError("BAD_VALUE")
    roll = payload.get("roll")
    if not isinstance(roll, str) or not roll.strip():
        raise FabricError("BAD_VALUE")
    cuts = payload.get("cuts")
    if cuts is None:
        cut = payload.get("cut_mm")
        cuts = [] if cut is None else [cut]
    if not isinstance(cuts, list) or not cuts or len(cuts) > MAX_CUTS:
        raise FabricError("BAD_VALUE")
    if any(not isinstance(cut, int) or isinstance(cut, bool) or cut < 1 for cut in cuts):
        raise FabricError("BAD_VALUE")
    if any(later <= earlier for earlier, later in zip(cuts, cuts[1:])):
        raise FabricError("BAD_VALUE")
    return {"receipt_id": receipt, "roll": roll.strip(), "cuts": cuts}


def _scope(document, recorded, roll_id):
    zones, by_roll = layout(document["snapshot"])
    roll = next((item for item in zones if item["id"] == roll_id), None)
    if roll is None:
        raise FabricError("CUT_UNPLANNED")
    pieces = by_roll.get(roll_id, [])
    scoped = [event for event in recorded if event["roll"] == roll_id]
    return roll, pieces, scoped


def submit(archive, run_id, payload):
    """登记一条落刀回执；同一回执重试只回放，不新增裁片、刀口或签条版本。"""
    document = archive.read(run_id)
    body = _normalize(payload)
    with archive.write() as db:
        if lookup(db, run_id) is None:
            raise FabricError("RUN_UNKNOWN", 404)
        previous = db.execute("SELECT body FROM resume_receipts WHERE run=? AND receipt=?",
                              (run_id, body["receipt_id"])).fetchone()
        if previous is not None:
            stored = json.loads(previous["body"])
            if {"roll": stored["roll"], "cuts": stored["cuts"]} != {"roll": body["roll"], "cuts": body["cuts"]}:
                raise FabricError("RECEIPT_CONFLICT", 409)
            return {**current(document, db, run_id), "replayed": True}
        count = db.execute("SELECT COUNT(*) FROM resume_receipts WHERE run=?", (run_id,)).fetchone()[0]
        if count >= MAX_RECEIPTS:
            raise FabricError("RECEIPT_LIMIT", 409)
        recorded = events(db, run_id)
        roll, pieces, scoped = _scope(document, recorded, body["roll"])
        states = derive(pieces, scoped)
        last_cut = max((event["cut"] for event in scoped), default=None)
        drafts = []
        for cut in body["cuts"]:
            draft, index, kind = accept(cut, roll, pieces, states, last_cut)
            drafts.append(draft)
            # 同一条回执里的先后刀口先按草稿顺序推进，后面一刀才能接着校验。
            trial = scoped + [{**item, "seq": len(recorded) + position, "receipt": body["receipt_id"],
                               "roll": body["roll"], "time": None} for position, item in enumerate(drafts)]
            states = derive(pieces, trial)
            last_cut = cut
        now = timestamp()
        versions = stored_versions(db, run_id)
        if not versions:  # 第一次登记时先把“未落刀”的原样确认单存成第 0 版，旧签条可回看
            original = build_sheet(document, [], [], 0, document["manifest"]["created_at"])
            db.execute("INSERT INTO resume_versions (run, version, time, document) VALUES (?,?,?,?)",
                       (run_id, 0, document["manifest"]["created_at"],
                        json.dumps(original, sort_keys=True, ensure_ascii=False)))
            versions = stored_versions(db, run_id)
        db.execute("INSERT INTO resume_receipts (run, receipt, time, body) VALUES (?,?,?,?)",
                   (run_id, body["receipt_id"], now,
                    json.dumps({"roll": body["roll"], "cuts": body["cuts"], "events": drafts},
                               sort_keys=True, ensure_ascii=False)))
        number = versions[-1]["version"] + 1
        result = build_sheet(document, events(db, run_id), stored_receipts(db, run_id), number, now)
        db.execute("INSERT INTO resume_versions (run, version, time, document) VALUES (?,?,?,?)",
                   (run_id, number, now, json.dumps(result, sort_keys=True, ensure_ascii=False)))
        return {**result, "latest_version": number, "stored_versions": len(versions) + 1, "replayed": False}
