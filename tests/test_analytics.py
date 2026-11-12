"""Analytics checked against numbers worked out by hand. Base currency is CZK."""

from datetime import date
from decimal import Decimal as D

import pytest

from portfolio.core import repo
from portfolio.core.analytics import checks, dividends, performance, taxes, timeseries
from portfolio.core.analytics.allocation import allocation
from portfolio.core.analytics.data import Series, load_data
from portfolio.core.analytics.overview import lots, overview, sales, summarize
from portfolio.core.models import FxRate, Instrument, Price, Transaction, Valuation
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod as V


def day(n: int, month: int = 1, year: int = 2024) -> date:
    return date(year, month, n)


class Book:
    """Small helper to write a portfolio into the test database."""

    def __init__(self, conn):
        self.conn = conn
        for code in ("CZK", "USD", "EUR", "PLN"):
            repo.add_currency(conn, code)
        for name in ("stock", "crypto", "savings", "benchmark"):
            repo.add_instrument_type(conn, name)

    def instrument(self, ticker, currency="CZK", type="stock", valuation=V.YAHOO, **more):
        return repo.add_instrument(
            self.conn,
            Instrument(ticker=ticker, type=type, currency=currency, valuation=valuation, **more),
        ).id

    def tx(self, instrument_id, on, kind, **fields):
        fields = {k: D(str(v)) if isinstance(v, int | float) else v
                  for k, v in fields.items()}  # fmt: skip
        repo.add_transaction(self.conn, Transaction(on, instrument_id, kind, **fields))

    def buy(self, instrument_id, on, quantity, price, currency="CZK", fx_rate=1, **more):
        self.tx(instrument_id, on, K.BUY, quantity=quantity, price=price, currency=currency,
                fx_rate=fx_rate, **more)  # fmt: skip

    def sell(self, instrument_id, on, quantity, price, currency="CZK", fx_rate=1, **more):
        self.tx(instrument_id, on, K.SELL, quantity=quantity, price=price, currency=currency,
                fx_rate=fx_rate, **more)  # fmt: skip

    def prices(self, instrument_id, closes: dict[date, float]):
        repo.save_prices(self.conn, [Price(instrument_id, d, close=c) for d, c in closes.items()])

    def fx(self, currency, rates: dict[date, float]):
        repo.save_fx_rates(self.conn, [FxRate(d, currency, "CZK", r) for d, r in rates.items()])

    def load(self):
        return load_data(self.conn, "CZK")


@pytest.fixture
def book(conn):
    return Book(conn)


def only(rows, ticker):
    (row,) = [r for r in rows if r.ticker == ticker]
    return row


# --- Series ---------------------------------------------------------------------------------


def test_series_returns_latest_value_on_or_before_a_day():
    series = Series([(day(5), 2.0), (day(2), 1.0)])
    assert series.at(day(1)) is None
    assert series.at(day(2)) == 1.0
    assert series.at(day(4)) == 1.0
    assert series.at_with_date(day(9)) == (day(5), 2.0)
    assert not Series()


# --- overview -------------------------------------------------------------------------------


def test_overview_of_a_foreign_stock(book):
    aapl = book.instrument("AAPL", "USD", name="Apple")
    book.fx("USD", {day(1): 20, day(10): 22})
    book.prices(aapl, {day(2): 100, day(10): 110})
    book.buy(aapl, day(2), 2, 100, "USD", 20, fee=10)  # costs 4000
    book.sell(aapl, day(5), 1, 105, "USD", 21, fee=5)  # brings 2205
    book.tx(aapl, day(8), K.DIVIDEND, amount=50, currency="CZK", fx_rate=1)

    row = only(overview(book.load(), day(10)), "AAPL")
    assert (row.name, row.type, row.currency) == ("Apple", "stock", "USD")
    assert row.quantity == pytest.approx(1)
    assert row.last_price == 110
    assert row.average_price == pytest.approx(100)
    assert row.invested == pytest.approx(4000)
    assert row.returned == pytest.approx(2205)
    assert (row.fees, row.dividends) == (15, 50)
    assert row.value == pytest.approx(1 * 110 * 22)  # 2420
    assert row.cost_basis == pytest.approx(2000)  # the one share still held
    assert row.unrealised_profit == pytest.approx(420)  # 2420 - 2000
    assert row.fx_profit == pytest.approx(200)  # its 100 USD bought at 20, now worth 22
    assert row.rewards == 0
    assert row.price_profit == pytest.approx(220)  # 10 USD up, at 22
    assert row.realised_profit == pytest.approx(205)  # sold for 2205 what cost 2000
    assert row.total_profit == pytest.approx(625)  # 2420 + 2205 - 4000 = 420 + 205
    assert row.net_profit == pytest.approx(660)  # 625 + 50 - 15


def test_sales_use_up_the_oldest_units_first(book):
    stock = book.instrument("X")
    book.prices(stock, {day(10): 200})
    book.buy(stock, day(1), 10, 100)  # 1000
    book.buy(stock, day(2), 10, 150)  # 1500
    book.sell(stock, day(3), 15, 180)  # 2700: ten at 100 and five at 150 = 1750
    row = only(overview(book.load(), day(10)), "X")

    assert row.quantity == pytest.approx(5)
    assert row.realised_profit == pytest.approx(2700 - 1750)
    assert row.cost_basis == pytest.approx(750)  # five units at 150
    assert row.average_price == pytest.approx(150)
    assert row.unrealised_profit == pytest.approx(5 * 200 - 750)
    assert row.price_profit == pytest.approx(250)
    assert row.total_profit == pytest.approx(row.unrealised_profit + row.realised_profit)
    # Before the sale nothing was realised.
    assert only(overview(book.load(), day(2)), "X").realised_profit == 0


def test_closed_position_keeps_its_realised_profit(book):
    stock = book.instrument("X")
    book.buy(stock, day(1), 2, 100)
    book.sell(stock, day(3), 2, 130, fee=7)
    row = only(overview(book.load(), day(10)), "X")
    assert (row.quantity, row.value, row.cost_basis) == (0, 0, 0)
    assert (row.unrealised_profit, row.fx_profit, row.price_profit, row.rewards) == (0, 0, 0, 0)
    assert row.average_price is None
    assert row.realised_profit == pytest.approx(60)
    assert row.total_profit == pytest.approx(60)
    assert row.net_profit == pytest.approx(53)


