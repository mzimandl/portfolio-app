import pytest

from portfolio.core import db, repo
from portfolio.core.models import Instrument, ValuationMethod


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    db.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def stock(conn):
    """A USD stock, with the reference data it needs."""
    for code in ("CZK", "USD", "EUR"):
        repo.add_currency(conn, code)
    for name in ("stock", "savings"):
        repo.add_instrument_type(conn, name)
    instrument = repo.add_instrument(
        conn,
        Instrument(ticker="AAPL", type="stock", currency="USD", valuation=ValuationMethod.YAHOO),
    )
    conn.commit()
    return instrument
