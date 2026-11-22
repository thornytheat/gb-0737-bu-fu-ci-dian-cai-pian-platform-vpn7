import json
import sqlite3
from contextlib import closing, contextmanager

from app.manifest import canonical
from app.reasons import FabricError


class Archive:
    def __init__(self, path):
        self.path = path

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def setup(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, time TEXT NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews (
                    seq INTEGER PRIMARY KEY, run TEXT REFERENCES runs(id) NOT NULL, time TEXT NOT NULL, action TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS recent_runs ON runs(time DESC, id DESC);
            """)

    @contextmanager
    def write(self):
        try:
            with closing(self.connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        except sqlite3.OperationalError as exc:
            if (getattr(exc, "sqlite_errorcode", 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise FabricError("STORE_BUSY", 503) from exc
            raise

    def read(self, run_id):
        with closing(self.connect()) as db:
            document = lookup(db, run_id)
        if document is None:
            raise FabricError("RUN_UNKNOWN", 404)
        return document

    def recent(self):
        with closing(self.connect()) as db:
            return [json.loads(row["manifest"]) for row in db.execute(
                "SELECT json_extract(document, '$.manifest') AS manifest FROM runs ORDER BY time DESC,id DESC LIMIT 30",
            )]


def lookup(db, run_id):
    row = db.execute("SELECT document FROM runs WHERE id=?", (run_id,)).fetchone()
    return json.loads(row["document"]) if row else None


def save(db, document):
    manifest = document["manifest"]
    db.execute("INSERT INTO runs VALUES (?,?,?)", (manifest["id"], manifest["created_at"], canonical(document)))


def review(db, run_id, time, action):
    db.execute("INSERT INTO reviews (run,time,action) VALUES (?,?,?)", (run_id, time, action))
