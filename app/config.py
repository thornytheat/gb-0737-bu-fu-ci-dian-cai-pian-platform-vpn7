import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "fabric-1.0.0"
FILE_LIMIT = 512 * 1024
ROW_LIMIT = 3000
MAX_ROLLS = 8
MAX_ORDERS = 4
MAX_PIECES = 12
MAX_SEGMENTS = 24
SAMPLES = {"dirty": "东库到货 · 原始验布", "clean": "复核对照 · 已确认"}


@dataclass(frozen=True)
class Settings:
    samples: Path
    database: Path

    @classmethod
    def from_env(cls):
        return cls(Path(os.getenv("FABRIC_SAMPLES", ROOT / "sample_data")),
                   Path(os.getenv("FABRIC_DB", ROOT / "var/fabric.sqlite3")))
