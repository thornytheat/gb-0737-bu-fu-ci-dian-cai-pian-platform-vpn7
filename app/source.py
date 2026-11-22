from dataclasses import dataclass
from hashlib import sha256

from app.config import FILE_LIMIT, SAMPLES
from app.reasons import FabricError


@dataclass(frozen=True)
class InputFile:
    name: str
    data: bytes

    def facts(self):
        return {"file": self.name, "size": len(self.data), "sha256": sha256(self.data).hexdigest()}


def inputs(directory, sample):
    if sample not in SAMPLES:
        raise FabricError("SAMPLE_UNKNOWN", 404)
    files = {}
    for role in ("rolls", "defects", "orders"):
        name = f"{sample}-{role}.csv"
        try:
            with (directory / name).open("rb") as file:
                data = file.read(FILE_LIMIT + 1)
        except OSError as exc:
            raise FabricError("FILE_MISSING", file=name) from exc
        if len(data) > FILE_LIMIT:
            raise FabricError("FILE_LIMIT", file=name)
        files[role] = InputFile(name, data)
    return files
