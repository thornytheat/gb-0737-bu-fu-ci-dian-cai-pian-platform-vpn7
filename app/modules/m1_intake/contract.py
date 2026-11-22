from app.measure import mm, quantity, required
from app.reasons import FabricError

ROLLS = ("卷号", "布种", "卷长", "卷长单位", "幅宽", "幅宽单位")
ORDERS = ("订单号", "布种", "最小幅宽", "幅宽单位", "净长", "净长单位", "单端缝份", "缝份单位", "数量", "优先级")
DEFECTS = ("疵号", "卷号", "坐标基准", "类型", "起点", "终点", "单位", "安全余量", "余量单位", "备注")


def roll(data):
    return {"id": required(data["卷号"]), "fabric": required(data["布种"]),
            "length": mm(data["卷长"], data["卷长单位"], 1),
            "width": mm(data["幅宽"], data["幅宽单位"], 1, 4000)}


def order(data):
    priority = required(data["优先级"])
    if priority not in {"急", "常"}:
        raise FabricError("BAD_VALUE")
    length = mm(data["净长"], data["净长单位"], 1)
    seam = mm(data["单端缝份"], data["缝份单位"], 0, 200)
    return {"id": required(data["订单号"]), "fabric": required(data["布种"]),
            "width": mm(data["最小幅宽"], data["幅宽单位"], 1, 4000),
            "net": length, "seam": seam, "length": length + 2 * seam,
            "quantity": quantity(data["数量"], 1, 12), "priority": priority}


def defect(data):
    origin, kind = required(data["坐标基准"]), required(data["类型"])
    if origin not in {"卷首", "卷尾"} or kind not in {"点", "段"}:
        raise FabricError("BAD_VALUE")
    return {"id": required(data["疵号"]), "roll": required(data["卷号"]), "origin": origin, "kind": kind,
            "start": mm(data["起点"], data["单位"]), "end": mm(data["终点"], data["单位"]),
            "margin": mm(data["安全余量"], data["余量单位"], 0, 10000), "note": data["备注"].strip()}


SCHEMAS = {
    "rolls": (ROLLS, roll, "卷号"),
    "defects": (DEFECTS, defect, "疵号"),
    "orders": (ORDERS, order, "订单号"),
}
