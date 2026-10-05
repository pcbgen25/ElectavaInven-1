"""Engineering value parsing/formatting for specification values.

Examples (unit "F", SI prefixes on):   "100n" -> 1E-7,  "10uF" -> 1E-5,  "4u7" -> 4.7E-6
Examples (unit "Ω"):                    "4k7" -> 4700,  "4R7" -> 4.7,   "10 kohm" -> 10000
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

SI_PREFIXES: dict[str, int] = {
    "f": -15, "p": -12, "n": -9, "u": -6, "µ": -6, "μ": -6, "m": -3,
    "": 0, "k": 3, "K": 3, "M": 6, "G": 9, "T": 12,
}
# Prefixes used when formatting (no K/µ duplicates).
_FORMAT_PREFIXES = [(12, "T"), (9, "G"), (6, "M"), (3, "k"), (0, ""), (-3, "m"), (-6, "µ"), (-9, "n"), (-12, "p"), (-15, "f")]

UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "Ω": ("Ω", "ohm", "ohms", "Ohm", "OHM", "R"),
}

_NUMBER_RE = re.compile(
    r"^(?P<int>[+-]?\d+)(?:(?P<dot>\.)(?P<frac>\d+))?(?P<prefix>[fpnuµμmkKMGT]?)(?P<tail>\d*)$"
)


class UnitParseError(ValueError):
    pass


def _strip_unit(text: str, unit: str) -> str:
    if not unit:
        return text
    candidates = sorted(set(UNIT_ALIASES.get(unit, ()) + (unit,)), key=len, reverse=True)
    for cand in candidates:
        if len(text) <= len(cand):
            continue
        # Single letters (F, V, A, R) are case-sensitive so "10f" (femto) is not read as "10 F".
        matches = text.endswith(cand) if len(cand) == 1 else text.lower().endswith(cand.lower())
        if matches:
            return text[: -len(cand)].strip()
    return text


def parse_engineering(raw: str | int | float | Decimal, unit: str = "", use_si_prefix: bool = True) -> Decimal:
    """Parse a user-entered value into a Decimal in the definition's base unit."""
    if isinstance(raw, bool):
        raise UnitParseError("Expected a number.")
    if isinstance(raw, (int, Decimal)):
        return Decimal(raw)
    if isinstance(raw, float):
        return Decimal(str(raw))
    text = str(raw).strip().replace(" ", "").replace(",", "")
    if not text:
        raise UnitParseError("Value is empty.")
    text = _strip_unit(text, unit)
    if unit == "Ω" and re.fullmatch(r"\d+R\d*", text):
        text = text.replace("R", ".") if not text.endswith("R") else text[:-1]
    if not use_si_prefix:
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise UnitParseError(f"'{raw}' is not a valid number.") from exc
    m = _NUMBER_RE.match(text)
    if not m:
        try:
            return Decimal(text)  # scientific notation such as 1e-7
        except InvalidOperation as exc:
            raise UnitParseError(f"'{raw}' is not a valid value{f' in {unit}' if unit else ''}.") from exc
    int_part, frac, prefix, tail = m["int"], m["frac"], m["prefix"], m["tail"]
    if tail and (frac or not prefix):
        raise UnitParseError(f"'{raw}' is ambiguous.")
    number = f"{int_part}.{frac or tail or '0'}"
    exponent = SI_PREFIXES[prefix]
    return Decimal(number).scaleb(exponent).normalize() if exponent else Decimal(number).normalize()


def format_engineering(value: Decimal | None, unit: str = "", use_si_prefix: bool = True) -> str:
    if value is None:
        return ""
    value = Decimal(value)
    if not use_si_prefix or value == 0:
        return f"{_trim(value)} {unit}".strip()
    exp = value.copy_abs().adjusted()
    for power, symbol in _FORMAT_PREFIXES:
        if exp >= power:
            scaled = value.scaleb(-power)
            return f"{_trim(scaled)} {symbol}{unit}".strip()
    power, symbol = _FORMAT_PREFIXES[-1]
    return f"{_trim(value.scaleb(-power))} {symbol}{unit}".strip()


def _trim(d: Decimal) -> str:
    if abs(d) >= 1:
        d = d.quantize(Decimal("0.000001"))
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s
