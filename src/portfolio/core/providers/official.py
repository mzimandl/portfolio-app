"""Public statistics, without extra packages: exchange rates of the Czech National Bank and
consumer prices from Eurostat.

Both are official sources that keep their formats for years and need no key. Everything that
reads them is in this file, so it is the only place to fix when one of them changes.
"""

import json
import urllib.error
import urllib.request
from datetime import date

from portfolio.core.providers.base import ProviderError

# One text file per year with every day's rates: "Datum|1 AUD|...|100 JPY|..." then
# "02.01.2025|15,145|...". The header is repeated when the list of currencies changes.
CNB_YEAR_URL = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/"
    "kurzy-devizoveho-trhu/rok.txt?rok={year}"
)
# The harmonised index of consumer prices, 2015 = 100, all items, monthly. Eurostat replaced
# its older dataset prc_hicp_midx with this one in 2026; it reaches back to 1996.
HICP_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr"
    "?geo={region}&coicop18=TOTAL&unit=I15"
)
_USER_AGENT = "portfolio-app"


def _get(url: str, what: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ProviderError(f"{what}: {e}") from e


def parse_cnb_year(text: str) -> list[tuple[str, date, float]]:
    """(currency, day, CZK per 1 unit) from a ČNB yearly file. Empty cells are skipped."""
    rates = []
    columns: list[tuple[str, float]] = []
    for line in text.splitlines():
        cells = line.strip().split("|")
        if not cells or not cells[0]:
            continue
        if cells[0] == "Datum":
            columns = []
            for header in cells[1:]:
                amount, _, code = header.partition(" ")
                columns.append((code.strip(), float(amount)))
            continue
        try:
            day_, month, year = cells[0].split(".")
            day = date(int(year), int(month), int(day_))
        except ValueError:
            continue
        for (code, amount), cell in zip(columns, cells[1:], strict=False):
            cell = cell.strip().replace(",", ".")
            if not cell:
                continue
            try:
                rates.append((code, day, float(cell) / amount))
            except ValueError:
                continue
    return rates


def parse_hicp(payload: dict) -> list[tuple[date, float]]:
    """(first day of the month, index) from Eurostat's JSON-stat answer, oldest first."""
    try:
        months = payload["dimension"]["time"]["category"]["index"]
        values = payload["value"]
    except (KeyError, TypeError):
        return []
    found = []
    for month, position in months.items():
        value = values.get(str(position)) if isinstance(values, dict) else None
        if value is None and isinstance(values, list) and position < len(values):
            value = values[position]
        if value is None:
            continue
        year, number = month.split("-")
        found.append((date(int(year), int(number), 1), float(value)))
    found.sort()
    return found


class OfficialProvider:
    def cnb_year(self, year: int) -> list[tuple[str, date, float]]:
        raw = _get(CNB_YEAR_URL.format(year=year), f"ČNB rates {year}")
        return parse_cnb_year(raw.decode("utf-8", errors="replace"))

    def hicp(self, region: str) -> list[tuple[date, float]]:
        raw = _get(HICP_URL.format(region=region), f"Eurostat HICP {region}")
        try:
            payload = json.loads(raw)
        except ValueError as e:
            raise ProviderError(f"Eurostat HICP {region}: {e}") from e
        found = parse_hicp(payload)
        if not found:
            raise ProviderError(
                f"Eurostat HICP {region}: no values (is inflation_region a Eurostat country "
                "code such as CZ?)"
            )
        return found