def test_staking_units_cost_nothing_and_lost_units_realise_a_loss(book):
    coin = book.instrument("C", type="crypto")
    book.prices(coin, {day(10): 50})
    book.tx(coin, day(1), K.STAKING_REWARD, quantity=2)
    book.buy(coin, day(2), 10, 40)  # 400
    book.sell(coin, day(3), 1, 45)  # oldest unit is a staking one: all 45 is profit
    book.sell(coin, day(4), 3, 0)  # one staking unit and two bought ones are lost: -80
    row = only(overview(book.load(), day(10)), "C")

    assert row.quantity == pytest.approx(8)
    assert row.realised_profit == pytest.approx(45 - 80)
    assert row.cost_basis == pytest.approx(320)
    assert row.rewards == 0  # no staking units are left
    assert row.average_price == pytest.approx(40)
    assert row.unrealised_profit == pytest.approx(8 * 50 - 320)
    assert row.total_profit == pytest.approx(row.unrealised_profit + row.realised_profit)


def test_staking_correction_takes_back_free_units_without_a_loss(book):
    coin = book.instrument("C", type="crypto")
    book.prices(coin, {day(10): 50})
    book.buy(coin, day(1), 10, 40)  # 400
    book.tx(coin, day(2), K.STAKING_REWARD, quantity=2)
    book.tx(coin, day(3), K.STAKING_REWARD, quantity=1)
    book.tx(coin, day(4), K.STAKING_CORRECTION, quantity=2.5)
    row = only(overview(book.load(), day(10)), "C")

    assert row.quantity == pytest.approx(10.5)
    assert row.realised_profit == pytest.approx(0)
    assert row.cost_basis == pytest.approx(400)
    assert row.rewards == pytest.approx(0.5 * 50)
    assert row.total_profit == pytest.approx(10.5 * 50 - 400)


def test_staking_correction_beyond_the_rewards_loses_bought_units(book):
    coin = book.instrument("C", type="crypto")
    book.prices(coin, {day(10): 50})
    book.buy(coin, day(1), 10, 40)
    book.tx(coin, day(2), K.STAKING_REWARD, quantity=1)
    book.tx(coin, day(3), K.STAKING_CORRECTION, quantity=3)
    row = only(overview(book.load(), day(10)), "C")

    assert row.quantity == pytest.approx(8)
    assert row.realised_profit == pytest.approx(-80)
    assert row.cost_basis == pytest.approx(320)
    assert row.rewards == 0


def test_exchange_rate_profit_only_counts_units_still_held(book):
    stock = book.instrument("U", "USD")
    book.fx("USD", {day(1): 20, day(10): 25})
    book.prices(stock, {day(10): 10})
    book.buy(stock, day(1), 10, 10, "USD", 20)  # 100 USD = 2000
    book.sell(stock, day(5), 9, 10, "USD", 24)  # 90 USD = 2160, cost 1800
    row = only(overview(book.load(), day(10)), "U")
    assert row.realised_profit == pytest.approx(360)
    assert row.fx_profit == pytest.approx(10 * 25 - 200)  # one unit: 10 USD from 20 to 25
    assert row.price_profit == pytest.approx(0)


def test_selling_more_than_held_does_not_break(book):
    stock = book.instrument("X")
    book.prices(stock, {day(10): 100})
    book.buy(stock, day(1), 1, 100)
    book.sell(stock, day(2), 3, 110)
    row = only(overview(book.load(), day(10)), "X")
    assert row.quantity == pytest.approx(-2)
    assert row.cost_basis == 0
    assert row.realised_profit == pytest.approx(330 - 100)
    assert row.total_profit == pytest.approx(row.unrealised_profit + row.realised_profit)


def test_overview_as_of_an_earlier_day(book):
    aapl = book.instrument("AAPL", "USD")
    book.fx("USD", {day(1): 20, day(10): 22})
    book.prices(aapl, {day(2): 100, day(10): 110})
    book.buy(aapl, day(2), 2, 100, "USD", 20)
    book.sell(aapl, day(5), 1, 105, "USD", 21)

    row = only(overview(book.load(), day(3)), "AAPL")
    assert row.quantity == 2
    assert row.returned == 0
    assert row.value == pytest.approx(2 * 100 * 20)


def test_overview_of_crypto_bought_in_two_currencies_with_staking(book):
    btc = book.instrument("BTC", "EUR", type="crypto")
    book.fx("EUR", {day(1): 25, day(10): 26})
    book.fx("USD", {day(1): 20, day(10): 22})
    book.prices(btc, {day(10): 40000})
    book.buy(btc, day(2), 0.1, 30000, "EUR", 25)  # 3000 EUR = 75000
    book.buy(btc, day(3), 0.1, 33000, "USD", 20)  # 3300 USD = 66000
    book.tx(btc, day(4), K.STAKING_REWARD, quantity=0.01)

    row = only(overview(book.load(), day(10)), "BTC")
    assert row.quantity == pytest.approx(0.21)
    assert row.invested == pytest.approx(141000)
    assert row.value == pytest.approx(0.21 * 40000 * 26)  # 218400
    assert row.total_profit == pytest.approx(77400)
    # The dollars paid 66000 / 25 = 2640 EUR worth of the coin, which is priced in EUR.
    assert row.fx_profit == pytest.approx((3000 + 2640) * 26 - 141000)  # 5640
    assert row.rewards == pytest.approx(0.01 * 40000 * 26)  # 10400
    assert row.price_profit == pytest.approx(77400 - 5640 - 10400)
    assert row.average_price == pytest.approx((3000 + 2640) / 0.2)


