from app.evidence import issue
from app.modules.m1_intake.contract import SCHEMAS
from app.modules.m1_intake.csvfile import records
from app.modules.m1_intake.identity import resolve
from app.reasons import FabricError


def read_role(role, source):
    expected, parse, id_column = SCHEMAS[role]
    rows, columns, facts = records(source, expected, role == "defects")
    good, bad = [], []
    for row in rows:
        data = dict(zip(columns, row.cells))
        identifier = data.get(id_column, "").strip()
        roll_id = data.get("卷号", "").strip() if role == "defects" else ""
        try:
            if len(row.cells) != len(columns):
                raise FabricError("BAD_COLUMNS")
            good.append((parse(data), row))
        except FabricError as exc:
            bad.append(issue(exc.code, row, identifier, roll_id))
    accepted, duplicates, rejected = resolve(good, bad)
    return {**facts, "accepted": accepted, "duplicates": duplicates, "isolated": rejected}


def intake(sources):
    return {role: read_role(role, source) for role, source in sources.items()}
