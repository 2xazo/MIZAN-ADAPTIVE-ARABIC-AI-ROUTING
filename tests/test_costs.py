import math

import pytest

from mizan.costs import BudgetError, Ledger, cost_usd, price_for, require_verified


def test_cost_formula():
    assert math.isclose(cost_usd(1_000_000, 500_000, {"input": 2.0, "output": 8.0}), 6.0)
    assert math.isclose(cost_usd(200, 1, {"input": 0.4, "output": 1.6}), 200 * 0.4e-6 + 1.6e-6)


def test_missing_price_refused():
    with pytest.raises(BudgetError):
        price_for({"models": {"x": {"input": None, "output": None}}}, "x")


def test_unverified_prices_refused():
    with pytest.raises(BudgetError):
        require_verified({"verified": False})


def test_ledger_stops_before_limit(tmp_path):
    led = Ledger(tmp_path / "l.jsonl", limit_usd=1.0)
    led.record("m", "1", 10, 1, 0.7)
    assert math.isclose(led.spent(), 0.7)
    led.check(0.29)
    with pytest.raises(BudgetError):
        led.check(0.31)
