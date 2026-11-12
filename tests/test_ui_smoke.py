"""Every page renders on a small portfolio, and the main actions work."""

from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from portfolio.core import db, repo
from portfolio.core.config import CONFIG_ENV_VAR
from portfolio.core.models import FxRate, Instrument, Price, Transaction, Valuation
from portfolio.core.models import TransactionKind as K
from portfolio.core.models import ValuationMethod as V
from portfolio.core.providers.base import Bar, ProviderError
from portfolio.ui import common

ROOT = Path(__file__).parent.parent
APP = str(ROOT / "src" / "portfolio" / "ui" / "app.py")
TIMEOUT = 20


@pytest.fixture
def database(tmp_path, monkeypatch):
    """A config file and a database with one stock and one savings account."""
    path = tmp_path / "p.db"
    (tmp_path / "config.toml").write_text(
        'db = "p.db"\nbase_currency = "CZK"\nlocale = "cs"\nbenchmark = "SPY"\n'
    )
    monkeypatch.setenv(CONFIG_ENV_VAR, str(tmp_path / "config.toml"))
    st.cache_resource.clear()

    conn = db.connect(path)
    db.migrate(conn)
    for code in ("CZK", "USD"):
        repo.add_currency(conn, code)
    for name in ("stock", "savings", "benchmark"):
        repo.add_instrument_type(conn, name)

    def add(ticker, type_, currency, valuation=V.YAHOO):
        return repo.add_instrument(
            conn, Instrument(ticker=ticker, type=type_, currency=currency, valuation=valuation)
        ).id

    aapl = add("AAPL", "stock", "USD")
    save = add("SAVE", "savings", "CZK", V.MANUAL)
    spy = add("SPY", "benchmark", "USD")
    repo.add_transaction(
        conn,
        Transaction(
            date(2023, 1, 2),
            aapl,
            K.BUY,
            quantity=D(2),
            price=D(100),
            currency="USD",
            fx_rate=D(22),
            fee=D(10),
        ),
    )
    repo.add_transaction(
        conn,
        Transaction(date(2024, 5, 1), aapl, K.DIVIDEND, amount=D(50), currency="CZK", fx_rate=D(1)),
    )
    repo.add_transaction(
        conn,
        Transaction(
            date(2023, 6, 1), save, K.DEPOSIT, amount=D(1000), currency="CZK", fx_rate=D(1)
        ),
    )
    repo.set_valuation(conn, Valuation(save, date(2024, 1, 1), D("1040")))
    for instrument, closes in ((aapl, (100.0, 150.0)), (spy, (400.0, 480.0))):
        repo.save_prices(
            conn,
            [
                Price(instrument, date(2023, 1, 2), closes[0]),
                Price(instrument, date(2024, 6, 3), closes[1]),
            ],
        )
    repo.save_fx_rates(
        conn,
        [
            FxRate(date(2023, 1, 2), "USD", "CZK", 22.0),
            FxRate(date(2024, 6, 3), "USD", "CZK", 23.0),
        ],
    )
    conn.commit()
    yield conn
    conn.close()
    st.cache_resource.clear()


def run_page(name: str) -> AppTest:
    def script(page_name):
        import importlib

        importlib.import_module(f"portfolio.ui.pages.{page_name}").render()

    return AppTest.from_function(script, args=(name,), default_timeout=TIMEOUT).run()


def run_shell() -> AppTest:
    """Sidebar and split notices on their own; the test harness cannot follow a rerun
    through the app's page navigation."""

    def script():
        from portfolio.ui import shell

        shell.sidebar()
        shell.pending_splits()

    return AppTest.from_function(script, default_timeout=TIMEOUT).run()


def clean(at: AppTest) -> AppTest:
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    return at


# --- whole app --------------------------------------------------------------------------------


def test_app_opens_on_the_overview(database):
    at = clean(AppTest.from_file(APP, default_timeout=TIMEOUT).run())
    assert at.title[0].value == "Overview"
    assert "2024-06-03" in at.sidebar.caption[0].value


def test_app_reports_missing_config(monkeypatch, tmp_path):
    st.cache_resource.clear()
    monkeypatch.setenv(CONFIG_ENV_VAR, str(tmp_path / "missing.toml"))
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not at.exception
    assert "not found" in at.error[0].value


def test_update_button_downloads_and_reports(database, monkeypatch):
    class Provider:
        def prices(self, symbol, start):
            if symbol == "SPY":
                raise ProviderError("SPY is unavailable")
            return [Bar(date(2024, 6, 4), 155.0)]

        def fx_rates(self, from_currency, to_currency, start):
            return [Bar(date(2024, 6, 4), 23.5)]

        def currency(self, symbol):
            return "USD"

    monkeypatch.setattr(common, "provider", Provider)
    at = run_shell()
    at.sidebar.button[0].click().run()

    assert not at.exception
    assert "2 series updated" in at.sidebar.success[0].value
    assert "SPY is unavailable" in at.sidebar.error[0].value
    assert "2024-06-04" in at.sidebar.caption[0].value
    database.rollback()
    assert repo.list_prices(database, 1)[-1].close == 155.0


