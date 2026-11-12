"""Analytics checked against numbers worked out by hand. Base currency is CZK."""

from datetime import date
from decimal import Decimal as D

import pytest

from portfolio.core import repo
from portfolio.core.analytics import performance, timeseries
from portfolio.core.analytics.data import Series, load_data
from portfolio.core.analytics.overview import overview, sales, summarize
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
    assert row.fx_profit == pytest.approx(3000 * 26 + 3300 * 22 - 141000)  # 9600
    assert row.rewards == pytest.approx(0.01 * 40000 * 26)  # 10400
    assert row.price_profit == pytest.approx(57400)
    assert row.average_price == pytest.approx((3000 * 26 + 3300 * 22) / (26 * 0.2))


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