def test_paying_in_base_currency_for_an_instrument_priced_in_another(book):
    """The same purchase entered in CZK or in EUR gives the same numbers."""
    in_czk = book.instrument("CSG", "EUR")
    in_eur = book.instrument("CSG2", "EUR")
    book.fx("EUR", {day(1): 25, day(10): 24})
    for stock in (in_czk, in_eur):
        book.prices(stock, {day(1): 14, day(10): 16})
    book.buy(in_czk, day(1), 10, 350)  # 3500 CZK
    book.buy(in_eur, day(1), 10, 14, "EUR", 25)  # 140 EUR = 3500 CZK
    data = book.load()

    czk, eur = only(overview(data, day(10)), "CSG"), only(overview(data, day(10)), "CSG2")
    for name in ("value", "cost_basis", "average_price", "fx_profit", "price_profit",
                 "unrealised_profit", "total_profit"):  # fmt: skip
        assert getattr(czk, name) == pytest.approx(getattr(eur, name)), name
    assert czk.value == pytest.approx(10 * 16 * 24)
    assert czk.average_price == pytest.approx(14)  # in EUR, comparable with the price
    assert czk.fx_profit == pytest.approx(140 * (24 - 25))
    assert czk.price_profit == pytest.approx(10 * (16 - 14) * 24)
    assert checks.run_checks(data, day(10)) == []


def test_overview_of_a_manually_valued_instrument(book):
    save = book.instrument("SAVE", type="savings", valuation=V.MANUAL)
    book.tx(save, day(1), K.DEPOSIT, amount=1000, currency="CZK", fx_rate=1)
    repo.set_valuation(book.conn, Valuation(save, day(5), D("1010")))
    book.tx(save, day(5), K.DEPOSIT, amount=500, currency="CZK", fx_rate=1)  # same day: on top
    book.tx(save, day(7), K.WITHDRAWAL, amount=200, currency="CZK", fx_rate=1)
    book.tx(save, day(8), K.FEE, fee=35)
    data = book.load()

    row = only(overview(data, day(10)), "SAVE")
    assert (row.quantity, row.last_price, row.average_price) == (None, None, None)
    assert row.value == pytest.approx(1010 + 500 - 200)
    assert (row.invested, row.returned, row.fees) == (1500, 200, 35)
    assert row.total_profit == pytest.approx(10)
    assert row.price_profit == pytest.approx(10)
    assert row.net_profit == pytest.approx(-25)
    assert row.cost_basis == pytest.approx(1300)  # money still in
    assert row.unrealised_profit == pytest.approx(10)
    assert row.realised_profit is None
    # Before any valuation exists the value is simply the money put in.
    assert only(overview(data, day(3)), "SAVE").value == pytest.approx(1000)


def test_split_scales_quantity_and_keeps_average_price_comparable(book):
    stock = book.instrument("NFLX")
    # Downloaded prices are already in post-split units for every day.
    book.prices(stock, {day(2): 100, day(6): 105, day(10): 110})
    book.buy(stock, day(2), 1, 1000)
    book.tx(stock, day(6), K.SPLIT, split_ratio=10)
    data = book.load()

    row = only(overview(data, day(10)), "NFLX")
    assert row.quantity == pytest.approx(10)
    assert row.average_price == pytest.approx(100)
    assert row.cost_basis == pytest.approx(1000)
    book.sell(stock, day(8), 4, 105)  # after the split: four of the ten new units
    sold = only(overview(book.load(), day(10)), "NFLX")
    assert sold.realised_profit == pytest.approx(4 * 105 - 400)
    assert (sold.quantity, sold.cost_basis) == (pytest.approx(6), pytest.approx(600))
    assert row.value == pytest.approx(1100)
    history = timeseries.instrument_daily(data, stock, day(10))
    assert [p.value for p in history if p.date in (day(3), day(6))] == pytest.approx([1000, 1050])


def test_missing_price_or_rate_gives_unknown_value(book):
    no_price = book.instrument("NOPRICE")
    no_rate = book.instrument("NORATE", "PLN")
    sold_out = book.instrument("SOLD")
    book.buy(no_price, day(2), 1, 100)
    book.buy(no_rate, day(2), 1, 100, "PLN", 5)
    book.prices(no_rate, {day(2): 100})
    book.buy(sold_out, day(2), 1, 100)
    book.sell(sold_out, day(3), 1, 120)
    rows = overview(book.load(), day(10))

    for ticker in ("NOPRICE", "NORATE"):
        row = only(rows, ticker)
        assert (row.value, row.total_profit, row.net_profit) == (None, None, None)
    assert only(rows, "SOLD").value == 0  # nothing held, so no price is needed
    assert only(rows, "SOLD").total_profit == pytest.approx(20)
    total = summarize(rows)["total"]
    assert total["missing"] == ["NOPRICE", "NORATE"]
    assert total["invested"] == pytest.approx(700)


def test_inactive_and_empty_instruments_are_left_out(book):
    active = book.instrument("A")
    inactive = book.instrument("B", active=False)
    book.instrument("EMPTY")
    for instrument in (active, inactive):
        book.buy(instrument, day(2), 1, 100)
        book.prices(instrument, {day(2): 100})
    data = book.load()
    assert [r.ticker for r in overview(data, day(3))] == ["A"]
    assert [r.ticker for r in overview(data, day(3), include_inactive=True)] == ["A", "B"]


def test_summarize_by_type(book):
    for ticker, type_, price in (("A", "stock", 110), ("B", "stock", 120), ("C", "crypto", 90)):
        instrument = book.instrument(ticker, type=type_)
        book.buy(instrument, day(2), 1, 100)
        book.prices(instrument, {day(3): price})
    groups = summarize(overview(book.load(), day(3)), key=lambda row: row.type)
    assert groups["stock"]["value"] == pytest.approx(230)
    assert groups["stock"]["total_profit"] == pytest.approx(30)
    assert groups["crypto"]["total_profit"] == pytest.approx(-10)


def test_cash_without_a_known_rate_is_reported(book):
    save = book.instrument("PLNSAVE", "PLN", type="savings", valuation=V.MANUAL)
    book.tx(save, day(1), K.DEPOSIT, amount=100, currency="PLN")
    data = book.load()
    assert len(data.warnings) == 1 and "PLN" in data.warnings[0]


def test_cash_without_a_stored_rate_uses_the_market_rate_of_the_day(book):
    stock = book.instrument("AAPL", "USD", dividend_currency="USD")
    book.fx("USD", {day(1): 20, day(8): 23})
    book.prices(stock, {day(2): 100})
    book.buy(stock, day(2), 1, 100, "USD", 20)
    book.tx(stock, day(9), K.DIVIDEND, amount=2, currency="USD")
    data = book.load()
    assert not data.warnings
    assert only(overview(data, day(10)), "AAPL").dividends == pytest.approx(46)


