from datetime import date
from decimal import Decimal as D

import pytest

from portfolio.core.models import Transaction, ValidationError
from portfolio.core.models import TransactionKind as K

DAY = date(2024, 3, 1)


def tx(kind, **fields):
    return Transaction(date=DAY, instrument_id=1, kind=kind, **fields)


VALID = {
    K.BUY: dict(quantity=D("2"), price=D("150.5"), currency="USD", fx_rate=D("23.1")),
    K.SELL: dict(quantity=D("2"), price=D("150.5"), currency="USD", fx_rate=D("23.1")),
    K.DEPOSIT: dict(amount=D("1000"), currency="CZK"),
    K.WITHDRAWAL: dict(amount=D("1000"), currency="CZK"),
    K.DIVIDEND: dict(amount=D("8.5"), currency="USD", tax=D("1.5")),
    K.STAKING_REWARD: dict(quantity=D("0.00000123")),
    K.SPLIT: dict(split_ratio=D("10")),
    K.FEE: dict(fee=D("35")),
}


@pytest.mark.parametrize("kind", list(K))
def test_valid_transaction_of_each_kind(kind):
    assert tx(kind, **VALID[kind]).kind == kind


@pytest.mark.parametrize(
    "kind, missing",
    [
        (K.BUY, "quantity"),
        (K.BUY, "price"),
        (K.BUY, "currency"),
        (K.SELL, "fx_rate"),
        (K.DEPOSIT, "amount"),
        (K.DIVIDEND, "currency"),
        (K.STAKING_REWARD, "quantity"),
        (K.SPLIT, "split_ratio"),
    ],
)
def test_required_field_missing(kind, missing):
    fields = {k: v for k, v in VALID[kind].items() if k != missing}
    with pytest.raises(ValidationError, match=f"needs '{missing}'"):
        tx(kind, **fields)


@pytest.mark.parametrize(
    "kind, extra",
    [
        (K.BUY, dict(amount=D("1"))),
        (K.BUY, dict(tax=D("1"))),
        (K.DEPOSIT, dict(quantity=D("1"))),
        (K.STAKING_REWARD, dict(price=D("1"))),
        (K.SPLIT, dict(quantity=D("1"))),
        (K.DIVIDEND, dict(split_ratio=D("2"))),
    ],
)
def test_field_not_allowed_for_kind(kind, extra):
    with pytest.raises(ValidationError, match="cannot have"):
        tx(kind, **VALID[kind], **extra)


@pytest.mark.parametrize(
    "change",
    [
        dict(quantity=D("0")),
        dict(quantity=D("-1")),
        dict(price=D("-0.01")),
        dict(fx_rate=D("0")),
        dict(fee=D("-1")),
        dict(quantity=D("NaN")),
        dict(price=D("Infinity")),
        dict(quantity=1.5),
    ],
)
def test_bad_numbers_rejected(change):
    with pytest.raises(ValidationError):
        tx(K.BUY, **{**VALID[K.BUY], **change})


def test_fee_transaction_needs_a_fee():
    with pytest.raises(ValidationError, match="greater than zero"):
        tx(K.FEE)
    with pytest.raises(ValidationError, match="cannot have"):
        tx(K.FEE, fee=D("5"), amount=D("5"))


def test_zero_price_is_allowed():
    assert tx(K.BUY, **{**VALID[K.BUY], "price": D("0")}).price == 0
