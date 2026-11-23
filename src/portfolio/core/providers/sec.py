"""Company results of US-listed companies from SEC EDGAR (data.sec.gov), without extra packages.

The SEC asks every automated client to name itself with a contact in the User-Agent header
and refuses requests without one, so this source is only used when ``sec_user_agent`` is set
in the config file. It also asks for at most ten requests a second; an update makes a few.

The facts are the numbers companies tag in their 10-K and 10-Q filings, as reported then.
Per-share numbers filed before a later split are in the old share units; they are converted
with the splits the price data knows.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Iterable
from datetime import date

from portfolio.core.providers.base import ProviderError, Statement

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# The tags companies use for each number, first choice first. Usage changed over the years
# (revenue moved to RevenueFromContractWithCustomer... in 2018), so each period takes the
# first tag that has a value for it.
_FLOWS = {
    "revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ),
    "net_income": (
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLoss",
    ),
    "eps": ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"),
}
_INSTANTS = {
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "shares": ("CommonStockSharesOutstanding",),
}
_UNITS = {"eps": "USD/shares", "shares": "shares"}  # everything else is in USD
_ANNUAL_DAYS = (350, 380)
_QUARTER_DAYS = (80, 100)


def _day(text: str) -> date:
    return date.fromisoformat(text)


def _later_splits(filed: date, splits: Iterable[tuple[date, float]]) -> float:
    factor = 1.0
    for day, ratio in splits:
        if day > filed and ratio > 0:
            factor *= ratio
    return factor


def _latest(rows: list[dict]) -> dict[tuple, dict]:
    """The newest filing's value for every (start, end); restatements replace older ones."""
    found: dict[tuple, dict] = {}
    for row in rows:
        if "val" not in row or "end" not in row or "filed" not in row:
            continue
        key = (row.get("start"), row["end"])
        if key not in found or row["filed"] >= found[key]["filed"]:
            found[key] = row
    return found


def statements_from_facts(
    facts: dict, splits: Iterable[tuple[date, float]] = ()
) -> list[Statement]:
    """Annual and quarterly periods from a companyfacts document, oldest first, in USD.

    A fourth quarter that is only in the annual report is the year minus the other three
    quarters (for EPS this is close, not exact, as the number of shares changes).
    """
    splits = list(splits)
    gaap = facts.get("facts", {}).get("us-gaap", {})
    periods: dict[tuple[str, date], dict] = {}
    annual_starts: dict[date, date] = {}

    def values(field: str, concepts: tuple[str, ...]) -> list[tuple[dict, dict]]:
        unit = _UNITS.get(field, "USD")
        return [
            (concept, _latest(gaap[concept].get("units", {}).get(unit, [])))
            for concept in concepts
            if concept in gaap
        ]

    def adjusted(field: str, row: dict) -> float:
        value = float(row["val"])
        factor = _later_splits(_day(row["filed"]), splits)
        if field == "eps":
            return value / factor
        if field == "shares":
            return value * factor
        return value

    for field, concepts in _FLOWS.items():
        for _, rows in values(field, concepts):
            for (start, end), row in rows.items():
                if start is None:
                    continue
                days = (_day(end) - _day(start)).days
                if _ANNUAL_DAYS[0] <= days <= _ANNUAL_DAYS[1]:
                    kind = "annual"
                    annual_starts[_day(end)] = _day(start)
                elif _QUARTER_DAYS[0] <= days <= _QUARTER_DAYS[1]:
                    kind = "quarterly"
                else:
                    continue  # half years and nine months from 10-Q filings
                period = periods.setdefault((kind, _day(end)), {})
                period.setdefault(field, adjusted(field, row))  # first tag wins

    _derive_fourth_quarters(periods, annual_starts)

    ends = {end for _, end in periods}
    for field, concepts in _INSTANTS.items():
        for _, rows in values(field, concepts):
            for (start, end), row in rows.items():
                if start is not None or _day(end) not in ends:
                    continue
                for kind in ("annual", "quarterly"):
                    if (kind, _day(end)) in periods:
                        periods[(kind, _day(end))].setdefault(field, adjusted(field, row))

    return [
        Statement(kind, end, **fields)
        for (kind, end), fields in sorted(
            periods.items(), key=lambda item: (item[0][1], item[0][0])
        )
        if fields
    ]


def _derive_fourth_quarters(periods: dict, annual_starts: dict[date, date]) -> None:
    for end, start in annual_starts.items():
        if ("quarterly", end) in periods:
            continue
        year = periods[("annual", end)]
        quarters = [
            fields
            for (kind, q_end), fields in periods.items()
            if kind == "quarterly" and start < q_end < end
        ]
        if len(quarters) != 3:
            continue
        fourth = {
            field: year[field] - sum(q[field] for q in quarters)
            for field in _FLOWS
            if field in year and all(field in q for q in quarters)
        }
        if fourth:
            periods[("quarterly", end)] = fourth


class SecProvider:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._tickers: dict[str, int] | None = None

    def _get(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            hint = " (is sec_user_agent a name and an e-mail?)" if e.code == 403 else ""
            raise ProviderError(f"SEC: {url}: {e}{hint}") from e
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ProviderError(f"SEC: {url}: {e}") from e

    def cik(self, ticker: str) -> int | None:
        """The SEC's number for a ticker as US exchanges write it (BRK-B), or None."""
        if self._tickers is None:
            listing = self._get(TICKERS_URL)
            self._tickers = {
                str(item["ticker"]).upper(): int(item["cik_str"])
                for item in listing.values()
                if isinstance(item, dict) and "ticker" in item and "cik_str" in item
            }
        return self._tickers.get(ticker.upper())

    def statements(self, ticker: str, splits: Iterable[tuple[date, float]] = ()) -> list[Statement]:
        cik = self.cik(ticker)
        if cik is None:
            return []
        return statements_from_facts(self._get(FACTS_URL.format(cik=cik)), splits)
