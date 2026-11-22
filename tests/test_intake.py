import pytest

from app.modules.m1_intake.contract import DEFECTS, ROLLS
from app.modules.m1_intake.service import read_role
from app.reasons import FabricError
from app.source import InputFile


# TRAP-01

def test_gb18030_and_mixed_seam_units(dirty):
    orders = dirty["intake"]["orders"]
    assert orders["encoding"] == "gb18030"
    assert [(o["id"], o["seam"], o["length"]) for o in orders["accepted"]] == [
        ("C001", 10, 620), ("C002", 5, 530), ("C003", 5, 320), ("C004", 10, 620),
    ]


# TRAP-02 TRAP-06

def test_bom_full_width_and_thousands(dirty_files, dirty):
    assert dirty_files["rolls"].data.startswith(b"\xef\xbb\xbf")
    slots = dirty["intake"]["rolls"]
    assert slots["encoding"] == "utf-8-sig"
    assert [(item["id"], item["length"], item["width"]) for item in slots["accepted"][:2]] == [
        ("R-001", 2200, 1500), ("R-002", 1800, 1550),
    ]


# TRAP-03 TRAP-04

def test_multiline_physical_range_and_repeated_header(dirty):
    defects = dirty["intake"]["defects"]
    assert (defects["raw"], defects["blank"], defects["segments"]) == (15, 1, 2)
    first = defects["accepted"][0]
    assert first["note"] == "接驳折痕\n记录已补测"
    assert first["source"]["ref"] == "dirty-defects.csv:2–3"
    assert defects["accepted"][1]["source"]["line"] == 4


# TRAP-05 TRAP-07

def test_bad_columns_missing_unit_and_sub_mm_are_kept_as_evidence(dirty):
    result = dirty["intake"]
    assert [(i["source"]["line"], i["code"]) for i in result["defects"]["isolated"]] == [
        (12, "MISSING"), (14, "KEY_CONFLICT"), (15, "KEY_CONFLICT"), (17, "BAD_COLUMNS"), (18, "SUB_MM"),
    ]
    assert result["rolls"]["isolated"][0]["source"]["cells"][2] == "-"
    assert result["orders"]["isolated"][0]["code"] == "BAD_UNIT"


# TRAP-14

def test_equivalent_units_deduplicate_and_differing_payloads_conflict(dirty):
    result = dirty["intake"]
    assert [(d["id"], d["source"]["line"], d["related"]) for d in result["rolls"]["duplicates"]] == [
        ("R-002", 7, ["dirty-rolls.csv:3"]),
    ]
    conflicts = [issue for issue in result["defects"]["isolated"] if issue["id"] == "D-010"]
    assert [(row["code"], row["related"]) for row in conflicts] == [
        ("KEY_CONFLICT", ["dirty-defects.csv:15"]), ("KEY_CONFLICT", ["dirty-defects.csv:14"]),
    ]


def test_untrusted_bad_duplicate_excludes_otherwise_valid_row(dirty_files):
    original = dirty_files["rolls"]
    patched = InputFile(original.name, original.data + "R-001,斜纹棉,待测,mm,150,cm\r\n".encode())
    result = read_role("rolls", patched)
    assert "R-001" not in {r["id"] for r in result["accepted"]}
    assert [(item["source"]["line"], item["code"]) for item in result["isolated"] if item["id"] == "R-001"] == [
        (2, "KEY_UNTRUSTED"), (9, "MISSING"),
    ]


# TRAP-18

def test_empty_blank_only_header_and_explicit_no_defects_are_distinct():
    for body, code in ((b"", "EMPTY_FILE"), (b"\n \n", "BLANK_FILE"), (",".join(ROLLS).encode(), "HEADER_ONLY")):
        with pytest.raises(FabricError) as error:
            read_role("rolls", InputFile("rolls.csv", body))
        assert error.value.code == code
    result = read_role("defects", InputFile("marks.csv", ",".join(DEFECTS).encode()))
    assert (result["raw"], result["segments"], result["accepted"]) == (0, 1, [])


# TRAP-16

def test_truncated_multiline_is_source_error_with_line(dirty_files):
    file = dirty_files["defects"]
    with pytest.raises(FabricError) as error:
        read_role("defects", InputFile(file.name, file.data + b'"unfinished\r\n'))
    assert (error.value.code, error.value.file, error.value.line) == ("CSV_SYNTAX", file.name, 20)
