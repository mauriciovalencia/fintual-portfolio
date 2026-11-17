from decimal import Decimal

import pytest

from portfolio.stock import Stock


def test_current_price_returns_last_available_price_as_decimal():
    stock = Stock("META", "512.34")

    assert stock.current_price() == Decimal("512.34")
    assert isinstance(stock.current_price(), Decimal)


def test_accepts_int_and_decimal_prices():
    assert Stock("AAPL", 190).current_price() == Decimal("190")
    assert Stock("AAPL", Decimal("190.5")).current_price() == Decimal("190.5")


def test_rejects_float_prices_to_avoid_binary_rounding_errors():
    with pytest.raises(TypeError, match="float"):
        Stock("AAPL", 0.1)


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity", "abc"])
def test_rejects_non_positive_or_non_finite_prices(price):
    with pytest.raises(ValueError):
        Stock("AAPL", price)


@pytest.mark.parametrize("symbol", ["", "   "])
def test_rejects_blank_symbols(symbol):
    with pytest.raises(ValueError, match="symbol"):
        Stock(symbol, "10")


def test_symbol_is_normalized_to_uppercase():
    assert Stock(" meta ", "10").symbol == "META"


def test_stock_is_immutable():
    stock = Stock("META", "10")

    with pytest.raises(AttributeError):
        stock.symbol = "AAPL"  # type: ignore[misc]
