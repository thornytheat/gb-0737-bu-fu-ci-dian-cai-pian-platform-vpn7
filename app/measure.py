import re
import unicodedata
from decimal import Decimal

from app.reasons import FabricError

MM = {"mm": 1, "毫米": 1, "cm": 10, "厘米": 10, "m": 1000, "米": 1000}
NULLS = {"", "-", "null", "n/a", "待测", "未知"}
NUMBER = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,4})?")


def required(value):
    value = value.strip()
    if value.casefold() in NULLS:
        raise FabricError("MISSING")
    if len(value) > 80:
        raise FabricError("BAD_VALUE")
    return value


def quantity(value, low, high):
    value = unicodedata.normalize("NFKC", required(value))
    if not value.isascii() or not value.isdecimal() or len(value) > 6:
        raise FabricError("BAD_VALUE")
    count = int(value)
    if not low <= count <= high:
        raise FabricError("BAD_VALUE")
    return count


def mm(value, unit, minimum=0, maximum=1_000_000):
    unit = unicodedata.normalize("NFKC", required(unit)).casefold()
    factor = MM.get(unit)
    if factor is None:
        raise FabricError("BAD_UNIT")
    value = unicodedata.normalize("NFKC", required(value))
    if len(value) > 18 or not NUMBER.fullmatch(value):
        raise FabricError("BAD_VALUE")
    exact = Decimal(value.replace(",", "")) * factor
    if exact != exact.to_integral_value():
        raise FabricError("SUB_MM")
    if not minimum <= exact <= maximum:
        raise FabricError("BAD_VALUE")
    return int(exact)
