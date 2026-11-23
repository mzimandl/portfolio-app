from datetime import date

from portfolio.core.providers.sec import statements_from_facts


def fact(start, end, val, filed, form="10-K"):
    row = {"end": end, "val": val, "filed": filed, "form": form, "accn": "x"}
    if start:
        row["start"] = start
    return row


def facts(**concepts):
    gaap = {}
    for name, (unit, rows) in concepts.items():
        gaap[name] = {"units": {unit: rows}}
    return {"facts": {"us-gaap": gaap}}


def test_years_and_quarters_with_the_newest_filing_winning():
    document = facts(
        Revenues=("USD", [
            fact("2018-01-01", "2018-12-31", 100.0, "2019-02-01"),
            fact("2018-01-01", "2018-12-31", 101.0, "2020-02-01"),  # restated a year later
            fact("2019-01-01", "2019-06-30", 55.0, "2019-08-01", "10-Q"),  # half year: skipped
        ]),
        RevenueFromContractWithCustomerExcludingAssessedTax=("USD", [
            fact("2018-01-01", "2018-12-31", 999.0, "2019-02-01"),  # second choice: not used
            fact("2019-01-01", "2019-12-31", 120.0, "2020-02-01"),  # the only tag that year
        ]),
        NetIncomeLoss=("USD", [fact("2019-01-01", "2019-12-31", 12.0, "2020-02-01")]),
        EarningsPerShareDiluted=(
            "USD/shares", [fact("2019-01-01", "2019-12-31", 1.2, "2020-02-01")]
        ),
        StockholdersEquity=("USD", [
            fact(None, "2019-12-31", 300.0, "2020-02-01"),
            fact(None, "2019-11-15", 999.0, "2020-02-01"),  # no period ends then: skipped
        ]),
        CommonStockSharesOutstanding=("shares", [fact(None, "2019-12-31", 10.0, "2020-02-01")]),
        EntityFoo=("USD", [fact("2019-01-01", "2019-12-31", 5.0, "2020-02-01")]),
    )  # fmt: skip
    first, second = statements_from_facts(document)
    assert (first.period, first.period_end, first.revenue) == ("annual", date(2018, 12, 31), 101.0)
    assert (second.revenue, second.net_income, second.eps) == (120.0, 12.0, 1.2)
    assert (second.equity, second.shares) == (300.0, 10.0)


def test_per_share_numbers_filed_before_a_split_are_converted():
    document = facts(
        EarningsPerShareDiluted=("USD/shares", [
            fact("2022-01-01", "2022-12-31", 20.0, "2023-02-01"),  # before the split
            fact("2023-01-01", "2023-12-31", 3.0, "2024-02-01"),  # after it: already new units
        ]),
        CommonStockSharesOutstanding=("shares", [
            fact(None, "2022-12-31", 100.0, "2023-02-01"),
            fact(None, "2023-12-31", 1000.0, "2024-02-01"),
        ]),
        NetIncomeLoss=("USD", [fact("2022-01-01", "2022-12-31", 2000.0, "2023-02-01")]),
    )  # fmt: skip
    old, new = statements_from_facts(document, [(date(2023, 6, 1), 10.0)])
    assert (old.eps, old.shares, old.net_income) == (2.0, 1000.0, 2000.0)
    assert (new.eps, new.shares) == (3.0, 1000.0)


def test_the_fourth_quarter_is_the_year_minus_three_quarters():
    q = [("2023-01-01", "2023-03-31"), ("2023-04-01", "2023-06-30"), ("2023-07-01", "2023-09-30")]
    document = facts(
        Revenues=("USD", [
            *(fact(s, e, 25.0, "2023-11-01", "10-Q") for s, e in q),
            fact("2023-01-01", "2023-12-31", 110.0, "2024-02-01"),
        ]),
        EarningsPerShareDiluted=("USD/shares", [
            *(fact(s, e, 0.5, "2023-11-01", "10-Q") for s, e in q[:2]),  # one quarter missing
            fact("2023-01-01", "2023-12-31", 2.0, "2024-02-01"),
        ]),
    )  # fmt: skip
    found = statements_from_facts(document)
    quarters = [s for s in found if s.period == "quarterly"]
    assert [s.period_end.month for s in quarters] == [3, 6, 9, 12]
    assert quarters[-1].revenue == 110.0 - 75.0
    assert quarters[-1].eps is None  # needs all three other quarters
    assert [s.period for s in found if s.period_end == date(2023, 12, 31)] == [
        "annual",
        "quarterly",
    ]


def test_nothing_for_companies_without_us_gaap_facts():
    assert statements_from_facts({}) == []
    assert statements_from_facts({"facts": {"ifrs-full": {"Revenue": {}}}}) == []


def test_shares_from_the_cover_page_or_the_average_over_the_period():
    document = facts(
        NetIncomeLoss=("USD", [
            {**fact("2022-01-01", "2022-12-31", 50.0, "2023-02-01"), "accn": "A"},
            {**fact("2023-01-01", "2023-12-31", 60.0, "2024-02-01"), "accn": "B"},
        ]),
        WeightedAverageNumberOfDilutedSharesOutstanding=("shares", [
            fact("2022-01-01", "2022-12-31", 9.0, "2023-02-01"),
            fact("2023-01-01", "2023-12-31", 11.0, "2024-02-01"),
        ]),
    )  # fmt: skip
    document["facts"]["dei"] = {
        "EntityCommonStockSharesOutstanding": {
            "units": {"shares": [{"end": "2024-01-20", "val": 12.0, "filed": "2024-02-01",
                                  "accn": "B"}]}
        }
    }  # fmt: skip
    first, second = statements_from_facts(document)
    assert first.shares == 9.0  # the average, nothing better
    assert second.shares == 12.0  # the count on the cover of the filing for that year
