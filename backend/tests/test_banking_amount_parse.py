"""USD amount parsing for transfers."""

import pytest

import app.tools.banking as banking


def test_parse_transfer_amount_usd_cents_whole_dollars() -> None:
    assert banking._parse_transfer_amount_usd_cents("10") == 1000


def test_parse_transfer_amount_usd_cents_decimals() -> None:
    assert banking._parse_transfer_amount_usd_cents(" 10.50 ") == 1050


def test_parse_transfer_amount_usd_cents_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        banking._parse_transfer_amount_usd_cents("0")


def test_parse_transfer_amount_usd_cents_rejects_invalid_string() -> None:
    with pytest.raises(ValueError, match="Invalid amount"):
        banking._parse_transfer_amount_usd_cents("not-a-number")
