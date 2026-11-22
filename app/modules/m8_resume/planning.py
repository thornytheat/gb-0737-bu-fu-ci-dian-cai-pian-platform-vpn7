from collections import Counter

from app.reasons import FabricError

# 落刀位置 cut_mm 是刀刃在布卷上的绝对坐标，按卷首量起。
# 一片的排版足迹是片身 [start, end) 加紧随的刀口 [end, kerf_end)。
#   正落在 kerf_end：片身和刀口一起完成；
#   落在 (end, kerf_end)：片身已断、刀口没闭合，只能补切到 kerf_end；
#   落在 (start, end)：切出半片，这一片连同它的刀口整件作废（宁可多耗一件，
#     也不能把半片当整片），后面的裁片仍按原排版继续。
#   落在片首：只在已有作废片时允许，用来重建前缘的空刀。
# 另外，只有当上一刀停在片首（或段首/禁切区隔断）时，才允许把整片切断；
# 否则会切出长度不对的长条。
# 回执只追加、不改写；同一回执重试不新增裁片或刀口，失败不落新版本。

COMPLETE = "complete"
KERF_OPEN = "kerf_open"
SCRAP = "scrap"
PENDING = "pending"
LIVE = {PENDING, KERF_OPEN}
HIT_COMPLETE = "hit_complete"
HIT_KERF = "hit_kerf"
HIT_PARTIAL = "hit_partial"
HIT_EDGE = "hit_edge"


def layout(snapshot):
    zones = snapshot["zones"]["rolls"]
    by_roll = {roll["id"]: [] for roll in zones}
    for plan in snapshot["changeovers"]["placements"]:
        by_roll.setdefault(plan["roll"], []).append(plan)
    for plans in by_roll.values():
        plans.sort(key=lambda plan: (plan["start"], plan["kerf_end"]))
    return zones, by_roll


def classify(cut, roll, pieces):
    """把绝对落刀位置对到某一片上；越界、穿禁切或不对方案的刀都拒绝。"""
    if cut <= 0 or cut > roll["length"]:
        raise FabricError("CUT_OUTSIDE")
    for span in roll["blocked"]:
        if span["start"] < cut < span["end"]:
            raise FabricError("CUT_BLOCKED")
    for index, piece in enumerate(pieces):
        if cut == piece["kerf_end"]:
            return index, HIT_COMPLETE
        if piece["start"] < cut < piece["end"]:
            return index, HIT_PARTIAL
        if piece["end"] <= cut < piece["kerf_end"]:
            return index, HIT_KERF
        if cut == piece["start"]:
            return index, HIT_EDGE
    raise FabricError("CUT_UNPLANNED")


def derive(pieces, events):
    """只追加、不回写：按登记顺序把事件还原成每片状态。"""
    index = {piece["id"]: position for position, piece in enumerate(pieces)}
    states = [{"status": PENDING, "cut": None, "events": []} for _ in pieces]
    for event in sorted(events, key=lambda item: item["seq"]):
        position = index.get(event["piece"])
        if position is None:
            raise RuntimeError("回执指向方案外的裁片")
        state = states[position]
        if event["kind"] == "trim":
            # 半片作废后收口，或片首重建前缘：只截齐，不改变完成状态。
            state["events"].append(event)
            continue
        if event["kind"] == "partial":
            state["status"], state["cut"] = SCRAP, event["cut"]
        elif event["kind"] == "kerf":
            state["status"], state["cut"] = KERF_OPEN, event["cut"]
        elif event["kind"] == "complete":
            state["status"], state["cut"] = COMPLETE, event["cut"]
        else:
            raise RuntimeError("未知回执事件")
        state["events"].append(event)
    return states


def frontier(states):
    return next((position for position, state in enumerate(states) if state["status"] in LIVE), None)


def span_of(roll, piece):
    return next((item for item in roll["available"] if item["start"] <= piece["start"] < item["end"]), None)


def edge_ready(roll, pieces, index, last_cut):
    """片首前缘是否已建立：卷首/段首是天然前缘，段内必须恰好停在片首才能算一刀到齐。"""
    if last_cut is None:
        return True
    piece, span = pieces[index], span_of(roll, pieces[index])
    if span is not None and last_cut <= span["start"]:
        return True
    return last_cut == piece["start"]


