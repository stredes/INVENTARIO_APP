from __future__ import annotations

import pytest

from src.utils.validators import (
    normalize_rut,
    is_valid_rut_chile,
    is_valid_email,
    is_positive_int,
    is_non_negative_number,
    is_non_empty,
)


def test_normalize_rut_strips_formatting():
    assert normalize_rut(" 12.345.678-k ") == "12345678-K"
    assert normalize_rut("") == ""


@pytest.mark.parametrize(
    "rut,expected",
    [
        ("12.345.678-5", True),
        ("12.345.678-K", False),  # DV incorrecto
        ("bad-format", False),
        ("", False),
    ],
)
def test_is_valid_rut_chile_detects_check_digit(rut: str, expected: bool):
    assert is_valid_rut_chile(rut) is expected


def test_is_valid_email_accepts_optional_and_rejects_invalid():
    assert is_valid_email(None) is True
    assert is_valid_email("") is True
    assert is_valid_email("ventas@example.com") is True
    assert is_valid_email("sin-arroba") is False


def test_is_positive_int_and_non_negative_number():
    assert is_positive_int(5) is True
    assert is_positive_int("3") is True
    assert is_positive_int(0) is False
    assert is_positive_int("bad") is False

    assert is_non_negative_number(0) is True
    assert is_non_negative_number("2.5") is True
    assert is_non_negative_number(-1) is False
    assert is_non_negative_number("bad") is False


def test_is_non_empty_checks_trimmed_strings():
    assert is_non_empty("hello") is True
    assert is_non_empty("   ") is False
    assert is_non_empty(None) is False
