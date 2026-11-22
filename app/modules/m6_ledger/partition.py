from collections import Counter


def partition(roll, placements, kerf):
    intervals = [{**span, "type": "blocked"} for span in roll["blocked"]]
    for plan in placements:
        if plan["kerf_start"] != plan["end"] or plan["kerf_end"] - plan["kerf_start"] != kerf:
            raise RuntimeError("切口长度或起点异常")
        intervals += [
            {"start": plan["start"], "end": plan["end"], "type": "piece", "id": plan["id"], "order": plan["order"]},
            {"start": plan["kerf_start"], "end": plan["kerf_end"], "type": "kerf", "id": plan["id"]},
        ]
    cursor = 0
    parts = []
    sums = Counter({"blocked": 0, "piece": 0, "kerf": 0, "unused": 0})
    for span in sorted(intervals, key=lambda span: (span["start"], span["end"])):
        if not cursor <= span["start"] < span["end"] <= roll["length"]:
            raise RuntimeError("发现跨区、相交或越界切割")
        if cursor < span["start"]:
            sums["unused"] += span["start"] - cursor
            parts.append({"start": cursor, "end": span["start"], "type": "unused"})
        parts.append(span)
        sums[span["type"]] += span["end"] - span["start"]
        cursor = span["end"]
    if cursor < roll["length"]:
        sums["unused"] += roll["length"] - cursor
        parts.append({"start": cursor, "end": roll["length"], "type": "unused"})
    if sum(sums.values()) != roll["length"] or sums["blocked"] != roll["blocked_mm"]:
        raise RuntimeError("卷长分项不守恒")
    return dict(sums), parts
