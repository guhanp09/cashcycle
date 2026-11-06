"""As-of accounting and censored dollar-weighted collection curves."""

from datetime import timedelta

import numpy as np
import pandas as pd


def ageing(invoices, payments, credits, as_of):
    cutoff = pd.Timestamp(as_of)
    inv = invoices[pd.to_datetime(invoices.issued) <= cutoff].copy()
    paid = payments[pd.to_datetime(payments.date) <= cutoff].groupby("invoice").amount.sum()
    credit = credits[pd.to_datetime(credits.date) <= cutoff].groupby("invoice").amount.sum()
    inv["paid"] = inv.invoice.map(paid).fillna(0)
    inv["credited"] = inv.invoice.map(credit).fillna(0)
    inv["outstanding"] = inv.amount - inv.paid - inv.credited
    if (inv.outstanding < -0.011).any():
        raise ValueError("Overallocated payment or credit")
    inv["outstanding"] = inv.outstanding.clip(lower=0).round(2)
    inv["age"] = (cutoff - pd.to_datetime(inv.issued)).dt.days
    inv["overdue"] = (cutoff - pd.to_datetime(inv.due)).dt.days
    inv["bucket"] = pd.cut(
        inv.overdue, [-np.inf, 0, 30, 60, 90, np.inf], labels=["Current", "1–30", "31–60", "61–90", "90+"]
    )
    return inv


def collection_curve(invoices, payments, credits, as_of, group, max_age=360):
    """Discrete dollar-weighted product-limit curve using only cash known at cutoff.

    Invoice dollars leave the risk set through receipts (event), credit notes (censor),
    or the valuation cutoff (censor). This is descriptive, not a causal collection model.
    """
    cutoff = pd.Timestamp(as_of)
    inv = invoices[(invoices.group == group) & (pd.to_datetime(invoices.issued) <= cutoff)].copy()
    start_date = cutoff - timedelta(days=730)
    inv = inv[pd.to_datetime(inv.issued) >= start_date]
    events = np.zeros(max_age + 1)
    removed = np.zeros(max_age + 1)
    paid_lookup = payments[pd.to_datetime(payments.date) <= cutoff].groupby("invoice")
    credit_lookup = credits[pd.to_datetime(credits.date) <= cutoff].groupby("invoice")
    total = float(inv.amount.sum())
    for row in inv.itertuples():
        issue = pd.Timestamp(row.issued)
        balance = float(row.amount)
        for records, cash in [(paid_lookup, True), (credit_lookup, False)]:
            if row.invoice in records.groups:
                for item in records.get_group(row.invoice).itertuples():
                    age = max(0, min(max_age, (pd.Timestamp(item.date) - issue).days))
                    value = min(balance, item.amount)
                    removed[age] += value
                    if cash:
                        events[age] += value
                    balance -= value
        age = max(0, min(max_age, (cutoff - issue).days))
        removed[age] += max(0, balance)
    risk = total
    survival = np.ones(max_age + 1)
    s = 1.0
    last_observed = 0
    for age in range(max_age + 1):
        if risk > 1e-9:
            s *= max(0, 1 - events[age] / risk)
            if events[age] > 0:
                last_observed = age
        survival[age] = s
        risk -= removed[age]
    # Beyond observed payment support, keep survival flat; do not force eventual collection.
    survival[last_observed + 1 :] = survival[last_observed]
    return survival


def weekly_collection(balance, age, survival, horizon_days=91, accelerate=0):
    """Conditional receipts for outstanding dollars given survival to the as-of age."""
    age = max(0, int(age))
    if age >= len(survival) - 1 or survival[age] <= 1e-12:
        return np.zeros(13)
    daily = []
    for day in range(1, horizon_days + 1):
        previous = min(len(survival) - 1, age + day - 1 + accelerate)
        current = min(len(survival) - 1, age + day + accelerate)
        # Acceleration redistributes only forecastable receipts; accumulated early mass goes in day 1.
        before = survival[age] if day == 1 else survival[previous]
        daily.append(max(0, balance * (before - survival[current]) / survival[age]))
    return np.array(daily, dtype=float).reshape(13, 7).sum(axis=1)