def test_pending_split_can_be_added_from_the_banner(database):
    repo.save_prices(database, [Price(1, date(2024, 3, 1), 120.0, split=4.0)])
    database.commit()
    at = run_shell()
    assert "AAPL" in at.warning[0].value and "4 for 1" in at.warning[0].value
    at.button(key="split_add_1_2024-03-01").click().run()

    assert not at.exception and not at.warning
    database.rollback()
    (split,) = repo.list_transactions(database, kinds=[K.SPLIT])
    assert (split.date, split.split_ratio) == (date(2024, 3, 1), D(4))


# --- pages ------------------------------------------------------------------------------------


def test_overview_page(database):
    at = clean(run_page("overview"))
    labels = {m.label: m.value for m in at.metric}
    # 2 shares x 150 USD x 23 = 6900, plus savings 1040
    assert labels["Value"] == "7\u00a0940"
    assert labels["Dividends"] == "50"
    assert len(at.dataframe) == 4  # by type, by currency, instruments, purchases held
    assert list(at.dataframe[2].value["ticker"]) == ["AAPL", "SAVE"]
    assert list(at.dataframe[2].value["share"]) == pytest.approx([6900 / 7940, 1040 / 7940])


def test_overview_follows_changes_made_outside_the_app(database):
    assert not run_page("overview").info
    database.execute("DELETE FROM transactions")
    database.commit()
    assert "No transactions yet" in run_page("overview").info[0].value


def test_overview_page_with_empty_database(database):
    database.execute("DELETE FROM transactions")
    database.commit()
    at = clean(run_page("overview"))
    assert "No transactions yet" in at.info[0].value


def test_performance_page(database):
    at = clean(run_page("performance"))
    labels = {m.label: m.value for m in at.metric}
    assert labels["Return (time-weighted)"].startswith("+")
    assert labels["SPY return"] == "+25,5 %"  # 480 x 23 / (400 x 22) - 1
    assert "Yearly return of your money in SPY" in labels
    assert any(label.startswith("You are ") for label in labels)
    years = at.dataframe[0].value
    assert list(years["Year"])[:2] == ["2023", "2024"]
    # One instrument only: the per-instrument table disappears.
    at.selectbox(key="performance_scope").select("AAPL").run()
    clean(at)
    at.selectbox(key="performance_period").select("This year").run()
    clean(at)


def test_charts_page(database):
    at = clean(run_page("charts"))
    assert len(at.get("vega_lite_chart")) + len(at.get("arrow_vega_lite_chart")) >= 2
    at.selectbox(key="charts_scope").select("Type: savings").run()
    clean(at)


def test_dividends_page(database):
    at = clean(run_page("dividends"))
    labels = {m.label: m.value for m in at.metric}
    assert labels["Received in total"] == "50"
    assert list(at.dataframe[0].value["Ticker"]) == ["AAPL"]
    database.execute("DELETE FROM transactions WHERE kind = 'dividend'")
    database.commit()
    assert "No dividends recorded" in run_page("dividends").info[0].value


def test_checks_page(database):
    at = clean(run_page("checks"))
    assert [s.value for s in at.subheader] == [
        "Prices out of date (2)",  # AAPL: its price and the USD rate
        "Manual values out of date (1)",
    ]
    assert set(at.dataframe[0].value["Ticker"]) == {"AAPL"}
    database.execute("DELETE FROM transactions")
    database.commit()
    assert run_page("checks").success


def test_findings_can_be_marked_as_checked_and_shown_again(database):
    at = clean(run_page("checks"))
    at.button(key="checks_mark_prices_out_of_date").click().run()
    clean(at)
    assert [s.value for s in at.subheader] == ["Manual values out of date (1)"]
    database.rollback()
    assert len(repo.list_reviewed_findings(database)) == 2
    database.rollback()  # let go of the database again
    at.button(key="checks_mark_manual_values_out_of_date").click().run()
    assert "Nothing to look at" in clean(at).success[0].value
    assert list(at.dataframe[0].value["Ticker"]) == ["AAPL", "AAPL", "SAVE"]  # the checked ones


def test_the_app_backs_up_the_database_before_using_it(database, tmp_path):
    clean(run_page("overview"))
    assert [p.name for p in (tmp_path / "backups").iterdir()] == [f"p-{date.today()}.db"]


