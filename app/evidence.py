from dataclasses import asdict, dataclass

from app.reasons import MESSAGES


@dataclass(frozen=True)
class Row:
    file: str
    line: int
    end: int
    cells: tuple[str, ...]

    @property
    def ref(self):
        return f"{self.file}:{self.line}" if self.line == self.end else f"{self.file}:{self.line}–{self.end}"

    def view(self):
        return {**asdict(self), "ref": self.ref}


def issue(code, row, identifier="", roll="", related=()):
    return {"code": code, "message": MESSAGES[code], "source": row.view(),
            "id": identifier, "roll": roll, "related": list(related)}
