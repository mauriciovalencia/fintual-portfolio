# Portfolio rebalancing

A small `Portfolio` module for a personal investments app. A portfolio holds stocks,
has a target allocation (e.g. 40% META, 60% AAPL), and `rebalance()` tells you which
stocks to sell and which to buy to reach that allocation.

```python
from portfolio.portfolio import Portfolio
from portfolio.stock import Stock

meta, aapl = Stock("META", "500"), Stock("AAPL", "200")
portfolio = Portfolio(holdings={meta: "4"}, allocation={meta: "0.4", aapl: "0.6"})

for order in portfolio.rebalance():
    print(order)
# Order(symbol='META', side=<Side.SELL: 'sell'>, shares=Decimal('2.4'), amount=Decimal('1200.0'))
# Order(symbol='AAPL', side=<Side.BUY: 'buy'>, shares=Decimal('6.0'), amount=Decimal('1200.0'))
```

## Run it

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.12+ if needed).

```bash
uv sync                 # create the virtualenv and install dev dependencies
uv run pytest           # 41 tests, including ~3,600 generated portfolios
uv run ruff check . && uv run ruff format --check .
```

## The algorithm

For every stock, whether held or allocated:

```
target value = total value * target weight
difference   = target value - current value     (> 0 buy, < 0 sell)
```

It runs in one pass, O(n) in the number of stocks. Rebalancing only redistributes
the current value, so the buys are fully financed by the sells. Sells come first in
the result because they free the cash the buys need.

## Decisions on what the statement leaves open

The statement is short on purpose, so these are the choices I made and why:

| Question | Decision | Why |
|---|---|---|
| Floats or exact numbers? | `Decimal` everywhere; **floats are rejected** with `TypeError` | `0.1 + 0.2 != 0.3` in binary floats. Once a value is a float the precision is already gone, so converting it silently would hide the bug. |
| How is "Current Price" provided? | Injected into an immutable `Stock`; `current_price()` returns it | Fetching market data is out of scope. Immutability means one rebalance always uses one consistent set of prices. |
| Fractional shares? | Yes | Most investment apps allow them, and it keeps the result exact. Rounding to whole shares is a broker constraint (see *Next steps*). |
| Weights as `40` or `0.4`? | Fractions (`0.4`) that must add up to **exactly** 1 | No `/ 100` in the math. A total of 0.99 is a user error, not something to guess around. |
| Stock held but not allocated? | Target weight 0, so it is sold entirely | The allocation describes the whole portfolio. |
| Stock allocated but not held? | Bought | That is why allocation is keyed by `Stock` (it carries a price), not by a bare symbol. |
| Same symbol with two prices? | `ValueError` | Any result would be computed on inconsistent data. |
| Empty portfolio? | No orders | Rebalancing redistributes value; it does not deposit cash. |
| Tiny drift? | Optional `min_trade_value` | Prices move every second. Without a threshold, an almost balanced portfolio would trade cents on every call and pay fees for nothing. The default of 0 keeps the result exact. |
| Does `rebalance` execute? | No, it only returns `Order`s | Previewing has no side effects. Execution belongs to another component. |
| `APPL` in the statement | Treated as a typo of `AAPL` | |

## How it is tested

1. **TDD, one feature per commit.** Each commit added failing tests first, then the
   code (see `git log`).
2. **Property-based (adversarial) tests** with [Hypothesis](https://hypothesis.works/)
   in `tests/test_rebalance_properties.py`. They do not check hand-picked examples.
   They generate thousands of random portfolios (odd prices, fractional shares,
   weights like 1/7, unallocated holdings) and check rules that must hold for every
   one of them:
   - buys are fully financed by sells;
   - after the orders run, every weight matches the allocation;
   - it never sells more shares than are held;
   - rebalancing an already rebalanced portfolio is a no-op;
   - the result does not depend on the order of the inputs;
   - an **oracle** redoes the math with `fractions.Fraction` (exact rationals, no
     rounding at all) and `Decimal` must agree with it to a relative error of 1e-20.

**They found a real bug.** The first version checked `sum(weights) == 1` with
`Decimal`. Decimal rounds every addition to 28 significant digits, so the same
weights added up to `1` in one order and to `0.9999999999999999999999999999` in
another: a valid allocation was rejected depending on dict order. The fix sums
weights as exact `Fraction`s, and a deterministic regression test pins the
counterexample (commit `e58d6c1`).

## Why Python, and when Go or Rust would make sense

- **Python** because what makes the calculation correct is exact decimal arithmetic,
  and `decimal` and `fractions` are in the standard library. It is also in Fintual's
  stack. Ruby (`BigDecimal`, `Rational`) would be just as correct. TypeScript would
  need a third-party decimal library, since `number` is a binary float.
- **Measured cost:** `rebalance()` takes ~0.01 ms for 10 stocks, ~1 ms for 1,000 and
  ~11 ms for 10,000 (Apple Silicon, Python 3.14). It grows linearly. A personal
  portfolio has tens of stocks, so CPU is not the bottleneck; fetching prices over the
  network is.
- **Go or Rust** would pay off in a different product: rebalancing millions of
  portfolios in a batch, or real-time drift monitoring on every price tick. Then a
  compiled language with fixed-point integers (amounts in micro-units as `int64`/
  `i128`) could give 10-100x less CPU and memory. Even in that case I would first
  vectorize the batch (one pass over all portfolios) and measure, because the
  algorithm stays O(n) whatever the language. The tests here define the expected
  behavior, so a port would have a test oracle to check it against.

## Next steps toward a product

- **Whole-share brokers:** round each order down to the broker's share increment,
  then redistribute the leftover cash greedily, and report the residual drift.
- **Cash:** treat cash as a position with its own target weight, so deposits and
  withdrawals rebalance in the same pass.
- **Costs and taxes:** prefer buying with new deposits over selling, and pick which
  lots to sell to minimize fees and taxes. That turns it into an optimization
  problem.
- **Price freshness:** carry the price timestamp in `Stock` and refuse to rebalance on
  stale quotes.
- **Execution:** persist `Order`s with an idempotency key and execute them
  sells-first, handling partial fills.

## LLM usage

This solution was built together with Claude (Claude Code), as the statement allows.
The full conversation, including the planning, the language choice and the bug found
by the property tests, is in [`docs/llm-conversation.md`](docs/llm-conversation.md).
