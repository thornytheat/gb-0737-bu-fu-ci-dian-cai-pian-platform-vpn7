from app.reasons import FabricError


def position(defect, length):
    start, end = defect["start"], defect["end"]
    if start > end:
        raise FabricError("COORD_DESC")
    if start > length or end > length:
        raise FabricError("COORD_OUTSIDE")
    if defect["kind"] == "段" and start == end:
        raise FabricError("ZERO_SPAN")
    if defect["kind"] == "点" and start != end:
        raise FabricError("POINT_WIDTH")
    if defect["origin"] == "卷尾":
        start, end = length - end, length - start
    anchor = [start, end]
    if start == end:
        start = min(start, length - 1)
        end = start + 1
    margin = defect["margin"]
    return {"anchor": anchor, "footprint": [start, end],
            "expanded": [max(0, start - margin), min(length, end + margin)]}