def accept(cut, roll, pieces, states, last_cut):
    """写入前校验一条落刀，返回 (事件草稿, 片序号, 落刀类别)。"""
    index, hit = classify(cut, roll, pieces)
    status = states[index]["status"]
    if status == SCRAP:
        # 作废片的刀口终点只用来收口，不新增裁片或刀口。
        if hit != HIT_COMPLETE:
            raise FabricError("CUT_DUPLICATE", 409)
        event = "trim"
    elif status == COMPLETE:
        raise FabricError("CUT_DUPLICATE", 409)
    elif status == KERF_OPEN:
        if hit != HIT_COMPLETE:
            raise FabricError("CUT_GAP", 409)
        event = "complete"
    elif index != frontier(states):
        raise FabricError("CUT_GAP", 409)
    elif hit == HIT_EDGE:
        # 片首齐刀只有在存在作废片、需要重建前缘时才有意义；否则是无产出的一刀。
        if not any(item["status"] == SCRAP for item in states):
            raise FabricError("CUT_GAP", 409)
        event = "trim"
    elif hit == HIT_COMPLETE:
        if not edge_ready(roll, pieces, index, last_cut):
            raise FabricError("CUT_EDGE", 409)
        event = "complete"
    elif hit == HIT_PARTIAL:
        event = "partial"
    elif hit == HIT_KERF:
        # 片身要在片首断开后才算独立一片；前缘没对齐就下刀，切出的是超长条。
        if not edge_ready(roll, pieces, index, last_cut):
            raise FabricError("CUT_EDGE", 409)
        event = "kerf"
    else:
        raise FabricError("CUT_GAP", 409)
    if last_cut is not None and cut <= last_cut:
        raise FabricError("CUT_DUPLICATE" if cut == last_cut else "CUT_GAP", 409)
    return {"cut": cut, "kind": event, "piece": pieces[index]["id"]}, index, hit


def resume_point(roll, pieces, states, last_cut):
    """剩余段从本卷最后一刀算起；下一刀要么补刀口，要么先重建前缘再落刀。"""
    target = frontier(states)
    if target is None:
        return None
    piece, state = pieces[target], states[target]
    span = span_of(roll, piece)
    if span is None:  # 方案外的裁片无从续裁，只报不猜
        return {"kind": "unplannable", "piece": piece["id"], "reference_cut_mm": last_cut,
                "segment": None, "next_cut_mm": None, "fits": False, "note": "裁片不在可用段内"}
    if state["status"] == KERF_OPEN:
        start = state["cut"]
        return {"kind": "kerf_finish", "piece": piece["id"], "order": piece["order"],
                "reference_cut_mm": last_cut, "advance_mm": 0,
                "segment": {"start_mm": start, "end_mm": span["end"], "length_mm": span["end"] - start},
                "next_cut_mm": piece["kerf_end"], "open_kerf_mm": piece["kerf_end"] - start,
                "piece_length_mm": piece["end"] - piece["start"],
                "fits": piece["kerf_end"] <= span["end"],
                "note": "片身已断、刀口未闭合；补切到刀口终点前余料不放行"}
    start = max(last_cut, span["start"]) if last_cut is not None else piece["start"]
    if edge_ready(roll, pieces, target, last_cut):
        return {"kind": "piece", "piece": piece["id"], "order": piece["order"],
                "reference_cut_mm": last_cut, "advance_mm": 0,
                "segment": {"start_mm": start, "end_mm": span["end"], "length_mm": span["end"] - start},
                "next_cut_mm": piece["kerf_end"], "piece_length_mm": piece["end"] - piece["start"],
                "fits": piece["kerf_end"] <= span["end"],
                "note": "前缘已对齐片首（或由段首/禁切区隔断），按片长落下一刀"}
    # 上一刀停在片身里或片首之外：下一刀先在片首重建前缘，否则会切出长度不对的长条。
    return {"kind": "realign", "piece": piece["id"], "order": piece["order"],
            "reference_cut_mm": last_cut, "advance_mm": piece["start"] - start,
            "segment": {"start_mm": start, "end_mm": span["end"], "length_mm": span["end"] - start},
            "next_cut_mm": piece["start"], "piece_length_mm": piece["end"] - piece["start"],
            "fits": piece["start"] >= start and piece["kerf_end"] <= span["end"],
            "note": "先在片首齐一刀重建前缘，再按片长落刀；这是半片作废的代价"}


