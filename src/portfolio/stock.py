"""A tradable stock and its last available price."""

from dataclasses import dataclass, field
from decimal import Decimal

from portfolio.money import Number, to_decimal


@dataclass(frozen=True, slots=True)
class Stock:
    """A stock identified by its ticker symbol.

    The statement says "assume each Stock has a Current Price method that receives
    the last available price". Fetching prices (market data APIs, caching, market
    hours) is out of scope, so the last available price is injected at construction
    and ``current_price()`` returns it. A new quote means a new ``Stock`` value:
    immutability keeps one rebalance calculation consistent with one set of prices.
    """

    symbol: str
    _price: Decimal = field(repr=False)

    def __init__(self, symbol: str, price: Number) -> None:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        decimal_price = to_decimal(price, "price")
        if decimal_price <= 0:
            raise ValueError(f"price must be positive, got {decimal_price}")
        object.__setattr__(self, "symbol", normalized)
        object.__setattr__(self, "_price", decimal_price)

    def current_price(self) -> Decimal:
        """Return the last available price for this stock."""
        return self._price
