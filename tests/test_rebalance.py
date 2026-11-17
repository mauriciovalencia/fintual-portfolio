from decimal import Decimal

import pytest

from portfolio.portfolio import Order, Portfolio, Side
from portfolio.stock import Stock

META = Stock("META", "500")
AAPL = Stock("AAPL", "200")
MSFT = Stock("MSFT", "400")


def test_statement_example_sells_overweight_and_buys_underweight():
    # 4 META = 2000 total. Target: 40% META (800), 60% AAPL (1200).
    portfolio = Portfolio(holdings={META: "4"}, allocation={META: "0.4", AAPL: "0.6"})

    assert portfolio.rebalance() == [
        Order("META", Side.SELL, shares=Decimal("2.4"), amount=Decimal("1200")),
        Order("AAPL", Side.BUY, shares=Decimal("6"), amount=Decimal("1200")),
    ]


def test_balanced_portfolio_needs_no_orders():
    portfolio = Portfolio(
        holdings={META: "0.8", AAPL: "3"},  # 400 META + 600 AAPL
        allocation={META: "0.4", AAPL: "0.6"},
    )

    assert portfolio.rebalance() == []


def test_stock_held_but_not_allocated_is_sold_entirely():
    portfolio = Portfolio(holdings={META: "1", MSFT: "1"}, allocation={META: "1"})

    assert portfolio.rebalance() == [
        Order("MSFT", Side.SELL, shares=Decimal("1"), amount=Decimal("400")),
        Order("META", Side.BUY, shares=Decimal("0.8"), amount=Decimal("400")),
    ]


def test_empty_portfolio_has_nothing_to_rebalance():
    portfolio = Portfolio(holdings={}, allocation={META: "0.4", AAPL: "0.6"})

    assert portfolio.rebalance() == []


def test_sells_come_before_buys_and_each_group_is_sorted_by_symbol():
    portfolio = Portfolio(
        holdings={MSFT: "5", META: "4"},  # 2000 MSFT + 2000 META
        allocation={AAPL: "0.5", Stock("AMZN", "100"): "0.5"},
    )

    orders = portfolio.rebalance()

    assert [(order.side, order.symbol) for order in orders] == [
        (Side.SELL, "META"),
        (Side.SELL, "MSFT"),
        (Side.BUY, "AAPL"),
        (Side.BUY, "AMZN"),
    ]


def test_min_trade_value_skips_drift_too_small_to_be_worth_a_trade():
    portfolio = Portfolio(
        holdings={META: "0.81", AAPL: "2.975"},  # 405 META + 595 AAPL, drift of 5
        allocation={META: "0.4", AAPL: "0.6"},
    )

    assert portfolio.rebalance(min_trade_value="5") == []
    assert len(portfolio.rebalance(min_trade_value="4.99")) == 2


def test_min_trade_value_must_not_be_negative():
    portfolio = Portfolio(holdings={META: "1"}, allocation={META: "1"})

    with pytest.raises(ValueError, match="min_trade_value"):
        portfolio.rebalance(min_trade_value="-1")


def test_rebalance_does_not_mutate_the_portfolio():
    portfolio = Portfolio(holdings={META: "4"}, allocation={META: "0.4", AAPL: "0.6"})

    portfolio.rebalance()

    assert portfolio.shares("META") == Decimal("4")
    assert portfolio.shares("AAPL") == Decimal("0")
