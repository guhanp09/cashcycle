from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import xlsxwriter

from .core import ageing, forecast
from .io import ROOT, chart, dump, report


def generate(seed=73):
    rng = np.random.default_rng(seed)
    invoices, payments, credits, bills, operating = [], [], [], [], []
    customers = pd.DataFrame(
        [dict(customer=f"C{i:03}", group=["prompt", "regular", "slow"][i % 3]) for i in range(45)]
    )
    counter = 0
    for date in pd.date_range("2024-01-01", "2026-06-30"):
        season = 1.25 if date.month in [10, 11, 12] else 1
        for _ in range(int(rng.poisson(4 * season))):
            customer = customers.iloc[int(rng.integers(0, len(customers)))]
            amount = round(float(rng.lognormal(8, 0.7)), 2)
            due = date + timedelta(days=30)
            disputed = bool(rng.random() < 0.045)
            inv = f"I{counter:06}"
            invoices.append(
                dict(
                    invoice=inv,
                    customer=customer.customer,
                    group=customer.group,
                    issued=date.date().isoformat(),
                    due=due.date().isoformat(),
                    amount=amount,
                    disputed=disputed,
                )
            )
            credit = round(amount * 0.12, 2) if rng.random() < 0.06 else 0
            if credit:
                credits.append(
                    dict(invoice=inv, date=(date + timedelta(days=20)).date().isoformat(), amount=credit)
                )
            remaining = round(amount - credit, 2)
            delay = {"prompt": -3, "regular": 12, "slow": 46}[customer.group]
            lag = max(3, int(30 + delay + rng.normal(0, 8))) + (80 if disputed else 0)
            if rng.random() > (0.16 if disputed else 0.025):
                first = round(remaining * 0.4, 2)
                for offset, value in [(lag, first), (lag + 14, round(remaining - first, 2))]:
                    payments.append(
                        dict(
                            invoice=inv,
                            date=(date + timedelta(days=offset)).date().isoformat(),
                            amount=value,
                        )
                    )
            cost = round(amount * 0.55, 2)
            bills.append(
                dict(
                    bill=f"B{counter:06}",
                    issued=date.date().isoformat(),
                    due=(date + timedelta(days=30)).date().isoformat(),
                    paid_date=(date + timedelta(days=30)).date().isoformat(),
                    amount=cost,
                )
            )
            counter += 1
        if date.day in [5, 28]:
            operating.append(
                dict(
                    date=date.date().isoformat(),
                    category="payroll" if date.day == 28 else "rent and overhead",
                    amount=90000 if date.day == 28 else 26000,
                )
            )
    # A committed equipment purchase creates a liquidity problem despite positive trading cash generation.
    bills.append(
        dict(
            bill="CAPEX-001", issued="2025-10-15", due="2026-01-20", paid_date="2026-01-20", amount=2200000.0
        )
    )
    tables = {
        "customers": customers,
        "invoices": pd.DataFrame(invoices),
        "payments": pd.DataFrame(payments),
        "credits": pd.DataFrame(credits),
        "bills": pd.DataFrame(bills),
        "operating": pd.DataFrame(operating),
    }
    out = ROOT / "data/processed"
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    dump(
        ROOT / "data/provenance.json",
        dict(
            kind="fully simulated business ledger",
            seed=seed,
            currency="INR",
            dates="2024-01-01 to 2026-06-30 invoice issuance; payments can occur later",
            opening_cash_2024_01_01=200000,
            committed_capex="INR 2,200,000 equipment purchase committed 2025-10-15, paid 2026-01-20; capital cash outflow, not operating expense",
            caveats="Generated group payment patterns are known to the simulation author; backtests are synthetic experiments, not external validation.",
        ),
    )
    return tables


def load():
    return {
        name: pd.read_csv(ROOT / f"data/processed/{name}.csv")
        for name in ["customers", "invoices", "payments", "credits", "bills", "operating"]
    }


def cash_at(tables, cutoff):
    cutoff = pd.Timestamp(cutoff)
    receipts = tables["payments"].loc[pd.to_datetime(tables["payments"].date) <= cutoff, "amount"].sum()
    bills = tables["bills"].loc[pd.to_datetime(tables["bills"].paid_date) <= cutoff, "amount"].sum()
    opex = tables["operating"].loc[pd.to_datetime(tables["operating"].date) <= cutoff, "amount"].sum()
    return float(200000 + receipts - bills - opex)


