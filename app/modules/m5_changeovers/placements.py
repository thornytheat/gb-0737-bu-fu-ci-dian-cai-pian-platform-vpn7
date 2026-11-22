from collections import defaultdict

from app.modules.m4_fit.choices import compatible
from app.reasons import MESSAGES


def cuts(picked, rolls, orders, kerf):
    by_roll = {roll["id"]: roll for roll in rolls}
    piece_no = defaultdict(int)
    plans = []
    for name, layout in picked.rolls:
        for span, vector in zip(by_roll[name]["available"], layout.segments):
            start = span["start"]
            for order, count in zip(orders, vector):
                for _ in range(count):
                    piece_no[order["id"]] += 1
                    end = start + order["length"]
                    plans.append({"id": f"{order['id']}/{piece_no[order['id']]:02}", "order": order["id"], "roll": name,
                                  "start": start, "end": end, "kerf_start": end, "kerf_end": end + kerf,
                                  "length": order["length"], "source": order["source"]["ref"]})
                    start = end + kerf
    return plans


def shortfall(order, count, rolls, kerf):
    if count == order["quantity"]:
        return None
    eligible = [roll for roll in rolls if compatible(order, roll)]
    free = [roll for roll in eligible if not roll["held"]]
    required = order["length"] + kerf
    if not eligible:
        code = "NO_COMPATIBLE_ROLL"
    elif not free:
        code = "ROLLS_HELD"
    elif not any(span["end"] - span["start"] >= required for roll in free for span in roll["available"]):
        code = "SEGMENT_TOO_SHORT"
    else:
        code = "CAPACITY_USED"
    return {"code": code, "message": MESSAGES[code], "rolls": [roll["id"] for roll in eligible]}