def forecast(
    invoices, payments, credits, bills, operating, as_of, opening_cash, method="behaviour", scenario="base"
):
    cutoff = pd.Timestamp(as_of)
    ar = ageing(invoices, payments, credits, cutoff)
    ar = ar[ar.outstanding > 0.01]
    weeks = pd.DataFrame(
        {"week": np.arange(1, 14), "week_end": [cutoff + timedelta(days=7 * i) for i in range(1, 14)]}
    )
    receipts = np.zeros(13)
    curves = {
        group: collection_curve(invoices, payments, credits, cutoff, group)
        for group in invoices.group.unique()
    }
    candidates = []
    for row in ar.itertuples():
        if method == "due_date":
            values = np.zeros(13)
            day = max(1, (pd.Timestamp(row.due) - cutoff).days)
            if day <= 91 and not row.disputed:
                values[(day - 1) // 7] = row.outstanding
        else:
            values = weekly_collection(
                row.outstanding,
                row.age,
                curves[row.group],
                accelerate=7 if scenario == "improvement" and not row.disputed else 0,
            )
            if row.disputed:
                values *= 0.25
        if scenario == "downside":
            values = np.r_[0.0, values[:-1]] * 0.8
        receipts += values
        candidates.append(
            {
                "invoice": row.invoice,
                "customer": row.customer,
                "outstanding": row.outstanding,
                "disputed": row.disputed,
                "expected_4wk_receipts": float(values[:4].sum()),
                "expected_13wk_receipts": float(values.sum()),
            }
        )
    existing = receipts.copy()
    # Forecast newly issued business from trailing 90-day invoicing, not future ledger records.
    trailing = invoices[
        (pd.to_datetime(invoices.issued) > cutoff - timedelta(days=90))
        & (pd.to_datetime(invoices.issued) <= cutoff)
    ]
    for group, subset in trailing.groupby("group"):
        daily_sales = subset.amount.sum() / 90
        if scenario == "downside":
            daily_sales *= 0.9
        survival = curves[group]
        for issue_day in range(1, 92):
            for day in range(issue_day + 1, 92):
                age = day - issue_day
                prob = max(0, survival[age - 1] - survival[age])
                receipts[(day - 1) // 7] += daily_sales * prob
    supplier = np.zeros(13)
    committed = bills[(pd.to_datetime(bills.issued) <= cutoff) & (pd.to_datetime(bills.paid_date) > cutoff)]
    for row in committed.itertuples():
        day = max(1, (pd.Timestamp(row.due) - cutoff).days)
        if day <= 91:
            supplier[(day - 1) // 7] += row.amount
    # New purchases are based on a documented 55% assumed purchase/sales ratio and 30-day terms.
    daily_purchase = trailing.amount.sum() / 90 * 0.55
    for day in range(31, 92):
        supplier[(day - 1) // 7] += daily_purchase
    opex = np.zeros(13)
    # Fixed monthly calendar is a planning assumption, independent of future actual cash values.
    end = cutoff + timedelta(days=91)
    for date in pd.date_range(cutoff + timedelta(days=1), end):
        expense = (90000 if date.day == 28 else 0) + (26000 if date.day == 5 else 0)
        opex[((date - cutoff).days - 1) // 7] += expense
    weeks["existing_ar_receipts"] = existing
    weeks["new_business_receipts"] = receipts - existing
    weeks["receipts"] = receipts
    weeks["supplier_payments"] = supplier
    weeks["operating_payments"] = opex
    weeks["net_cash"] = receipts - supplier - opex
    weeks["closing_cash"] = opening_cash + weeks.net_cash.cumsum()
    weeks["opening_cash"] = np.r_[opening_cash, weeks.closing_cash.to_numpy()[:-1]]
    actions = pd.DataFrame(candidates).sort_values("expected_4wk_receipts", ascending=False)
    return weeks, actions
