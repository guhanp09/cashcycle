import pandas as pd
import plotly.express as px
import streamlit as st

from .core import ageing, forecast
from .io import ROOT, require, theme
from .pipeline import cash_at, load


def main():
    theme("CashCycle", "Receivables, collection priorities, and thirteen-week liquidity planning")
    require(ROOT / "reports/metrics.json", "cashcycle run")
    require(ROOT / "data/processed/invoices.csv", "cashcycle run")
    st.info("Fully simulated INR business ledger. Scenario improvements are hypothetical.")
    t = load()
    as_of = st.sidebar.date_input(
        "Valuation date",
        pd.Timestamp("2025-12-31").date(),
        min_value=pd.Timestamp("2025-01-01").date(),
        max_value=pd.Timestamp("2026-03-31").date(),
    )
    scenario = st.sidebar.selectbox("Scenario", ["base", "downside", "improvement"])
    method = st.sidebar.selectbox("Collection assumption", ["behaviour", "due_date"])
    opening = st.sidebar.number_input("Opening cash (INR)", value=cash_at(t, as_of))
    args = [t[n] for n in ["invoices", "payments", "credits", "bills", "operating"]]
    ar = ageing(*args[:3], as_of)
    frame, actions = forecast(*args, as_of, opening, method, scenario)
    cols = st.columns(3)
    cols[0].metric("Receivables", f"₹{ar.outstanding.sum():,.0f}")
    cols[1].metric("Minimum closing cash", f"₹{frame.closing_cash.min():,.0f}")
    cols[2].metric("Weeks below zero", int((frame.closing_cash < 0).sum()))
    tabs = st.tabs(["Cash forecast", "Receivables", "Collection priorities", "Backtests"])
    with tabs[0]:
        st.plotly_chart(px.line(frame, x="week_end", y="closing_cash", markers=True), width="stretch")
        st.dataframe(frame, hide_index=True)
        st.caption(
            "Future new-business invoices and purchases use historical averages and explicit planning assumptions."
        )
    with tabs[1]:
        buckets = ar.groupby("bucket", observed=False).outstanding.sum().reset_index()
        st.plotly_chart(px.bar(buckets, x="bucket", y="outstanding"), width="stretch")
        st.dataframe(ar[ar.outstanding > 0.01], hide_index=True)
    with tabs[2]:
        st.dataframe(actions, hide_index=True)
    with tabs[3]:
        b = pd.read_csv(ROOT / "reports/backtests.csv")
        st.dataframe(b.groupby("method")[["receipts_error", "closing_error"]].agg(lambda s: s.abs().mean()))
        st.caption("Synthetic, overlapping forecast windows; descriptive performance only.")
    st.download_button(
        "Download formula-driven cash plan", (ROOT / "reports/cash_plan.xlsx").read_bytes(), "cash_plan.xlsx"
    )
