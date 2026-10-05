from decimal import Decimal

import pytest

from apps.components.units import UnitParseError, format_engineering, parse_engineering


@pytest.mark.parametrize(
    "raw,unit,expected",
    [
        ("100n", "F", Decimal("1E-7")),
        ("100nF", "F", Decimal("1E-7")),
        ("10uF", "F", Decimal("0.00001")),
        ("10µF", "F", Decimal("0.00001")),
        ("4u7", "F", Decimal("0.0000047")),
        ("22 pF", "F", Decimal("2.2E-11")),
        ("4k7", "Ω", Decimal("4700")),
        ("4R7", "Ω", Decimal("4.7")),
        ("10R", "Ω", Decimal("10")),
        ("10 kohm", "Ω", Decimal("10000")),
        ("1M", "Ω", Decimal("1000000")),
        ("100m", "W", Decimal("0.1")),
        ("50", "V", Decimal("50")),
        ("3.3V", "V", Decimal("3.3")),
        ("1e-7", "F", Decimal("1E-7")),
        (12, "V", Decimal("12")),
    ],
)
def test_parse_engineering(raw, unit, expected):
    assert parse_engineering(raw, unit, True) == expected


def test_lowercase_f_is_femto_not_farad():
    assert parse_engineering("10f", "F", True) == Decimal("1E-14")


@pytest.mark.parametrize("raw", ["", "abc", "10x", "1.5k7", True])
def test_parse_engineering_rejects_garbage(raw):
    with pytest.raises(UnitParseError):
        parse_engineering(raw, "F", True)


def test_without_si_prefix_plain_numbers_only():
    assert parse_engineering("512", "KB", False) == Decimal("512")
    with pytest.raises(UnitParseError):
        parse_engineering("10k", "", False)


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        (Decimal("1E-7"), "F", "100 nF"),
        (Decimal("0.00001"), "F", "10 µF"),
        (Decimal("4700"), "Ω", "4.7 kΩ"),
        (Decimal("0.1"), "W", "100 mW"),
        (Decimal("50"), "V", "50 V"),
        (Decimal("0"), "V", "0 V"),
    ],
)
def test_format_engineering(value, unit, expected):
    assert format_engineering(value, unit, True) == expected