# --- time series ----------------------------------------------------------------------------


@pytest.fixture
def two_buys(book):
    """One share at 100 on day 1, another at 110 on day 3; price ends at 121."""
    stock = book.instrument("X")
    book.prices(stock, {day(1): 100, day(2): 110, day(4): 121})
    book.buy(stock, day(1), 1, 100)
    book.buy(stock, day(3), 1, 110)
    return stock


def test_daily_history(book, two_buys):
    history = timeseries.instrument_daily(book.load(), two_buys, day(4))
    assert [p.date for p in history] == [day(1), day(2), day(3), day(4)]
    assert [p.value for p in history] == pytest.approx([100, 110, 220, 242])
    assert [p.put_in for p in history] == pytest.approx([100, 0, 110, 0])
    assert [p.invested for p in history] == pytest.approx([100, 100, 210, 210])
    assert [p.profit for p in history] == pytest.approx([0, 10, 10, 32])
    assert timeseries.instrument_daily(book.load(), two_buys, date(2023, 12, 31)) == []


def test_history_counts_fees_and_dividends_as_income(book, two_buys):
    book.tx(two_buys, day(2), K.DIVIDEND, amount=7, currency="CZK", fx_rate=1)
    book.tx(two_buys, day(4), K.FEE, fee=3)
    last = timeseries.instrument_daily(book.load(), two_buys, day(4))[-1]
    assert last.income == pytest.approx(4)
    assert last.profit == pytest.approx(32)
    assert last.net_profit == pytest.approx(36)
    assert (last.put_in, last.taken_out) == (3, 0)


def test_value_is_carried_at_cost_until_the_first_price(book):
    stock = book.instrument("LATE")
    book.prices(stock, {day(3): 120})
    book.buy(stock, day(1), 1, 100)
    data = book.load()
    history = timeseries.instrument_daily(data, stock, day(3))
    assert [p.value for p in history] == pytest.approx([100, 100, 120])
    assert performance.twr(history) == pytest.approx(0.2)


def test_combine_aligns_different_histories(book, two_buys):
    other = book.instrument("Y")
    book.prices(other, {day(1): 50})
    book.buy(other, day(2), 2, 50)
    data = book.load()
    first = timeseries.instrument_daily(data, two_buys, day(4))
    second = timeseries.instrument_daily(data, other, day(3))  # ends a day earlier
    total = timeseries.combine([first, second])
    assert [p.value for p in total] == pytest.approx([100, 210, 320, 342])
    assert [p.put_in for p in total] == pytest.approx([100, 100, 110, 0])
    assert total[-1].invested == pytest.approx(310)
    assert timeseries.combine([]) == []
    assert set(timeseries.all_daily(data, day(4))) == {two_buys, other}


# --- returns --------------------------------------------------------------------------------


def test_twr_ignores_the_timing_of_new_money(book, two_buys):
    # Price went 100 -> 110 -> 110 -> 121: +10 % twice, whatever was bought when.
    history = timeseries.instrument_daily(book.load(), two_buys, day(4))
    assert performance.twr(history) == pytest.approx(0.21)
    assert performance.twr(history, start=day(3)) == pytest.approx(0.1)
    assert performance.twr(history, end=day(2)) == pytest.approx(0.1)
    assert performance.twr(history, start=day(20)) is None


def test_twr_counts_new_money_from_the_price_it_was_invested_at(book):
    stock = book.instrument("X")
    book.prices(stock, {day(1): 100, day(2): 100, day(3): 90, day(5): 99})
    book.buy(stock, day(1), 1, 100)
    book.buy(stock, day(3), 100, 90)  # far more money, at the day's low
    history = timeseries.instrument_daily(book.load(), stock, day(5))

    assert history[2].early_gain == pytest.approx(-10)  # the old unit, 100 -> 90
    levels = dict(performance.growth(history))
    assert levels[day(3)] == pytest.approx(0.9)  # not watered down by the purchase
    assert performance.twr(history) == pytest.approx(99 / 100 - 1)  # the price, exactly

    # A purchase away from the close: the old unit moves with the price, the new one
    # earns from what was paid for it.
    other = book.instrument("Y")
    book.prices(other, {day(1): 100, day(3): 120})
    book.buy(other, day(1), 1, 100)
    book.buy(other, day(3), 1, 110)
    history = timeseries.instrument_daily(book.load(), other, day(3))
    assert performance.twr(history) == pytest.approx(110 / 100 * 240 / 220 - 1)

    # Selling everything at a price: the whole move up to that price counts.
    book.sell(other, day(4), 2, 150)
    history = timeseries.instrument_daily(book.load(), other, day(5))
    assert performance.twr(history) == pytest.approx(150 / 100 - 1)
    both = timeseries.combine([history, timeseries.instrument_daily(book.load(), stock, day(5))])
    assert both[2].early_gain == pytest.approx(-10 + 10)


def test_twr_survives_selling_everything(book, two_buys):
    book.sell(two_buys, day(5), 2, 121)
    history = timeseries.instrument_daily(book.load(), two_buys, day(6))
    assert history[-1].value == 0
    assert performance.twr(history) == pytest.approx(0.21)


def test_twr_includes_dividends_and_fees(book):
    stock = book.instrument("DIV")
    book.prices(stock, {day(1): 100})
    book.buy(stock, day(1), 1, 100)
    book.tx(stock, day(2), K.DIVIDEND, amount=5, currency="CZK", fx_rate=1)
    data = book.load()
    assert performance.twr(timeseries.instrument_daily(data, stock, day(3))) == pytest.approx(0.05)

    costly = book.instrument("FEE")
    book.prices(costly, {day(1): 100})
    book.buy(costly, day(1), 1, 100, fee=25)  # paid 125 for something worth 100
    data = book.load()
    assert performance.twr(timeseries.instrument_daily(data, costly, day(3))) == pytest.approx(-0.2)


