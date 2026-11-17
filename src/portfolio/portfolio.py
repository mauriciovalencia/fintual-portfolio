"""Portfolio: what you own (holdings) and what you aim to own (allocation)."""

from collections.abc import Mapping
from decimal import Decimal

from portfolio.money import Number, to_decimal
from portfolio.stock import Stock


class Portfolio:
    """A collection of held stocks plus the target distribution it aims for.

    ``holdings`` maps each stock to the number of shares owned. Fractional shares
    are allowed, as in most modern investment apps.

    ``allocation`` maps each stock to its target weight as a fraction of the total
    value (``"0.4"`` means 40%). Weights are fractions rather than percentages so the
    rebalance math is a plain multiplication, with no ``/ 100`` anywhere.

    Both collections are keyed by ``Stock`` objects (not bare symbols) because a
    stock that is allocated but not yet held still needs a price to be bought.

    The constructor validates everything up front, so a ``Portfolio`` that exists is
    always consistent and ``rebalance`` never has to defend against bad state.
    """

    def __init__(self, holdings: Mapping[Stock, Number], allocation: Mapping[Stock, Number]):
        self._stocks: dict[str, Stock] = {}
        self._shares: dict[str, Decimal] = {}
        self._weights: dict[str, Decimal] = {}

        for stock, shares in holdings.items():
            self._register(stock)
            amount = to_decimal(shares, f"shares of {stock.symbol}")
            if amount < 0:
                raise ValueError(f"shares of {stock.symbol} must not be negative, got {amount}")
            self._shares[stock.symbol] = amount

        if not allocation:
            raise ValueError("allocation must contain at least one stock")
        for stock, weight in allocation.items():
            self._register(stock)
            fraction = to_decimal(weight, f"weight of {stock.symbol}")
            if not 0 <= fraction <= 1:
                raise ValueError(
                    f"weight of {stock.symbol} must be between 0 and 1, got {fraction}"
                )
            self._weights[stock.symbol] = fraction

        # Exact comparison is safe because weights are Decimals, never floats.
        total_weight = sum(self._weights.values(), Decimal(0))
        if total_weight != 1:
            raise ValueError(f"allocation weights must add up to 1, got {total_weight}")

    def _register(self, stock: Stock) -> None:
        """Index stocks by symbol, refusing two different prices for one symbol.

        If holdings say META is 500 and allocation says META is 480, any result would
        be computed on inconsistent data, so failing loudly is the only safe answer.
        """
        known = self._stocks.setdefault(stock.symbol, stock)
        if known.current_price() != stock.current_price():
            raise ValueError(
                f"{stock.symbol} appears with two prices: "
                f"{known.current_price()} and {stock.current_price()}"
            )

    def shares(self, symbol: str) -> Decimal:
        """Shares currently held of ``symbol`` (zero when not held)."""
        return self._shares.get(symbol, Decimal(0))

    def price(self, symbol: str) -> Decimal:
        """Current price of a stock known to this portfolio."""
        return self._stocks[symbol].current_price()

    def target_weight(self, symbol: str) -> Decimal:
        """Target weight of ``symbol``; stocks held but not allocated target zero."""
        return self._weights.get(symbol, Decimal(0))

    def symbols(self) -> list[str]:
        """Every symbol held or allocated, sorted for deterministic output."""
        return sorted(self._stocks)

    def position_value(self, symbol: str) -> Decimal:
        """Market value of the shares held of ``symbol``."""
        return self.shares(symbol) * self.price(symbol)

    def total_value(self) -> Decimal:
        """Market value of every holding at current prices."""
        return sum((self.position_value(symbol) for symbol in self._shares), Decimal(0))
