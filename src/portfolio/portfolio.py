"""Portfolio: what you own (holdings) and what you aim to own (allocation)."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction

from portfolio.money import Number, to_decimal
from portfolio.stock import Stock


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Order:
    """One instruction of a rebalance: buy or sell ``shares`` worth ``amount``.

    ``shares`` and ``amount`` are always positive; the direction lives in ``side``.
    Both are returned because apps usually execute by amount (fractional investing)
    while brokers and users often reason in shares.
    """

    symbol: str
    side: Side
    shares: Decimal
    amount: Decimal


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

        # Summed as exact rationals, not Decimals. Decimal rounds every addition to 28
        # significant digits, so the result of a Decimal sum depends on the order of
        # the terms: the same weights could add up to 1 in one order and to
        # 0.9999999999999999999999999999 in another. The property-based tests caught
        # exactly that. Fraction has no rounding, so this check is exact and does
        # not depend on order.
        total_weight = sum((Fraction(weight) for weight in self._weights.values()), Fraction(0))
        if total_weight != 1:
            shown = Decimal(total_weight.numerator) / Decimal(total_weight.denominator)
            raise ValueError(f"allocation weights must add up to 1, got {shown}")

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
        """Market value of every holding at current prices.

        Summed in symbol order (not input order) for the same reason as the weight
        check: Decimal addition rounds, so a fixed order keeps the result identical
        however the caller built the holdings.
        """
        return sum((self.position_value(s) for s in sorted(self._shares)), Decimal(0))

    def rebalance(self, min_trade_value: Number = 0) -> list[Order]:
        """Return the orders that move the holdings to the target allocation.

        For every stock, held or allocated:

            target value = total value * target weight
            difference   = target value - current value
            difference > 0 -> BUY that amount; difference < 0 -> SELL it

        Rebalancing redistributes the current value, it does not add money, so the
        sum of buys equals the sum of sells (self-financed). Selling first frees the
        cash the buys need, which is why sells come first in the result. Within each
        side orders are sorted by symbol, so the same input always gives the same
        output.

        ``min_trade_value`` skips orders whose amount is not greater than it. Prices
        move every second, so without a threshold an almost balanced portfolio would
        trade tiny amounts on every call and pay fees for nothing. The default of
        zero keeps the result exact. With a threshold, a skipped order leaves the
        portfolio slightly off target, and buys and sells may no longer cancel out.

        The method only computes orders; it does not execute them or change the
        portfolio, so it is safe to call to preview a rebalance.
        """
        threshold = to_decimal(min_trade_value, "min_trade_value")
        if threshold < 0:
            raise ValueError(f"min_trade_value must not be negative, got {threshold}")

        total = self.total_value()
        sells: list[Order] = []
        buys: list[Order] = []
        for symbol in self.symbols():
            difference = total * self.target_weight(symbol) - self.position_value(symbol)
            amount = abs(difference)
            if amount == 0 or amount <= threshold:
                continue
            # The only division in the module. Decimal keeps 28 significant digits,
            # so a non-terminating quotient (e.g. 100 / 3) is off by less than 1e-25
            # shares: far below anything a broker can execute.
            side = Side.BUY if difference > 0 else Side.SELL
            order = Order(symbol, side, shares=amount / self.price(symbol), amount=amount)
            (buys if side is Side.BUY else sells).append(order)
        return sells + buys