def test_drawdown_ignores_new_money(book):
    stock = book.instrument("X")
    book.prices(stock, {day(1): 100, day(3): 120, day(5): 90, day(6): 96, day(8): 130, day(9): 117})
    book.buy(stock, day(1), 1, 100)
    book.buy(stock, day(4), 10, 120)  # a lot of new money just before the fall
    history = timeseries.instrument_daily(book.load(), stock, day(9))

    levels = dict(performance.growth(history))
    assert levels[day(3)] == pytest.approx(1.2)
    assert levels[day(5)] == pytest.approx(0.9)
    assert levels[day(9)] == pytest.approx(1.17)
    assert levels[day(9)] - 1 == pytest.approx(performance.twr(history))

    result = performance.drawdown(history)
    assert result.deepest == pytest.approx(90 / 120 - 1)
    # The high is held for two days; the drop is counted from the last of them.
    assert (result.peak, result.trough, result.recovered) == (day(4), day(5), day(8))
    assert result.current == pytest.approx(117 / 130 - 1)
    assert dict(performance.drops(history))[day(6)] == pytest.approx(96 / 120 - 1)

    # Within a period the high is counted from the period's start.
    late = performance.drawdown(history, start=day(6))
    assert late.deepest == pytest.approx(-0.10)
    assert (late.peak, late.trough, late.recovered) == (day(8), day(9), None)
    assert performance.drawdown(history, start=date(2030, 1, 1)) is None


def test_drawdown_of_something_that_only_rose(book):
    stock = book.instrument("X")
    book.prices(stock, {day(1): 100, day(3): 120})
    book.buy(stock, day(1), 1, 100)
    result = performance.drawdown(timeseries.instrument_daily(book.load(), stock, day(4)))
    assert (result.deepest, result.peak, result.trough, result.current) == (0.0, None, None, 0.0)


def test_xirr():
    assert performance.xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), 1100)]) == pytest.approx(
        0.10, abs=1e-6
    )
    # Two payments of 1000, half a year apart, worth 2200 after a year.
    rate = performance.xirr(
        [(date(2023, 1, 1), -1000), (date(2023, 7, 2), -1000), (date(2024, 1, 1), 2200)]
    )
    assert 1000 * (1 + rate) + 1000 * (1 + rate) ** (183 / 365) == pytest.approx(2200)
    assert performance.xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), 500)]) == pytest.approx(
        -0.5, abs=1e-6
    )
    assert performance.xirr([(date(2023, 1, 1), -1000), (date(2023, 1, 11), 2000)]) > 1000
    assert performance.xirr([]) is None
    assert performance.xirr([(date(2023, 1, 1), -1000), (date(2024, 1, 1), -5)]) is None


def test_money_weighted_return(book):
    stock = book.instrument("X")
    book.prices(stock, {date(2023, 1, 1): 1000, date(2024, 1, 1): 1100})
    book.buy(stock, date(2023, 1, 1), 1, 1000)
    history = timeseries.instrument_daily(book.load(), stock, date(2024, 1, 1))
    assert performance.money_weighted(history) == pytest.approx(0.10, abs=1e-6)
    # From mid-2023 the holding is treated as bought for its value on the day before.
    assert performance.money_weighted(history, start=date(2023, 7, 1)) == pytest.approx(
        1.1 ** (365 / 184) - 1, abs=1e-6
    )
    assert performance.money_weighted(history, start=date(2030, 1, 1)) is None


def test_yearly_rows_add_up_to_the_net_profit(book):
    stock = book.instrument("X")
    book.prices(stock, {date(2023, 6, 1): 100, date(2023, 12, 31): 120, date(2024, 3, 1): 150})
    book.buy(stock, date(2023, 6, 1), 2, 100, fee=4)
    book.tx(stock, date(2024, 2, 1), K.DIVIDEND, amount=10, currency="CZK", fx_rate=1)
    book.sell(stock, date(2024, 3, 1), 1, 150)
    history = timeseries.instrument_daily(book.load(), stock, date(2024, 3, 2))

    first, second = performance.yearly(history)
    assert (first.year, first.start_value, first.end_value) == (2023, 0, 240)
    assert (first.put_in, first.taken_out) == (204, 0)
    assert first.profit == pytest.approx(36)  # 240 - 204
    assert first.twr == pytest.approx(240 / 204 - 1)
    assert (second.year, second.start_value, second.end_value) == (2024, 240, 150)
    assert second.taken_out == pytest.approx(160)
    assert second.profit == pytest.approx(70)  # 150 - 240 + 160
    assert second.twr == pytest.approx((250 / 240) * (300 / 240) - 1)
    assert first.profit + second.profit == pytest.approx(history[-1].net_profit)


def test_benchmark_price_return(book):
    index = book.instrument("SPX", "USD", type="benchmark")
    book.prices(index, {day(1): 100, day(10): 120})
    book.fx("USD", {day(1): 20, day(10): 22})
    data = book.load()
    assert performance.holding_return(data, index, day(1), day(10)) == pytest.approx(0.32)
    assert performance.holding_return(data, index, date(2023, 1, 1), day(10)) is None
    assert index not in data.instrument_ids()  # no transactions, so not part of the portfolio


def test_benchmark_return_reinvests_dividends(book):
    index = book.instrument("SPX", type="benchmark")
    repo.save_prices(
        book.conn,
        [
            Price(index, day(1), close=100),
            Price(index, day(5), close=100, dividend=5),
            Price(index, day(10), close=110),
        ],
    )
    data = book.load()
    assert performance.holding_return(data, index, day(1), day(10)) == pytest.approx(
        1.05 * 1.10 - 1
    )
    # A dividend on the first day belongs to whoever held it before.
    assert performance.holding_return(data, index, day(5), day(10)) == pytest.approx(0.10)


