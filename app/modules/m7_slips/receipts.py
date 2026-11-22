from app.reasons import MESSAGES


def receipts(rolls, planning, books):
    by_roll = {record["roll"]: record for record in books["rolls"]}
    sequences = {name: index for index, name in enumerate(planning["roll_sequence"], 1)}
    result = []
    for roll in rolls:
        roll_id = roll["id"]
        placed = [plan for plan in planning["placements"] if plan["roll"] == roll_id]
        state = "封存" if roll["held"] else "待裁" if placed else "留存"
        result.append({
            "serial": f"签-{roll_id}", "roll": roll_id, "fabric": roll["fabric"], "width": roll["width"],
            "length": roll["length"], "state": state, "sequence": sequences.get(roll_id),
            "pieces": placed, "lengths": by_roll[roll_id]["lengths"], "hold_refs": roll["hold_refs"],
            "hold_message": MESSAGES["ROLL_HELD"] if roll["held"] else None, "source": roll["source"]["ref"],
        })
    return result
