"""Exact numeric conversion shared by the whole module.

Money and weights are handled with ``Decimal`` end to end. Binary floats cannot
represent values such as 0.1 exactly (``0.1 + 0.2 != 0.3``), and in a module that
tells a user how much to buy or sell, those errors leak into real orders.

Floats are rejected on purpose instead of silently converted: by the time a value
is a float the precision is already lost, so the caller must pass ``str``, ``int``
or ``Decimal``.
"""

from decimal import Decimal, InvalidOperation

Number = Decimal | int | str


def to_decimal(value: Number, field: str) -> Decimal:
    """Convert ``value`` to a finite ``Decimal`` or raise a descriptive error."""
    if isinstance(value, float):
        raise TypeError(f"{field} must not be a float; pass a str, int or Decimal")
    if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
        raise TypeError(f"{field} must be a str, int or Decimal, got {type(value).__name__}")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field} is not a valid number: {value!r}") from error
    if not result.is_finite():
        raise ValueError(f"{field} must be finite, got {value!r}")
    return result
