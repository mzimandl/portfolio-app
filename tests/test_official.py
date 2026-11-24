"""Reading the ČNB and Eurostat answers, from samples shaped like the real ones."""

from datetime import date

import pytest

from portfolio.core.providers.official import parse_cnb_year, parse_hicp

CNB = """Datum|1 EUR|100 JPY|1 USD
02.01.2025|25,175|15,539|24,398
03.01.2025|25,155||24,410
Datum|1 EUR|1 USD
05.01.2025|25,100|24,300|
"""


def test_cnb_year_file():
    rates = parse_cnb_year(CNB)
    assert rates[:3] == [
        ("EUR", date(2025, 1, 2), 25.175),
        ("JPY", date(2025, 1, 2), pytest.approx(0.15539)),  # per 1 yen, not per 100
        ("USD", date(2025, 1, 2), 24.398),
    ]
    # An empty cell is skipped; a repeated header changes the columns from then on.
    assert [r for r in rates if r[1] == date(2025, 1, 3)] == [
        ("EUR", date(2025, 1, 3), 25.155), ("USD", date(2025, 1, 3), 24.41),
    ]  # fmt: skip
    assert [r for r in rates if r[1] == date(2025, 1, 5)] == [
        ("EUR", date(2025, 1, 5), 25.1), ("USD", date(2025, 1, 5), 24.3),
    ]  # fmt: skip
    assert parse_cnb_year("") == []


def test_eurostat_json_stat():
    payload = {
        "value": {"0": 155.8, "2": 156.5},
        "dimension": {"time": {"category": {"index": {"2025-06": 0, "2025-07": 1,
                                                       "2025-08": 2}}}},
    }  # fmt: skip
    assert parse_hicp(payload) == [(date(2025, 6, 1), 155.8), (date(2025, 8, 1), 156.5)]
    assert parse_hicp({"error": "no data"}) == []