def written_regions(roll, pieces, states):
    """半片作废写掉的连续区间：从该片片首到刀口终点；
    若下一片同段且片首更远，中间空走段也随作废片写掉，不能算余料。"""
    regions = []
    for position, (piece, state) in enumerate(zip(pieces, states)):
        if state["status"] != SCRAP:
            continue
        end = piece["kerf_end"]
        if position + 1 < len(pieces):
            nxt = pieces[position + 1]
            if span_of(roll, piece) is span_of(roll, nxt):
                end = max(end, nxt["start"])
        regions.append((piece["start"], end))
    merged = []
    for start, end in sorted(regions):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def roll_progress(pieces, events, roll):
    states = derive(pieces, events)
    last_cut = max((event["cut"] for event in events), default=None)
    completed, kerf_open, interrupted, pending = [], [], [], []
    for position, (piece, state) in enumerate(zip(pieces, states)):
        record = {"piece": piece["id"], "order": piece["order"], "start": piece["start"], "end": piece["end"],
                  "kerf_start": piece["kerf_start"], "kerf_end": piece["kerf_end"],
                  "receipt": state["events"][-1]["receipt"] if state["events"] else None}
        if state["status"] == COMPLETE:
            completed.append({**record, "cut_mm": state["cut"]})
        elif state["status"] == KERF_OPEN:
            kerf_open.append({**record, "cut_mm": state["cut"], "open_kerf_mm": piece["kerf_end"] - state["cut"]})
        elif state["status"] == SCRAP:
            # 半片按整件作废：这一片足迹（片身加刀口）整段写掉，绝不回流成合格裁片。
            interrupted.append({**record, "cut_mm": state["cut"],
                                "discarded_mm": state["cut"] - piece["start"]})
        else:
            pending.append({**record, "expected_cut_mm": piece["kerf_end"]})

    written = written_regions(roll, pieces, states)
    finished = sum(item["end"] - item["start"] for item in completed + kerf_open)
    kerf = sum(item["kerf_end"] - item["kerf_start"] for item in completed)
    kerf += sum(item["cut_mm"] - item["end"] for item in kerf_open)
    open_kerf = sum(item["open_kerf_mm"] for item in kerf_open)
    written_off = sum(end - start for start, end in written)
    remaining = sum(item["end"] - item["start"] + item["kerf_end"] - item["kerf_start"] for item in pending)
    unused = sum(span["end"] - span["start"] for span in roll["available"]) - finished - kerf - open_kerf \
        - written_off - remaining
    amounts = {"length": roll["length"], "finished_piece_mm": finished, "kerf_mm": kerf,
               "open_kerf_mm": open_kerf, "written_off_mm": written_off,
               "blocked_mm": roll["blocked_mm"], "remaining_piece_mm": remaining, "unused_mm": unused}
    amounts["delta"] = roll["length"] - sum(amounts[key] for key in (
        "finished_piece_mm", "kerf_mm", "open_kerf_mm", "written_off_mm", "blocked_mm",
        "remaining_piece_mm", "unused_mm"))

    cut_conflicts = sorted({item["cut_mm"] for item in completed + kerf_open + interrupted
                            if any(span["start"] < item["cut_mm"] < span["end"] for span in roll["blocked"])})
    blocked_ok = not cut_conflicts and all(
        not (piece["start"] < span["end"] and span["start"] < piece["kerf_end"])
        for piece in pieces for span in roll["blocked"])
    kerf_ok = not kerf_open
    balanced = kerf_ok and blocked_ok and not interrupted and not pending and amounts["delta"] == 0

    reasons = []
    if roll["held"]:
        reasons.append("HELD")
    if pending:
        reasons.append("PENDING")
    if kerf_open:
        reasons.append("KERF_OPEN")
    if interrupted:
        reasons.append("SCRAPPED")
    if not blocked_ok:
        reasons.append("BLOCKED_CONFLICT")
    if amounts["delta"] != 0:
        reasons.append("ACCOUNTING")
    # 仓管只在计划刀口全部闭合、且与禁切区对平后才放行余料；作废的半片也必须先人工裁决。
    release_ready = not roll["held"] and not pending and not kerf_open and not interrupted \
        and blocked_ok and amounts["delta"] == 0
    return {
        "roll": roll["id"], "fabric": roll["fabric"], "width": roll["width"], "length": roll["length"],
        "held": roll["held"], "hold_refs": roll["hold_refs"], "source": roll["source"]["ref"],
        "completed": completed, "kerf_open": kerf_open, "interrupted": interrupted, "pending": pending,
        "resume": resume_point(roll, pieces, states, last_cut),
        "reconciliation": {
            "planned_kerfs": len(pieces), "balanced_kerfs": len(completed),
            "open_kerfs": len(kerf_open), "scrapped_pieces": len(interrupted),
            "blocked_spans": len(roll["blocked"]), "blocked_mm": roll["blocked_mm"],
            "blocked_ok": blocked_ok, "kerf_ok": kerf_ok, "cut_conflicts": cut_conflicts,
            "amounts": amounts, "balanced": balanced,
        },
        "release": {"ready": release_ready, "unused_mm": unused if release_ready else 0, "reasons": reasons},
        "progress": {COMPLETE: len(completed), KERF_OPEN: len(kerf_open),
                     SCRAP: len(interrupted), PENDING: len(pending)},
    }


