from app.evidence import Row, issue
from app.modules.m2_locate.geometry import position
from app.reasons import FabricError


def locate(accepted):
    rolls = {roll["id"]: roll for roll in accepted["rolls"]["accepted"]}
    raw = accepted["defects"]
    located, isolated = [], []
    for defect in raw["accepted"]:
        roll = rolls.get(defect["roll"])
        try:
            if roll is None:
                raise FabricError("ROLL_UNKNOWN")
            located.append({**defect, **position(defect, roll["length"])})
        except FabricError as exc:
            src = defect["source"]
            row = Row(src["file"], src["line"], src["end"], tuple(src["cells"]))
            isolated.append(issue(exc.code, row, defect["id"], defect["roll"],
                                  (roll["source"]["ref"],) if roll else ()))
    holds = {}
    for item in raw["isolated"] + isolated:
        if item["roll"] in rolls:
            holds.setdefault(item["roll"], []).append(item["source"]["ref"])
    return {"located": located, "isolated": isolated, "holds": holds}