def test_same_money_in_the_benchmark(book):
    stock = book.instrument("X")
    index = book.instrument("SPX", type="benchmark")
    book.prices(stock, {day(1): 100, day(10): 100})
    book.prices(index, {day(3): 50, day(5): 100, day(10): 200})
    book.buy(stock, day(1), 10, 100)  # 1000, waits as cash until the index has a price
    book.buy(stock, day(5), 5, 100)  # 500
    book.sell(stock, day(8), 4, 100)  # 400 out
    data = book.load()
    history = timeseries.instrument_daily(data, stock, day(10))

    twin = performance.same_money(data, index, history)
    by_day = {p.date: p for p in twin}
    assert by_day[day(2)].value == pytest.approx(1000)
    assert by_day[day(3)].value == pytest.approx(1000)  # 20 units at 50
    assert by_day[day(5)].value == pytest.approx(25 * 100)
    assert by_day[day(8)].value == pytest.approx(21 * 100)
    assert twin[-1].value == pytest.approx(21 * 200)
    assert twin[-1].invested == pytest.approx(1100)
    assert [p.put_in for p in twin] == [p.put_in for p in history]

    # From day 6 on: what the portfolio was worth the day before goes in first.
    later = performance.same_money(data, index, history, start=day(6))
    assert later[0].put_in == pytest.approx(1500)
    assert later[-1].value == pytest.approx((15 - 4) * 200)
    assert performance.twr(later) == pytest.approx(1.0)
    assert performance.same_money(data, index, history, start=date(2030, 1, 1)) == []


def test_sales_list_what_each_one_realised(book):
    stock = book.instrument("X", "USD")
    save = book.instrument("SAVE", type="savings", valuation=V.MANUAL)
    book.buy(stock, day(1), 2, 100, "USD", 20)  # 4000
    book.buy(stock, day(11), 2, 110, "USD", 20)  # 4400
    book.sell(stock, day(21), 3, 150, "USD", 22)  # 9900 for units that cost 4000 + 2200
    book.tx(save, day(1), K.DEPOSIT, amount=100, currency="CZK", fx_rate=1)
    book.tx(save, day(2), K.WITHDRAWAL, amount=50, currency="CZK", fx_rate=1)
    data = book.load()

    (sale,) = sales(data, day(30))
    assert (sale.date, sale.ticker, sale.quantity) == (day(21), "X", 3)
    assert (sale.proceeds, sale.cost, sale.profit) == pytest.approx((9900, 6200, 3700))
    assert sale.held_days == pytest.approx((2 * 20 + 1 * 10) / 3)
    assert sale.profit == pytest.approx(only(overview(data, day(30)), "X").realised_profit)
    assert sales(data, day(20)) == []


def test_invested_by_period(book):
    stock = book.instrument("X", "USD")
    coin = book.instrument("C", type="crypto")
    old = book.instrument("OLD", active=False)
    book.buy(stock, date(2023, 3, 1), 1, 100, "USD", 20)  # 2000
    book.sell(stock, date(2024, 1, 5), 1, 50, "USD", 22)  # -1100
    book.buy(coin, date(2024, 1, 20), 2, 300)  # 600
    book.tx(coin, date(2024, 2, 1), K.STAKING_REWARD, quantity=1)
    book.buy(old, date(2024, 2, 1), 1, 999)
    data = book.load()

    assert performance.invested_by_period(data) == [
        {"period": "2023", "total": 2000, "stock": 2000},
        {"period": "2024", "total": -500, "crypto": 600, "stock": -1100},
    ]
    months = performance.invested_by_period(data, "month", include_inactive=True)
    assert [row["period"] for row in months] == ["2023-03", "2024-01", "2024-02"]
    assert months[2] == {"period": "2024-02", "total": 999, "stock": 999}
    with pytest.raises(ValueError):
        performance.invested_by_period(data, "week")


def test_thin_keeps_both_ends_and_even_spacing():
    points = list(range(1000))
    kept, spacing = timeseries.thin(points, 100)
    assert spacing == 10
    assert kept[0] == 0 and kept[-1] == 999
    assert len(kept) <= 101
    assert {b - a for a, b in zip(kept[1:], kept[2:], strict=False)} == {10}

    assert timeseries.thin(points, 1000) == (points, 1)
    assert timeseries.thin(points, 5000) == (points, 1)
    assert timeseries.thin([], 100) == ([], 1)
    kept, spacing = timeseries.thin(list(range(401)), 400)
    assert spacing == 2 and kept[0] == 0 and kept[-1] == 400 and len(kept) == 201


def test_lots_still_held(book):
    stock = book.instrument("X", "USD")
    book.prices(stock, {day(30): 150})
    book.fx("USD", {day(30): 22})
    book.buy(stock, day(1), 2, 100, "USD", 20)
    book.buy(stock, day(11), 2, 110, "USD", 20)
    book.tx(stock, day(12), K.STAKING_REWARD, quantity=1)
    book.sell(stock, day(21), 3, 150, "USD", 22)
    data = book.load()

    bought, reward = lots(data, day(30))
    assert (bought.ticker, bought.date, bought.age_days) == ("X", day(11), 19)
    assert (bought.quantity, bought.cost) == pytest.approx((1, 2200))
    assert (bought.value, bought.profit) == pytest.approx((3300, 1100))
    assert (reward.staking, reward.cost, reward.value) == (True, 0, pytest.approx(3300))
    assert sum(row.cost for row in lots(data, day(30))) == pytest.approx(
        only(overview(data, day(30)), "X").cost_basis
    )
    assert [row.value for row in lots(data, day(15))] == [None, None, None]  # no price yet


def test_monthly_returns_multiply_to_the_whole(book):
    stock = book.instrument("X")
    book.prices(
        stock,
        {day(1): 100, day(31): 110, day(29, 2): 99, date(2025, 1, 1): 99, date(2025, 1, 31): 198},
    )
    book.buy(stock, day(1), 1, 100)
    book.buy(stock, day(10, 2), 5, 110)
    history = timeseries.instrument_daily(book.load(), stock, date(2025, 1, 31))

    months = performance.monthly(history)
    assert months[2024][1] == pytest.approx(0.10)
    assert months[2024][2] == pytest.approx(-0.10)
    assert months[2024][7] == pytest.approx(0)
    assert months[2025] == {1: pytest.approx(1.0)}
    whole = 1.0
    for year in months.values():
        for value in year.values():
            whole *= 1 + value
    assert whole - 1 == pytest.approx(performance.twr(history))