def actual_weeks(tables, cutoff):
    cutoff = pd.Timestamp(cutoff)
    result = []
    for week in range(1, 14):
        a, b = cutoff + timedelta(days=7 * (week - 1)), cutoff + timedelta(days=7 * week)

        def total(table, column, start=a, end=b):
            dates = pd.to_datetime(table[column])
            return float(table.loc[(dates > start) & (dates <= end), "amount"].sum())

        receipts = total(tables["payments"], "date")
        suppliers = total(tables["bills"], "paid_date")
        opex = total(tables["operating"], "date")
        result.append(
            dict(
                week=week,
                actual_receipts=receipts,
                actual_net=receipts - suppliers - opex,
                actual_closing=cash_at(tables, b),
            )
        )
    return pd.DataFrame(result)


def workbook(ar, scenarios, opening):
    target = ROOT / "reports/cash_plan.xlsx"
    with xlsxwriter.Workbook(target) as book:
        money = book.add_format({"num_format": "#,##0.00;[Red](#,##0.00)"})
        header = book.add_format({"bold": True, "bg_color": "#17324d", "font_color": "white"})
        inputs = book.add_worksheet("Inputs")
        inputs.write_row(0, 0, ["Driver", "Value", "Meaning"], header)
        for i, row in enumerate(
            [
                ("Opening cash", opening, "As-of ledger balance, INR"),
                ("Receipt multiplier", 1, "Editable collection sensitivity"),
                ("Supplier multiplier", 1, "Editable purchase sensitivity"),
                ("Operating multiplier", 1, "Editable cost sensitivity"),
                ("Minimum cash", 0, "Shortfall threshold"),
                ("Data status", "SIMULATED", "All ledgers are generated"),
            ],
            1,
        ):
            inputs.write_row(i, 0, row)
        inputs.set_column(0, 0, 25)
        inputs.set_column(1, 1, 20)
        inputs.set_column(2, 2, 45)
        raw = book.add_worksheet("Receivables")
        columns = ["invoice", "customer", "amount", "paid", "credited", "outstanding", "overdue", "bucket"]
        raw.write_row(0, 0, columns, header)
        for i, row in enumerate(ar[columns].astype({"bucket": str}).itertuples(index=False, name=None), 1):
            raw.write_row(i, 0, row)
        raw.autofilter(0, 0, len(ar), len(columns) - 1)
        raw.freeze_panes(1, 0)
        raw.set_column(0, 7, 18)
        control = book.add_worksheet("Controls")
        control.write_row(0, 0, ["Check", "Difference; must be zero"], header)
        last = len(ar) + 1
        control.write(1, 0, "Receivables equation")
        control.write_formula(
            1,
            1,
            f"=SUM(Receivables!C2:C{last})-SUM(Receivables!D2:D{last})-SUM(Receivables!E2:E{last})-SUM(Receivables!F2:F{last})",
            money,
            0,
        )
        for name, frame in scenarios.items():
            sheet = book.add_worksheet(name.title())
            cols = [
                "Week",
                "Opening cash",
                "Receipts",
                "Suppliers",
                "Operating",
                "Net movement",
                "Closing cash",
                "Below minimum",
            ]
            sheet.write_row(0, 0, cols, header)
            for i, row in enumerate(frame.itertuples(), 1):
                excel = i + 1
                sheet.write(i, 0, row.week)
                sheet.write_formula(
                    i, 1, "=Inputs!$B$2" if i == 1 else f"=G{excel - 1}", money, row.opening_cash
                )
                sheet.write_formula(i, 2, f"={row.receipts:.12f}*Inputs!$B$3", money, row.receipts)
                sheet.write_formula(
                    i, 3, f"={row.supplier_payments:.12f}*Inputs!$B$4", money, row.supplier_payments
                )
                sheet.write_formula(
                    i, 4, f"={row.operating_payments:.12f}*Inputs!$B$5", money, row.operating_payments
                )
                sheet.write_formula(i, 5, f"=C{excel}-D{excel}-E{excel}", money, row.net_cash)
                sheet.write_formula(i, 6, f"=B{excel}+F{excel}", money, row.closing_cash)
                sheet.write_formula(i, 7, f"=G{excel}<Inputs!$B$6", None, bool(row.closing_cash < 0))
            sheet.set_column(0, 7, 21)
            sheet.freeze_panes(1, 2)
            sheet.conditional_format(
                "G2:G14",
                {
                    "type": "cell",
                    "criteria": "<",
                    "value": 0,
                    "format": book.add_format({"bg_color": "#ffd7d7"}),
                },
            )
            plot = book.add_chart({"type": "line"})
            plot.add_series(
                {
                    "name": "Closing cash",
                    "categories": [name.title(), 1, 0, 13, 0],
                    "values": [name.title(), 1, 6, 13, 6],
                }
            )
            sheet.insert_chart("J2", plot)