def test_taxes_page(database):
    at = clean(run_page("taxes"))
    assert [s.value for s in at.subheader][:3] == [
        "What you hold today", "Sales in 2024", "Dividends in 2024",
    ]  # fmt: skip
    assert list(at.dataframe[0].value["Ticker"]) == ["AAPL"]
    assert list(at.dataframe[1].value["Ticker"]) == ["AAPL", "Total"]


def test_target_allocation_is_set_in_settings_and_shown_on_the_overview(database):
    assert "Against the target" not in [s.value for s in run_page("overview").subheader]
    at = clean(run_page("settings"))
    assert at.button(key="settings_targets_save").disabled is False  # all zero: no target
    at.number_input(key="settings_target_stock").set_value(60).run()
    assert at.button(key="settings_targets_save").disabled
    at.number_input(key="settings_target_savings").set_value(40).run()
    at.button(key="settings_targets_save").click().run()
    clean(at)
    database.rollback()
    assert repo.list_targets(database) == {"savings": D("40"), "stock": D("60")}
    database.rollback()

    at = clean(run_page("overview"))
    assert "Against the target" in [s.value for s in at.subheader]
    at.number_input(key="overview_new_money").set_value(1000).run()
    table = clean(at).dataframe[1].value
    assert list(table["Type"]) == ["savings", "stock"]
    assert list(table["Buy now"]) == [1000, 0]  # savings are far below their 40 %


def test_prices_and_settings_pages(database):
    clean(run_page("prices"))
    at = clean(run_page("settings"))
    assert list(at.dataframe[0].value["Ticker"]) == ["AAPL", "SAVE", "SPY"]


def test_transactions_page_adds_a_buy(database):
    at = clean(run_page("transactions"))
    assert "3 transactions" in at.caption[0].value
    at.text_input(key="tx_form_new_buy_quantity").set_value("1,5")
    at.text_input(key="tx_form_new_buy_price").set_value("160")
    at.run()
    at.text_input(key="tx_form_new_buy_USD_rate").set_value("23,4")
    at.text_input(key="tx_form_new_fee").set_value("12")
    at.button(key="tx_form_new_save").click().run()

    clean(at)
    assert "added" in at.success[0].value
    database.rollback()
    added = repo.list_transactions(database, kinds=[K.BUY])[-1]
    assert (added.quantity, added.price, added.currency) == (D("1.5"), D("160"), "USD")
    assert (added.fx_rate, added.fee, added.instrument_id) == (D("23.4"), D("12"), 1)


def test_form_offers_the_currency_last_used_for_the_instrument(database):
    key = "tx_form_new_buy_1_currency"
    assert run_page("transactions").selectbox(key=key).value == "USD"
    repo.add_transaction(
        database,
        Transaction(
            date(2024, 6, 1), 1, K.BUY, quantity=D(1), price=D(3000), currency="CZK", fx_rate=D(1)
        ),
    )
    database.commit()
    assert run_page("transactions").selectbox(key=key).value == "CZK"


def test_transactions_page_explains_bad_input(database):
    at = run_page("transactions")
    at.text_input(key="tx_form_new_buy_quantity").set_value("abc")
    at.button(key="tx_form_new_save").click().run()
    assert not at.exception
    assert "not a valid Quantity" in at.error[0].value

    at.text_input(key="tx_form_new_buy_quantity").set_value("2")
    at.button(key="tx_form_new_save").click().run()
    assert "needs 'price'" in at.error[0].value
    database.rollback()
    assert len(repo.list_transactions(database)) == 3


def test_valuation_on_the_day_of_a_deposit_is_pointed_out(database):
    assert not run_page("transactions").warning
    repo.set_valuation(database, Valuation(2, date(2023, 6, 1), D("1000")))
    database.commit()
    at = run_page("transactions")
    assert "counted twice" in at.warning[0].value


def test_valuation_can_be_saved(database):
    at = run_page("transactions")
    at.text_input(key="val_value").set_value("1 100,50")
    at.button(key="val_save").click().run()
    clean(at)
    database.rollback()
    assert repo.list_valuations(database, 2)[-1].value == D("1100.50")


def test_settings_adds_a_currency_and_refuses_to_delete_one_in_use(database):
    at = run_page("settings")
    next(t for t in at.text_input if t.placeholder == "Code, e.g. USD").set_value("eur")
    next(b for b in at.button if b.label == "Add" and b.form_id == "currencies_form").click().run()
    clean(at)
    database.rollback()
    assert repo.list_currencies(database) == ["CZK", "EUR", "USD"]

    at.button(key="currencies_delete_USD").click().run()
    assert "in use" in at.error[0].value


