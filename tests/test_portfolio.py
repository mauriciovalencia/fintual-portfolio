from decimal import Decimal

import pytest

from portfolio.portfolio import Portfolio
from portfolio.stock import Stock

META = Stock("META", "500")
AAPL = Stock("AAPL", "200")


def test_total_value_is_the_sum_of_shares_times_current_price():
    portfolio = Portfolio(
        holdings={META: "2", AAPL: "5"},
        allocation={META: "0.4", AAPL: "0.6"},
    )

    assert portfolio.total_value() == Decimal("2000")


def test_holds_fractional_shares():
    portfolio = Portfolio(holdings={META: "0.5"}, allocation={META: "1"})

    assert portfolio.total_value() == Decimal("250")


def test_allocation_must_add_up_to_exactly_one():
    with pytest.raises(ValueError, match="add up to 1"):
        Portfolio(holdings={META: "1"}, allocation={META: "0.4", AAPL: "0.5"})


def test_allocation_that_adds_up_with_many_decimals_is_accepted():
    third = Decimal(1) / 3
    weights = {META: third, AAPL: third, Stock("MSFT", "400"): 1 - 2 * third}

    Portfolio(holdings={}, allocation=weights)


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1)])
def test_weight_sum_check_does_not_depend_on_input_order(order):
    # Found by the property-based tests: summed as Decimals, these weights give 1 in
    # one order and 0.9999999999999999999999999999 in another.
    weights = [
        Decimal("0.08333333333333333333333333333"),
        Decimal("0.08333333333333333333333333333"),
        Decimal("0.83333333333333333333333333334"),
    ]
    stocks = [META, AAPL, Stock("MSFT", "400")]

    Portfolio(holdings={}, allocation={stocks[i]: weights[i] for i in order})


def test_allocation_must_not_be_empty():
    with pytest.raises(ValueError, match="allocation"):
        Portfolio(holdings={META: "1"}, allocation={})


@pytest.mark.parametrize("weight", ["-0.1", "1.1"])
def test_each_weight_must_be_between_zero_and_one(weight):
    with pytest.raises(ValueError, match="weight"):
        Portfolio(holdings={}, allocation={META: weight, AAPL: 1 - Decimal(weight)})


def test_zero_weight_is_allowed_to_express_an_exit():
    Portfolio(holdings={META: "1"}, allocation={META: "0", AAPL: "1"})


def test_shares_must_not_be_negative():
    with pytest.raises(ValueError, match="shares"):
        Portfolio(holdings={META: "-1"}, allocation={META: "1"})


def test_rejects_the_same_symbol_with_two_different_prices():
    stale_meta = Stock("META", "480")

    with pytest.raises(ValueError, match="META"):
        Portfolio(holdings={META: "1"}, allocation={stale_meta: "1"})


def test_rejects_float_weights_and_shares():
    with pytest.raises(TypeError):
        Portfolio(holdings={META: 1.5}, allocation={META: "1"})  # type: ignore[dict-item]
    with pytest.raises(TypeError):
        Portfolio(holdings={META: "1"}, allocation={META: 1.0})  # type: ignore[dict-item]


def test_inputs_are_copied_so_later_mutation_does_not_change_the_portfolio():
    holdings = {META: "1"}
    portfolio = Portfolio(holdings=holdings, allocation={META: "1"})

    holdings[META] = "100"

    assert portfolio.total_value() == Decimal("500")
