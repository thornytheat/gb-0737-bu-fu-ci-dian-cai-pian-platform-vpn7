def union(expanded):
    merged = []
    total = 0
    for start, end, ref in sorted(expanded):
        total += end - start
        if merged and start <= merged[-1]["end"]:
            previous = merged[-1]
            previous["end"] = max(previous["end"], end)
            previous["refs"].append(ref)
        else:
            merged.append({"start": start, "end": end, "refs": [ref]})
    return merged, total - sum(span["end"] - span["start"] for span in merged)


def complement(length, blocked):
    start, result = 0, []
    for span in blocked:
        if start < span["start"]:
            result.append({"start": start, "end": span["start"]})
        start = span["end"]
    if start < length:
        result.append({"start": start, "end": length})
    return result