def paying_stock(book):
    stock = book.instrument("X", "USD")
    repo.save_prices(
        book.conn,
        [
            Price(stock, date(2023, 1, 2), close=100),
            Price(stock, date(2023, 3, 1), close=100, dividend=1.0),
            Price(stock, date(2023, 6, 1), close=100, dividend=1.0),
            Price(stock, date(2023, 9, 1), close=100, dividend=0.5),  # after a 2:1 split
            Price(stock, date(2024, 3, 1), close=100, dividend=0.5),
        ],
    )
    book.fx("USD", {date(2023, 1, 2): 20})
    book.buy(stock, date(2023, 3, 1), 10, 100, "USD", 20)  # bought on the day: too late
    book.tx(stock, date(2023, 6, 20), K.DIVIDEND, amount=8.5, currency="USD", fx_rate=20, tax=1.5)
    book.tx(stock, date(2023, 7, 1), K.SPLIT, split_ratio=2)
    book.tx(stock, date(2023, 9, 20), K.DIVIDEND, amount=8.5, currency="USD", fx_rate=20, tax=1.5)
    return stock


def test_expected_dividends_follow_the_units_held(book):
    stock = paying_stock(book)
    data = book.load()
    found = dividends.expected(data, stock, date(2024, 12, 31))
    assert [(e.date, e.quantity, e.gross) for e in found] == [
        (date(2023, 6, 1), 20, 400),  # 10 units then, 20 as counted today
        (date(2023, 9, 1), 20, 200),
        (date(2024, 3, 1), 20, 200),
    ]
    assert dividends.expected(data, stock, date(2023, 8, 1)) == found[:1]


def test_dividends_by_year_and_instrument(book):
    stock = paying_stock(book)
    quiet = book.instrument("Q")
    book.buy(quiet, date(2023, 1, 2), 1, 10)
    data = book.load()
    today = date(2024, 12, 31)

    this_year, last_year = dividends.by_year(data, [stock, quiet], today)
    assert (last_year.year, last_year.ticker, last_year.payments) == (2023, "X", 2)
    assert (last_year.received, last_year.tax) == pytest.approx((340, 60))
    assert (last_year.expected, last_year.expected_payments) == (pytest.approx(600), 2)
    assert (this_year.year, this_year.received, this_year.payments) == (2024, 0, 0)
    assert (this_year.expected, this_year.expected_payments) == (pytest.approx(200), 1)

    (row,) = dividends.by_instrument(data, [stock, quiet], today)
    assert (row.ticker, row.payments, row.missing) == ("X", 2, 1)
    assert (row.received, row.tax, row.last_year) == pytest.approx((340, 60, 0))
    # A dividend reported in the last two months may not have been paid out yet.
    assert dividends.by_instrument(data, [stock], date(2024, 3, 20))[0].missing == 0


def test_checks_find_what_looks_wrong(book):
    today = date(2024, 6, 30)
    stock = paying_stock(book)  # one dividend not recorded
    book.fx("USD", {date(2024, 1, 10): 22})
    book.buy(stock, date(2024, 1, 10), 1, 130, "USD", 22)  # 30 % above the close
    book.buy(stock, date(2024, 1, 11), 1, 100, "USD", 24)  # rate 9 % off
    dust = book.instrument("DUST")
    book.prices(dust, {today: 10})
    book.buy(dust, day(1), 1000, 10)
    book.sell(dust, day(2), 999.5, 10)
    short = book.instrument("SHORT")
    book.prices(short, {today: 10})
    book.buy(short, day(1), 1, 10)
    book.sell(short, day(2), 2, 10)
    save = book.instrument("SAVE", type="savings", valuation=V.MANUAL)
    book.tx(save, day(5), K.DEPOSIT, amount=500, currency="CZK", fx_rate=1)
    repo.set_valuation(book.conn, Valuation(save, day(5), D("1000")))

    found = {(f.check, f.ticker) for f in checks.run_checks(book.load(), today)}
    assert found == {
        (checks.STALE_PRICE, "X"),  # newest price and newest rate
        (checks.PRICE_OFF, "X"),
        (checks.RATE_OFF, "X"),
        (checks.DIVIDENDS, "X"),
        (checks.LEFTOVER, "DUST"),
        (checks.OVERSOLD, "SHORT"),
        (checks.STALE_VALUATION, "SAVE"),
        (checks.SAME_DAY, "SAVE"),
    }
    assert {f.check for f in checks.run_checks(book.load(), today)} <= set(checks.EXPLANATIONS)


def test_checks_are_quiet_about_healthy_data(book):
    stock = book.instrument("X")
    book.prices(stock, {day(1): 100, day(9): 104})
    book.buy(stock, day(1), 1, 101)
    assert checks.run_checks(book.load(), day(10)) == []


def test_a_checked_finding_comes_back_only_when_it_changes(book):
    dust = book.instrument("DUST")
    book.prices(dust, {day(1): 10, day(9): 10})
    book.buy(dust, day(1), 1000, 10)
    book.sell(dust, day(2), 999.5, 10)
    (finding,) = checks.run_checks(book.load(), day(10))
    assert finding.instrument_id == dust

    repo.mark_finding_reviewed(book.conn, finding.identity, day(10))
    repo.mark_finding_reviewed(book.conn, finding.identity, day(11))  # twice is fine
    assert repo.list_reviewed_findings(book.conn) == {finding.identity}
    # Another price changes what the leftover is worth, not what it is.
    book.prices(dust, {day(10): 12})
    (same,) = checks.run_checks(book.load(), day(10))
    assert same.detail != finding.detail and same.identity == finding.identity
    # Another quantity is another finding.
    book.sell(dust, day(3), 0.1, 10)
    (changed,) = checks.run_checks(book.load(), day(10))
    assert changed.identity not in repo.list_reviewed_findings(book.conn)

    repo.unmark_finding_reviewed(book.conn, finding.identity)
    assert repo.list_reviewed_findings(book.conn) == set()


def test_allocation_against_targets():
    rows = allocation({"stock": 700, "etf": 200, "crypto": 100}, {"stock": 0.5, "etf": 0.5})
    by_name = {row.name: row for row in rows}
    assert by_name["stock"].share == pytest.approx(0.7)
    assert by_name["stock"].to_target == pytest.approx(-200)
    assert by_name["etf"].to_target == pytest.approx(300)
    assert (by_name["crypto"].target, by_name["crypto"].to_target) == (0, -100)
    assert sum(row.to_target for row in rows) == pytest.approx(0)
    assert all(row.buy == 0 for row in rows)