def run(as_of="2025-12-31"):
    t = generate()
    args = [t[n] for n in ["invoices", "payments", "credits", "bills", "operating"]]
    opening = cash_at(t, as_of)
    ar = ageing(*args[:3], as_of)
    ar.to_csv(ROOT / "reports/receivables_ageing.csv", index=False)
    scenarios = {}
    for scenario in ["base", "downside", "improvement"]:
        frame, actions = forecast(*args, as_of, opening, scenario=scenario)
        frame.to_csv(ROOT / f"reports/forecast_{scenario}.csv", index=False)
        scenarios[scenario] = frame
        if scenario == "base":
            actions.to_csv(ROOT / "reports/collection_priorities.csv", index=False)
    rows = []
    for cutoff in pd.date_range("2025-01-31", "2025-12-31", freq="ME"):
        actual = actual_weeks(t, cutoff)
        for method in ["due_date", "behaviour"]:
            predicted, _ = forecast(*args, cutoff, cash_at(t, cutoff), method=method)
            for p, a in zip(predicted.itertuples(), actual.itertuples(), strict=True):
                rows.append(
                    dict(
                        cutoff=cutoff.date().isoformat(),
                        method=method,
                        week=p.week,
                        receipts_error=p.receipts - a.actual_receipts,
                        closing_error=p.closing_cash - a.actual_closing,
                        actual_shortfall=a.actual_closing < 0,
                        predicted_shortfall=p.closing_cash < 0,
                    )
                )
    backtest = pd.DataFrame(rows)
    backtest.to_csv(ROOT / "reports/backtests.csv", index=False)
    summaries = []
    for method, group in backtest.groupby("method"):
        summaries.append(
            dict(
                method=method,
                weekly_receipt_mae=float(group.receipts_error.abs().mean()),
                closing_cash_mae=float(group.closing_error.abs().mean()),
                missed_shortfalls=int((group.actual_shortfall & ~group.predicted_shortfall).sum()),
                false_shortfall_warnings=int((~group.actual_shortfall & group.predicted_shortfall).sum()),
            )
        )
    workbook(ar, scenarios, opening)
    combined = pd.concat([f.assign(scenario=n) for n, f in scenarios.items()])
    chart(
        px.line(
            combined,
            x="week_end",
            y="closing_cash",
            color="scenario",
            title="Thirteen-week cash scenarios — simulated business",
        ),
        "cash_scenarios",
    )
    metrics = dict(
        as_of=as_of,
        data_kind="fully simulated",
        invoices=len(t["invoices"]),
        opening_cash=opening,
        receivables=float(ar.outstanding.sum()),
        ledger_reconciliation_difference=float(
            ar.amount.sum() - ar.paid.sum() - ar.credited.sum() - ar.outstanding.sum()
        ),
        minimum_base_cash=float(scenarios["base"].closing_cash.min()),
        backtests=summaries,
    )
    report(
        "CashCycle",
        f"""# Receivables and liquidity review

All customer, invoice, payment and cost records are simulated with seed 73. Currency: INR. The simulation embeds group payment patterns; model performance on it is not evidence of performance on real customers.

At {as_of}, receivables are INR {ar.outstanding.sum():,.2f} and ledger cash is INR {opening:,.2f}. Invoice amount less cash received and credits reconciles to outstanding balances. Payment and credit records dated after the cutoff are excluded.

The base forecast reaches a minimum weekly closing cash of INR {metrics["minimum_base_cash"]:,.2f}. A simulated INR 2,200,000 equipment purchase, committed on 2025-10-15 and due on 2026-01-20, creates a cash requirement despite positive trading cash generation. It is a capital outflow, not an operating expense. Existing receivables use dollar-weighted product-limit collection curves with right-censoring. Disputed balances receive an explicit 75% collection haircut. New business uses trailing 90-day average issuance; new purchases assume 55% of sales and 30-day terms. Fixed monthly payroll and overhead are planning assumptions.

Twelve historical cutoffs compare contractual due-date collection with behaviour-based forecasts. See backtests.csv and metrics.json for receipt error, cash error and shortfall warnings. Overlapping horizons are correlated; do not treat the 156 weekly rows per model as independent experiments.

Recommendation: begin the collection review with the highest expected four-week receipts in collection_priorities.csv, treating disputed items as a separate resolution queue. Improvement assumes a seven-day acceleration for undisputed existing balances; it is a hypothetical scenario, not an estimated causal effect.

The Excel workbook has editable receipt and cost multipliers, cash roll-forward formulas, zero-difference controls, cached values and scenario charts. Changes recalculate in Excel. No real cash release or savings are claimed.

Limitations: no tax, interest, foreign exchange, inventory capacity or committed credit facility. Dollar-weighted censoring assumes credits are non-informative removals, which may be unrealistic. Future sales and collection distributions can shift. The simulated counterfactuals use fixed group assumptions.
""",
        metrics,
    )
    return metrics
