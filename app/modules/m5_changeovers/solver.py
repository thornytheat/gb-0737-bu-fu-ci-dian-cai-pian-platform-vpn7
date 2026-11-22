from dataclasses import dataclass

from app.modules.m4_fit.choices import add, counts_key, within


@dataclass(frozen=True)
class Pick:
    rolls: tuple = ()
    unused: int = 0

    def rank(self):
        return len(self.rolls), self.unused, tuple((name, layout.segments) for name, layout in self.rolls)


def allocate(rolls, orders, options, kerf):
    maximum = tuple(order["quantity"] for order in orders)
    totals = {tuple(0 for _ in orders): Pick()}
    for roll in sorted(rolls, key=lambda item: item["id"]):
        roll_id = roll["id"]
        capacity = roll["length"] - roll["blocked_mm"]
        pending = dict(totals)
        for previous, pick in totals.items():
            for counts, layout in options[roll_id].items():
                if not any(counts):
                    continue
                combined = add(previous, counts)
                if not within(combined, maximum):
                    continue
                used = sum(count * (order["length"] + kerf) for count, order in zip(counts, orders))
                candidate = Pick(pick.rolls + ((roll_id, layout),), pick.unused + capacity - used)
                if combined not in pending or candidate.rank() < pending[combined].rank():
                    pending[combined] = candidate
        totals = pending
    # 对所有满足相同优先目标的向量，继续比较实领卷数与已开卷余料。
    best = min(totals, key=lambda counts: (tuple(-key for key in counts_key(counts, orders)), totals[counts].rank(), counts))
    return best, totals[best]