def state_label(roll, progress):
    if roll["held"]:
        return "封存"
    if not progress["reconciliation"]["planned_kerfs"]:
        return "留存"
    if progress["interrupted"]:
        return "中断待决"
    if progress["kerf_open"]:
        return "续裁中"
    if not progress["pending"]:
        return "已完成"
    if progress["completed"]:
        return "续裁中"
    return "待裁"


def build_sheet(document, events, receipts, version, created_at):
    snapshot = document["snapshot"]
    manifest = document["manifest"]
    zones, by_roll = layout(snapshot)
    grouped = {}
    for event in events:
        grouped.setdefault(event["roll"], []).append(event)
    rolls, slips = [], []
    totals = Counter({"planned": 0, "completed": 0, "kerf_open": 0, "scrapped": 0, "pending": 0})
    for roll in zones:
        pieces = by_roll.get(roll["id"], [])
        progress = roll_progress(pieces, grouped.get(roll["id"], []), roll)
        progress["state"] = state_label(roll, progress)
        progress["serial"] = f"签-{roll['id']}"
        progress["version"] = version
        rolls.append(progress)
        slips.append({"serial": progress["serial"], "version": version, "roll": roll["id"],
                      "state": progress["state"], "completed": progress["completed"],
                      "kerf_open": progress["kerf_open"], "interrupted": progress["interrupted"],
                      "pending": progress["pending"], "resume": progress["resume"],
                      "release": progress["release"], "reconciliation": progress["reconciliation"]})
        totals["planned"] += len(pieces)
        totals["completed"] += len(progress["completed"])
        totals["kerf_open"] += len(progress["kerf_open"])
        totals["scrapped"] += len(progress["interrupted"])
        totals["pending"] += len(progress["pending"])
    waiting = [roll["roll"] for roll in rolls if not roll["held"] and not roll["release"]["ready"]]
    sealed = [roll["roll"] for roll in rolls if roll["held"]]
    return {
        "run_id": manifest["id"], "version": version, "created_at": created_at,
        "plan_sha256": manifest["result_sha256"], "kerf_mm": snapshot["fit"]["kerf_mm"],
        "totals": dict(totals),
        "release": {"ready": not waiting,
                    "release_ready_rolls": [roll["roll"] for roll in rolls if roll["release"]["ready"]],
                    "waiting_rolls": waiting, "sealed_rolls": sealed},
        "rolls": rolls,
        "slips": slips,
        "receipts": [dict(receipt) for receipt in receipts],
    }
