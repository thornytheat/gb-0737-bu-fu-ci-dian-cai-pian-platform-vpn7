import hashlib
import json
from datetime import UTC, datetime

from app.config import MAX_ORDERS, MAX_PIECES, MAX_ROLLS, MAX_SEGMENTS, VERSION


def canonical(content):
    return json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def hash_payload(content):
    return hashlib.sha256(canonical(content).encode("utf-8")).hexdigest()


def timestamp():
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def identity(files, sample, kerf):
    inputs = {name: item.facts() for name, item in files.items()}
    limits = {"rolls": MAX_ROLLS, "orders": MAX_ORDERS, "pieces": MAX_PIECES, "spans": MAX_SEGMENTS}
    payload = {"sample": sample, "rules": VERSION, "kerf_mm": kerf, "inputs": inputs, "limits": limits}
    return {"id": hash_payload(payload), **payload}
