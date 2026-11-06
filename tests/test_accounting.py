import numpy as np
import pandas as pd
import pytest

from cashcycle.core import ageing, collection_curve, weekly_collection


def tables():
    inv = pd.DataFrame(
        [
            dict(
                invoice="A",
                customer="C",
                group="regular",
                issued="2025-01-01",
                due="2025-01-31",
                amount=100.0,
                disputed=False,
            )
        ]
    )
    paid = pd.DataFrame(
        [dict(invoice="A", date="2025-01-20", amount=30.0), dict(invoice="A", date="2025-03-01", amount=60.0)]
    )
    credits = pd.DataFrame([dict(invoice="A", date="2025-01-25", amount=10.0)])
    return inv, paid, credits


def test_as_of_partial_cash_and_credits():
    inv, paid, credits = tables()
    row = ageing(inv, paid, credits, "2025-01-31").iloc[0]
    assert row.outstanding == 60
    assert row.bucket == "Current"
    assert ageing(inv, paid, credits, "2025-03-01").outstanding.sum() == 0


def test_future_payments_do_not_change_as_of_curve():
    inv, paid, credits = tables()
    a = collection_curve(inv, paid, credits, "2025-01-31", "regular")
    paid.loc[1, "amount"] = 9000
    b = collection_curve(inv, paid, credits, "2025-01-31", "regular")
    np.testing.assert_allclose(a, b)
    assert np.all(np.diff(a) <= 1e-12)


def test_receipts_never_exceed_balance():
    survival = np.exp(-np.arange(361) / 45)
    values = weekly_collection(100, 40, survival)
    assert values.min() >= 0
    assert values.sum() <= 100
    assert weekly_collection(100, 500, survival).sum() == 0


def test_overallocated_payment_rejected():
    inv, paid, credits = tables()
    paid.loc[0, "amount"] = 150
    with pytest.raises(ValueError, match="Overallocated"):
        ageing(inv, paid, credits, "2025-01-31")


def test_forecast_does_not_use_future_cash_or_invoices():
    from cashcycle.core import forecast

    inv, paid, credits = tables()
    bills = pd.DataFrame(
        [dict(bill="B", issued="2025-01-01", due="2025-02-15", paid_date="2025-02-15", amount=20.0)]
    )
    operating = pd.DataFrame(columns=["date", "amount"])
    first, _ = forecast(inv, paid, credits, bills, operating, "2025-01-31", 100.0)
    paid.loc[1, "amount"] = 90000
    inv.loc[1] = ["FUTURE", "X", "regular", "2025-02-01", "2025-03-01", 50000.0, False]
    bills.loc[1] = ["FUTURE", "2025-02-01", "2025-02-15", "2025-02-15", 99999.0]
    second, _ = forecast(inv, paid, credits, bills, operating, "2025-01-31", 100.0)
    pd.testing.assert_frame_equal(first, second)


def test_zero_evidence_curve_does_not_force_receipts():
    survival = np.ones(361)
    assert weekly_collection(1000.0, 15, survival).sum() == 0