def test_export_downloads_and_csv_import(database):
    at = clean(run_page("data"))
    assert [b.label for b in at.get("download_button")] == [
        "Database file",
        "All tables as CSV (zip)",
    ]

    csv_text = (
        "date;ticker;kind;quantity;price;currency;fx_rate;fee\n"
        "2024-07-01;AAPL;buy;0,5;170;USD;23,2;\n"
        "2023-01-02;AAPL;buy;2;100;USD;22;10\n"  # already in the database
    )
    at.file_uploader[0].upload("new.csv", csv_text.encode(), "text/csv").run()
    clean(at)
    assert any("**2** usable" in m.value for m in at.markdown)
    assert at.dataframe[0].value["already there"].tolist() == [False, True]
    at.button(key="import_go").click().run()
    clean(at)
    assert "1 transactions imported" in at.success[0].value
    database.rollback()
    newest = repo.list_transactions(database, kinds=[K.BUY])[-1]
    assert (newest.date, newest.quantity, newest.fx_rate) == (date(2024, 7, 1), D("0.5"), D("23.2"))


def test_csv_import_refuses_files_with_errors(database):
    at = run_page("data")
    at.file_uploader[0].upload(
        "bad.csv", b"date,ticker,kind,quantity\n2024-07-01,NOPE,staking_reward,1\n"
    ).run()
    assert not at.exception
    assert "Line 2 (NOPE): unknown instrument" in at.error[0].value
    assert not [b for b in at.button if b.key == "import_go"]

    at.file_uploader[0].upload("worse.csv", b"when,what\n1,2\n").run()
    assert "needs the columns" in at.error[0].value
    database.rollback()
    assert len(repo.list_transactions(database)) == 3


@pytest.fixture
def savings_apart(database, tmp_path):
    """The same portfolio, with savings configured as a separately reported type."""
    with (tmp_path / "config.toml").open("a") as f:
        f.write('separate_types = ["savings"]\n')
    st.cache_resource.clear()


def test_overview_keeps_separate_types_out_of_the_headline(savings_apart):
    at = clean(run_page("overview"))
    values = [m.value for m in at.metric if m.label == "Value"]
    assert values == ["6\u00a0900", "1\u00a0040"]  # investments, then savings
    by_label = {m.label: (m.value, m.delta) for m in at.metric}
    # AAPL: worth 6900, cost 4400; savings: worth 1040, 1000 deposited
    assert by_label["Cost of holdings"][0] == "4\u00a0400"
    assert by_label["Unrealised profit"] == ("+2\u00a0500", "+56,8\u00a0%")
    assert by_label["Realised profit"][0] == "0"
    assert by_label["Still deposited"][0] == "1\u00a0000"
    assert by_label["Profit"] == ("+40", "+4,0\u00a0%")
    assert [h.value for h in at.header] == ["Savings"]
    by_type, by_currency, instruments, purchases, savings = at.dataframe
    assert list(purchases.value["Ticker"]) == ["AAPL"]
    assert list(by_type.value["type"]) == ["stock"]
    assert list(by_currency.value["currency"]) == ["USD"]
    assert list(by_currency.value["share"]) == [1.0]
    assert list(instruments.value["ticker"]) == ["AAPL"]
    assert list(savings.value["ticker"]) == ["SAVE"]
    assert "Savings is not included" in at.caption[0].value


def test_returns_and_charts_default_to_investments_only(savings_apart):
    for page, key in (("performance", "performance_scope"), ("charts", "charts_scope")):
        at = clean(run_page(page))
        picker = at.selectbox(key=key)
        assert picker.value == "Investments (without savings)"
        assert picker.options[:3] == [
            "Investments (without savings)",
            "All active",
            "Everything, including inactive",
        ]
    at = clean(run_page("performance"))
    without = at.metric[2].value
    at.selectbox(key="performance_scope").select("All active").run()
    assert clean(at).metric[2].value != without


def test_scope_has_no_investments_entry_without_separate_types(database):
    at = clean(run_page("charts"))
    assert at.selectbox(key="charts_scope").options[0] == "All active"


def test_overview_rows_are_tinted_by_profit_or_loss(database):
    from portfolio.ui.pages import overview as page

    assert page._tint(125.0) == page._GAIN
    assert page._tint(-0.5) == page._LOSS
    assert page._tint(0.0) == page._tint(None) == page._tint(float("nan")) == ""
    html = page._tinted(
        [{"ticker": "UP", "total_profit": 10}, {"ticker": "DOWN", "total_profit": -10}]
    ).to_html()
    assert "rgba(46, 160, 67" in html and "rgba(218, 54, 51" in html
    # The page still gets the plain numbers.
    at = clean(run_page("overview"))
    assert list(at.dataframe[2].value["total_profit"]) == [2500, 40]
