"""Adversarial, property-based tests for ``Portfolio.rebalance``.

Example-based tests only check the cases the author thought of. Here Hypothesis
generates thousands of random portfolios (odd prices, fractional shares, weights
like 1/7, stocks held but not allocated, empty holdings) and shrinks any failure
to the smallest counterexample. Each test states a rule that must hold for EVERY
portfolio, not for one hand-picked case.

The strongest check is the oracle: the same math redone with ``fractions.Fraction``,
which is exact rational arithmetic with no rounding at all. ``Decimal`` must agree
with it to within a relative error of 1e-20.
"""

from decimal import Decimal, localcontext
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from portfolio.portfolio import Order, Portfolio, Side
from portfolio.stock import Stock

# 28 significant digits of Decimal leave plenty of room; this is far stricter than
# any currency (cents) or broker share precision (usually 1e-6 to 1e-9).
RELATIVE_TOLERANCE = Decimal("1e-20")

TICKERS = ["AAPL", "META", "MSFT", "AMZN", "GOOG", "NVDA", "TSLA", "NFLX"]

prices = st.decimals(min_value="0.01", max_value="100000", places=2)
share_counts = st.decimals(min_value="0", max_value="100000", places=6)


@st.composite
def portfolios(draw) -> Portfolio:
    universe = draw(st.lists(st.sampled_from(TICKERS), min_size=1, unique=True))
    stocks = {symbol: Stock(symbol, draw(prices)) for symbol in universe}

    allocated = draw(st.lists(st.sampled_from(universe), min_size=1, unique=True))
    # Integer parts normalized to fractions, with the last weight absorbing the
    # remainder so the total is exactly 1 (e.g. 1/3, 1/3, 1 - 2/3). The last
    # part is at least 1 so rounding can never push it below zero.
    parts = [draw(st.integers(0, 100)) for _ in allocated[:-1]] + [draw(st.integers(1, 100))]
    total_parts = sum(parts)
    weights = [Decimal(part) / total_parts for part in parts[:-1]]
    with localcontext() as exact:
        exact.prec = 100  # enough digits for the remainder to be computed exactly
        weights.append(1 - sum(weights, Decimal(0)))

    held = draw(st.lists(st.sampled_from(universe), unique=True))
    return Portfolio(
        holdings={stocks[symbol]: draw(share_counts) for symbol in held},
        allocation={stocks[s]: w for s, w in zip(allocated, weights, strict=True)},
    )


def tolerance(portfolio: Portfolio) -> Decimal:
    return max(portfolio.total_value(), Decimal(1)) * RELATIVE_TOLERANCE


def shares_after(portfolio: Portfolio, orders: list[Order]) -> dict[str, Decimal]:
    after = {symbol: portfolio.shares(symbol) for symbol in portfolio.symbols()}
    for order in orders:
        sign = 1 if order.side is Side.BUY else -1
        after[order.symbol] += sign * order.shares
    return after


@settings(max_examples=500, deadline=None)
@given(portfolios())
def test_buys_are_fully_financed_by_sells(portfolio):
    orders = portfolio.rebalance()

    bought = sum((o.amount for o in orders if o.side is Side.BUY), Decimal(0))
    sold = sum((o.amount for o in orders if o.side is Side.SELL), Decimal(0))

    assert abs(bought - sold) <= tolerance(portfolio)


@settings(max_examples=500, deadline=None)
@given(portfolios())
def test_after_executing_orders_every_weight_matches_the_allocation(portfolio):
    after = shares_after(portfolio, portfolio.rebalance())
    total = portfolio.total_value()

    for symbol, shares in after.items():
        value = shares * portfolio.price(symbol)
        assert abs(value - total * portfolio.target_weight(symbol)) <= tolerance(portfolio)


@settings(max_examples=500, deadline=None)
@given(portfolios())
def test_never_sells_more_shares_than_held(portfolio):
    after = shares_after(portfolio, portfolio.rebalance())

    for symbol, shares in after.items():
        assert shares >= -tolerance(portfolio) / portfolio.price(symbol)


@settings(max_examples=500, deadline=None)
@given(portfolios())
def test_orders_are_positive_unique_and_consistent_with_price(portfolio):
    orders = portfolio.rebalance()

    assert len({o.symbol for o in orders}) == len(orders)
    for order in orders:
        assert order.amount > 0
        assert order.shares > 0
        assert abs(order.shares * portfolio.price(order.symbol) - order.amount) <= tolerance(
            portfolio
        )


@settings(max_examples=300, deadline=None)
@given(portfolios())
def test_rebalancing_a_rebalanced_portfolio_is_a_no_op(portfolio):
    after = shares_after(portfolio, portfolio.rebalance())
    stocks = {s: Stock(s, portfolio.price(s)) for s in portfolio.symbols()}
    weights = {stocks[s]: portfolio.target_weight(s) for s in portfolio.symbols()}
    # Rounding residue can be a hair below zero; it is not a real short position.
    holdings = {stocks[s]: max(shares, Decimal(0)) for s, shares in after.items()}

    rebalanced = Portfolio(holdings=holdings, allocation=weights)

    assert rebalanced.rebalance(min_trade_value=tolerance(portfolio)) == []


@settings(max_examples=300, deadline=None)
@given(portfolios(), st.randoms(use_true_random=False))
def test_result_does_not_depend_on_input_order(portfolio, rng):
    symbols = portfolio.symbols()
    shuffled = rng.sample(symbols, len(symbols))
    stocks = {s: Stock(s, portfolio.price(s)) for s in shuffled}

    same = Portfolio(
        holdings={stocks[s]: portfolio.shares(s) for s in shuffled if portfolio.shares(s)},
        allocation={stocks[s]: portfolio.target_weight(s) for s in shuffled},
    )

    assert same.rebalance() == portfolio.rebalance()


@settings(max_examples=1000, deadline=None)
@given(portfolios())
def test_matches_exact_rational_arithmetic_oracle(portfolio):
    """Recompute every order with Fraction (no rounding) and compare."""
    total = sum(
        (Fraction(portfolio.shares(s)) * Fraction(portfolio.price(s)) for s in portfolio.symbols()),
        Fraction(0),
    )
    expected: dict[str, Fraction] = {}
    for symbol in portfolio.symbols():
        current = Fraction(portfolio.shares(symbol)) * Fraction(portfolio.price(symbol))
        difference = total * Fraction(portfolio.target_weight(symbol)) - current
        if difference != 0:
            expected[symbol] = difference

    actual = {
        o.symbol: Fraction(o.amount) * (1 if o.side is Side.BUY else -1)
        for o in portfolio.rebalance()
    }

    exact_tolerance = Fraction(tolerance(portfolio))
    for symbol in expected.keys() | actual.keys():
        assert abs(expected.get(symbol, Fraction(0)) - actual.get(symbol, Fraction(0))) <= (
            exact_tolerance
        )
