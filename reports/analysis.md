# Receivables and liquidity review

All customer, invoice, payment and cost records are simulated with seed 73. Currency: INR. The simulation embeds group payment patterns; model performance on it is not evidence of performance on real customers.

At 2025-12-31, receivables are INR 1,428,839.92 and ledger cash is INR 1,763,931.33. Invoice amount less cash received and credits reconciles to outstanding balances. Payment and credit records dated after the cutoff are excluded.

The base forecast reaches a minimum weekly closing cash of INR -353,987.30. A simulated INR 2,200,000 equipment purchase, committed on 2025-10-15 and due on 2026-01-20, creates a cash requirement despite positive trading cash generation. It is a capital outflow, not an operating expense. Existing receivables use dollar-weighted product-limit collection curves with right-censoring. Disputed balances receive an explicit 75% collection haircut. New business uses trailing 90-day average issuance; new purchases assume 55% of sales and 30-day terms. Fixed monthly payroll and overhead are planning assumptions.

Twelve historical cutoffs compare contractual due-date collection with behaviour-based forecasts. See backtests.csv and metrics.json for receipt error, cash error and shortfall warnings. Overlapping horizons are correlated; do not treat the 156 weekly rows per model as independent experiments.

Recommendation: begin the collection review with the highest expected four-week receipts in collection_priorities.csv, treating disputed items as a separate resolution queue. Improvement assumes a seven-day acceleration for undisputed existing balances; it is a hypothetical scenario, not an estimated causal effect.

The Excel workbook has editable receipt and cost multipliers, cash roll-forward formulas, zero-difference controls, cached values and scenario charts. Changes recalculate in Excel. No real cash release or savings are claimed.

Limitations: no tax, interest, foreign exchange, inventory capacity or committed credit facility. Dollar-weighted censoring assumes credits are non-informative removals, which may be unrealistic. Future sales and collection distributions can shift. The simulated counterfactuals use fixed group assumptions.
