"""Domain objects stored in the database."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class ValidationError(ValueError):
    """A record does not satisfy the rules for its kind."""


class ValuationMethod(StrEnum):
    YAHOO = "yahoo"  # quantity held x downloaded price
    MANUAL = "manual"  # value entered by hand (savings, funds without a quote)


class TransactionKind(StrEnum):
    BUY = "buy"
    SELL = "sell"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    DIVIDEND = "dividend"
    STAKING_REWARD = "staking_reward"
    SPLIT = "split"
    FEE = "fee"  # a charge on its own, not tied to another transaction


@dataclass(frozen=True)
class Instrument:
    ticker: str
    type: str
    currency: str
    valuation: ValuationMethod
    name: str | None = None
    dividend_currency: str | None = None
    yahoo_symbol: str | None = None
    active: bool = True
    id: int | None = None


K = TransactionKind

# Which optional fields each kind uses: field -> kinds where it is required / merely allowed.
_REQUIRED: dict[str, set[TransactionKind]] = {
    "quantity": {K.BUY, K.SELL, K.STAKING_REWARD},
    "price": {K.BUY, K.SELL},
    "amount": {K.DEPOSIT, K.WITHDRAWAL, K.DIVIDEND},
    "currency": {K.BUY, K.SELL, K.DEPOSIT, K.WITHDRAWAL, K.DIVIDEND},
    "fx_rate": {K.BUY, K.SELL},
    "split_ratio": {K.SPLIT},
}
_ALLOWED: dict[str, set[TransactionKind]] = {
    # No rate on cash movements and dividends means "use the market rate of that day".
    "fx_rate": {K.DEPOSIT, K.WITHDRAWAL, K.DIVIDEND},
    "tax": {K.DIVIDEND},
}
_STRICTLY_POSITIVE = {"quantity", "amount", "fx_rate", "split_ratio"}


TRANSACTION_FIELDS = ("quantity", "price", "amount", "currency", "fx_rate", "tax", "split_ratio")


def fields_for(kind: TransactionKind) -> tuple[list[str], list[str]]:
    """Which of the optional transaction fields a kind requires, and which it merely allows."""
    required = [f for f in TRANSACTION_FIELDS if kind in _REQUIRED.get(f, ())]
    optional = [f for f in TRANSACTION_FIELDS if kind in _ALLOWED.get(f, ()) and f not in required]
    return required, optional


@dataclass(frozen=True)
class Transaction:
    """One ledger row. Numbers are always positive; ``kind`` gives the direction.

    ``fx_rate`` is base currency per 1 unit of ``currency``. ``fee`` is in base currency.
    For dividends ``amount`` is the net amount received and ``tax`` the amount withheld.
    """

    date: date
    instrument_id: int
    kind: TransactionKind
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal | None = None
    currency: str | None = None
    fx_rate: Decimal | None = None
    fee: Decimal = Decimal(0)
    tax: Decimal | None = None
    split_ratio: Decimal | None = None
    note: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        kind = self.kind
        for field in TRANSACTION_FIELDS:
            value = getattr(self, field)
            required = kind in _REQUIRED.get(field, ())
            allowed = required or kind in _ALLOWED.get(field, ())
            if value is None:
                if required:
                    raise ValidationError(f"A {kind} transaction needs '{field}'")
                continue
            if not allowed:
                raise ValidationError(f"A {kind} transaction cannot have '{field}'")
            if field != "currency":
                self._check_number(field, value, strictly_positive=field in _STRICTLY_POSITIVE)
        self._check_number("fee", self.fee, strictly_positive=False)
        if kind is K.FEE and self.fee == 0:
            raise ValidationError("A fee transaction needs a 'fee' greater than zero")

    @staticmethod
    def _check_number(field: str, value: Decimal, *, strictly_positive: bool) -> None:
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValidationError(f"'{field}' must be a finite decimal number")
        if value < 0 or (strictly_positive and value == 0):
            limit = "greater than zero" if strictly_positive else "zero or more"
            raise ValidationError(f"'{field}' must be {limit}")


@dataclass(frozen=True)
class Valuation:
    """Manually entered total value of an instrument on a date, in its currency."""

    instrument_id: int
    date: date
    value: Decimal


@dataclass(frozen=True)
class Price:
    instrument_id: int
    date: date
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    dividend: float = 0.0
    split: float = 0.0


@dataclass(frozen=True)
class FxRate:
    """``close`` is how many units of ``to_currency`` one unit of ``from_currency`` buys."""

    date: date
    from_currency: str
    to_currency: str
    close: float
