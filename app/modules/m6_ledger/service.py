from collections import Counter, defaultdict

from app.modules.m4_fit.choices import compatible
from app.modules.m6_ledger.partition import partition


def ledger(rolls, fitting, planning, accepted, mapping):
    plans = defaultdict(list)
    orders = {order["id"]: order for order in fitting["orders"]}
    order_counts = Counter()
    roll_index = {roll["id"]: roll for roll in rolls}
    for item in planning["placements"]:
        order, roll = orders[item["order"]], roll_index[item["roll"]]
        if not compatible(order, roll) or item["end"] - item["start"] != order["length"]:
            raise RuntimeError("裁片规格或幅宽不符")
        order_counts[item["order"]] += 1
        plans[item["roll"]].append(item)
    for item in planning["orders"]:
        if item["planned"] != order_counts[item["order"]] or item["planned"] + item["remaining"] != item["requested"]:
            raise RuntimeError("订单分项不守恒")

    result = []
    for roll in rolls:
        sums, spans = partition(roll, plans[roll["id"]], fitting["kerf_mm"])
        result.append({"roll": roll["id"], "length": roll["length"], "held": roll["held"],
                       "source": roll["source"]["ref"], "lengths": sums, "spans": spans})
    totals = {key: sum(item["lengths"][key] for item in result) for key in ("piece", "blocked", "kerf", "unused")}
    totals["length"] = sum(item["length"] for item in result)
    totals["delta"] = totals["length"] - sum(totals[k] for k in ("piece", "blocked", "kerf", "unused"))
    sources = {}
    for role, report in accepted.items():
        extra = len(mapping["isolated"]) if role == "defects" else 0
        counts = {"raw": report["raw"], "accepted": len(report["accepted"]) - extra,
                  "duplicates": len(report["duplicates"]), "isolated": len(report["isolated"]) + extra}
        counts["delta"] = counts["raw"] - counts["accepted"] - counts["duplicates"] - counts["isolated"]
        if counts["delta"] != 0:
            raise RuntimeError("采信账不守恒")
        sources[role] = counts
    return {"rolls": result, "totals": totals, "records": sources}
