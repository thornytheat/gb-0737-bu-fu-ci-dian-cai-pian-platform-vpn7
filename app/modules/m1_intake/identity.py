from collections import defaultdict

from app.evidence import issue


def resolve(valid, invalid):
    groups = defaultdict(list)
    uncertain = defaultdict(list)
    for item, row in valid:
        groups[item["id"]].append((item, row))
    for entry in invalid:
        if entry["id"]:
            uncertain[entry["id"]].append(entry["source"]["ref"])
    accepted, duplicates, rejected = [], [], []
    for identifier, siblings in groups.items():
        first, initial_row = siblings[0]
        difference = next((row for item, row in siblings if item != first), None)
        if uncertain[identifier] or difference:
            code = "KEY_UNTRUSTED" if uncertain[identifier] else "KEY_CONFLICT"
            for item, row in siblings:
                link = (difference if item == first else initial_row) if difference else None
                refs = uncertain[identifier] or [link.ref]
                rejected.append(issue(code, row, identifier, item.get("roll", ""), refs))
            continue
        accepted.append({**first, "source": initial_row.view()})
        for item, row in siblings[1:]:
            duplicates.append(issue("DUPLICATE", row, identifier, item.get("roll", ""), (initial_row.ref,)))
    return accepted, duplicates, sorted(invalid + rejected, key=lambda entry: entry["source"]["line"])
