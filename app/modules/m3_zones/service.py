from collections import defaultdict

from app.modules.m3_zones.intervals import complement, union


def zones(rolls, mapping):
    by_roll = defaultdict(list)
    for defect in mapping["located"]:
        by_roll[defect["roll"]].append((*defect["expanded"], defect["source"]["ref"]))
    result = []
    for roll in rolls:
        blocked, overlap = union(by_roll[roll["id"]])
        hold_refs = mapping["holds"].get(roll["id"], [])
        if hold_refs:
            refs = sorted(set(hold_refs + [ref for span in blocked for ref in span["refs"]]))
            blocked = [{"start": 0, "end": roll["length"], "refs": refs}]
        available = complement(roll["length"], blocked)
        result.append({**roll, "blocked": blocked, "available": available, "held": bool(hold_refs),
                       "hold_refs": hold_refs, "overlap": overlap,
                       "blocked_mm": sum(span["end"] - span["start"] for span in blocked)})
    return {"rolls": result, "blocked_mm": sum(item["blocked_mm"] for item in result),
            "usable_mm": sum(item["length"] - item["blocked_mm"] for item in result)}
