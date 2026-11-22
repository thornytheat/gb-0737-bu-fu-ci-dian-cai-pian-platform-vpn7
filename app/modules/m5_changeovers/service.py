from app.modules.m5_changeovers.placements import cuts, shortfall
from app.modules.m5_changeovers.solver import allocate


def changeovers(rolls, fit_result, options):
    orders, kerf = fit_result["orders"], fit_result["kerf_mm"]
    counts, picked = allocate(rolls, orders, options, kerf)
    return {
        "placements": cuts(picked, rolls, orders, kerf),
        "roll_sequence": [name for name, _ in picked.rolls],
        "used_rolls": len(picked.rolls), "changes": max(0, len(picked.rolls) - 1), "opened_unused_mm": picked.unused,
        "orders": [{"order": order["id"], "priority": order["priority"], "requested": order["quantity"],
                    "planned": count, "remaining": order["quantity"] - count, "review": shortfall(order, count, rolls, kerf),
                    "source": order["source"]["ref"]} for order, count in zip(orders, counts)],
    }