def test_new_money_goes_to_what_is_below_its_target():
    targets = {"stock": 0.5, "etf": 0.3, "gold": 0.2}
    values = {"stock": 700, "etf": 200, "gold": 100}
    # After 200 more the targets are 600 / 360 / 240: etf is 160 short, gold 140.
    buy = {row.name: row.buy for row in allocation(values, targets, 200)}
    assert buy == pytest.approx({"stock": 0, "etf": 200 * 160 / 300, "gold": 200 * 140 / 300})
    # Enough money to get everything on target exactly.
    buy = {row.name: row.buy for row in allocation(values, targets, 1000)}
    assert buy == pytest.approx({"stock": 300, "etf": 400, "gold": 300})
    # Nothing held yet, or everything on target: by the targets.
    assert {r.name: r.buy for r in allocation({}, targets, 100)} == pytest.approx(
        {"stock": 50, "etf": 30, "gold": 20}
    )
    assert [r.share for r in allocation({}, targets)] == [None, None, None]


def test_targets_are_stored_and_have_to_add_up(book):
    repo.set_targets(book.conn, {"stock": D("60"), "crypto": D("40"), "savings": D("0")})
    assert repo.list_targets(book.conn) == {"crypto": D("40"), "stock": D("60")}
    with pytest.raises(ValueError, match="add up to 100"):
        repo.set_targets(book.conn, {"stock": D("60")})
    with pytest.raises(ValueError, match="negative"):
        repo.set_targets(book.conn, {"stock": D("110"), "crypto": D("-10")})
    assert repo.list_targets(book.conn) == {"crypto": D("40"), "stock": D("60")}
    repo.set_targets(book.conn, {})
    assert repo.list_targets(book.conn) == {}


def test_tax_rules_count_the_holding_period_in_calendar_years():
    rules = taxes.TaxRules(holding_years=3)
    assert rules.exempt_from(date(2021, 5, 10)) == date(2024, 5, 11)
    assert rules.exempt_from(date(2020, 2, 29)) == date(2023, 3, 1)
    assert rules.group("crypto") == taxes.CRYPTO
    assert rules.group("etf") == taxes.SECURITIES


def tax_book(book):
    stock = book.instrument("X")
    coin = book.instrument("C", type="crypto")
    save = book.instrument("SAVE", type="savings", valuation=V.MANUAL)
    book.prices(stock, {date(2024, 12, 31): 300})
    book.prices(coin, {date(2024, 3, 1): 50, date(2024, 12, 31): 60})
    book.buy(stock, date(2021, 5, 10), 10, 100)
    book.buy(stock, date(2023, 6, 1), 10, 200)
    book.sell(stock, date(2024, 5, 10), 4, 250)  # exactly three years: not yet longer
    book.sell(stock, date(2024, 5, 11), 8, 250)  # 6 old units and 2 new ones
    book.tx(stock, date(2024, 7, 1), K.DIVIDEND, amount=85, currency="USD", fx_rate=20, tax=15)
    book.buy(coin, date(2024, 1, 5), 100, 40)
    book.tx(coin, date(2024, 3, 1), K.STAKING_REWARD, quantity=2)
    book.tx(coin, date(2024, 3, 2), K.STAKING_CORRECTION, quantity=0.5)
    book.sell(coin, date(2024, 6, 1), 10, 45)
    book.tx(save, date(2024, 1, 1), K.DEPOSIT, amount=1000, currency="CZK", fx_rate=1)
    book.tx(save, date(2024, 2, 1), K.WITHDRAWAL, amount=500, currency="CZK", fx_rate=1)
    return book.load(), [stock, coin, save]


def test_sales_for_tax_are_split_by_the_purchases_they_used(book):
    data, ids = tax_book(book)
    rules = taxes.TaxRules(holding_years=3, proceeds_limit=2500)
    parts = taxes.sales(data, ids, 2024, rules)
    assert [(p.date.day, p.ticker, p.acquired.year, p.quantity, p.long_held) for p in parts] == [
        (10, "X", 2021, 4, False),
        (11, "X", 2021, 6, True),
        (11, "X", 2023, 2, False),
        (1, "C", 2024, 10, False),
    ]
    assert [(p.proceeds, p.cost, p.profit) for p in parts[:3]] == [
        (1000, 400, 600), (1500, 600, 900), (500, 400, 100),
    ]  # fmt: skip
    assert taxes.sales(data, ids, 2023, rules) == []

    securities, crypto = taxes.summary(parts, rules)
    assert (securities.group, securities.proceeds, securities.profit) == ("securities", 3000, 1600)
    assert (securities.long_proceeds, securities.long_profit) == (1500, 900)
    assert (securities.short_proceeds, securities.short_profit) == (1500, 700)
    assert (securities.under_limit, securities.not_exempt) == (False, 700)
    # The coins: 450 received, under the limit, so nothing is left to tax.
    assert (crypto.proceeds, crypto.under_limit, crypto.not_exempt) == (450, True, 0)
    assert taxes.years(data, ids) == [2024]


def test_dividends_and_staking_for_tax(book):
    data, ids = tax_book(book)
    (dividend,) = taxes.dividends(data, ids, 2024)
    assert (dividend.ticker, dividend.currency, dividend.payments) == ("X", "USD", 1)
    assert (dividend.net, dividend.tax, dividend.gross) == (1700, 300, 2000)
    (reward,) = taxes.staking(data, ids, 2024)
    assert (reward.ticker, reward.quantity, reward.value) == ("C", 1.5, pytest.approx(75))
    assert taxes.dividends(data, ids, 2023) == taxes.staking(data, ids, 2023) == []


def test_what_could_be_sold_exempt_today(book):
    stock = book.instrument("X")
    book.prices(stock, {date(2024, 12, 31): 300})
    book.buy(stock, date(2020, 5, 10), 10, 100)
    book.buy(stock, date(2023, 6, 1), 5, 200)
    book.buy(stock, date(2024, 6, 1), 1, 200)
    (row,) = taxes.held(book.load(), [stock], date(2024, 12, 31), taxes.TaxRules())
    assert (row.long_quantity, row.long_value, row.long_profit) == (10, 3000, 2000)
    assert (row.short_quantity, row.short_value, row.short_profit) == (6, 1800, 600)
    assert (row.next_exempt, row.next_quantity) == (date(2026, 6, 2), 5)
