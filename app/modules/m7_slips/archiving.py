from time import perf_counter_ns

from app.archive import lookup, review, save
from app.manifest import hash_payload, identity, timestamp
from app.pipeline import plan_batch
from app.reasons import FabricError
from app.source import inputs


def submit(archive, source_dir, sample, kerf):
    files = inputs(source_dir, sample)
    key = identity(files, sample, kerf)
    run_id = key["id"]
    with archive.write() as db:
        current = lookup(db, run_id)
        if current:
            return current["manifest"], True
        start = perf_counter_ns()
        snapshot = plan_batch(files, kerf)
        manifest = {**key, "created_at": timestamp(), "elapsed_ms": (perf_counter_ns() - start) // 1_000_000,
                    "result_sha256": hash_payload(snapshot), "totals": snapshot["ledger"]["totals"],
                    "piece_count": len(snapshot["changeovers"]["placements"]), "used_rolls": snapshot["changeovers"]["used_rolls"]}
        save(db, {"manifest": manifest, "snapshot": snapshot})
        review(db, run_id, manifest["created_at"], "committed")
        return manifest, False


def replay(archive, source_dir, run_id):
    stored = archive.read(run_id)
    manifest = stored["manifest"]
    files = inputs(source_dir, manifest["sample"])
    if identity(files, manifest["sample"], manifest["kerf_mm"])["id"] != run_id:
        raise FabricError("STALE_RUN", 409)
    result = plan_batch(files, manifest["kerf_mm"])
    digest = manifest["result_sha256"]
    if hash_payload(result) != digest or hash_payload(stored["snapshot"]) != digest:
        raise FabricError("REPLAY_DIFF", 409)
    with archive.write() as db:
        review(db, run_id, timestamp(), "replayed")
    return manifest
