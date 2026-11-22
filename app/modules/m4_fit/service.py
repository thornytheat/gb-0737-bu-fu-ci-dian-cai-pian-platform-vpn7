from dataclasses import dataclass

from app.config import MAX_ORDERS, MAX_PIECES, MAX_ROLLS, MAX_SEGMENTS
from app.modules.m4_fit.choices import add, compatible, counts_key, piece_vectors, within
from app.reasons import FabricError


@dataclass(frozen=True)
class Layout:
    segments: tuple


def section_rank(layout):
    occupied = [(index, tuple(-count for count in vector)) for index, vector in enumerate(layout.segments) if any(vector)]
    return len(occupied), occupied


def section_choices(roll, orders, maximum, vectors):
    usable = [compatible(order, roll) for order in orders]
    candidates = [(vector, used) for vector, used in vectors if all(not count or ok for count, ok in zip(vector, usable))]
    proposals = {tuple(0 for _ in orders): Layout(())}
    for segment in roll["available"]:
        capacity = segment["end"] - segment["start"]
        feasible = [vector for vector, used in candidates if used <= capacity]
        pending = {}
        for existing, former in proposals.items():
            for vector in feasible:
                total = add(existing, vector)
                if not within(total, maximum):
                    continue
                option = Layout(former.segments + (vector,))
                if total not in pending or section_rank(option) < section_rank(pending[total]):
                    pending[total] = option
        proposals = pending
    return proposals


def fit(rolls, raw_orders, kerf):
    orders = sorted(raw_orders, key=lambda order: (order["priority"] != "急", order["id"]))
    if (len(rolls) > MAX_ROLLS or len(orders) > MAX_ORDERS or sum(order["quantity"] for order in orders) > MAX_PIECES
            or sum(len(roll["available"]) for roll in rolls) > MAX_SEGMENTS):
        raise FabricError("PLAN_LIMIT")
    maximum, vectors = piece_vectors(orders, kerf)
    options, summaries = {}, []
    for roll in rolls:
        proposals = section_choices(roll, orders, maximum, vectors)
        best = max(proposals, key=lambda vector: (counts_key(vector, orders), vector))
        options[roll["id"]] = proposals
        summaries.append({"roll": roll["id"], "compatible": [order["id"] for order in orders if compatible(order, roll)],
                          "usable_spans": len(roll["available"]), "options": len(proposals),
                          "best_piece_count": sum(best), "best_by_order": dict(zip((item["id"] for item in orders), best))})
    return {"kerf_mm": kerf, "orders": orders, "roll_options": summaries}, options
