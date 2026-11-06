# CashCycle methodology

Receivables equal issued invoice amount minus payments and credits posted at or before valuation. Future-dated records are excluded. Negative balances fail validation rather than being silently accepted. Ageing is based on contractual due dates, while collection curves use elapsed days since invoice issue.

Group-specific product-limit curves use dollar amounts at risk. Partial receipts remove dollars as cash events; credits and valuation cutoffs remove dollars as censoring. Curves use only information available at the cutoff and a trailing two-year issuance window. Survival is flat beyond observed payment support, rather than forcing eventual recovery. Non-informative credit censoring is an assumption that may be unrealistic in real collections.

Outstanding-dollar receipt probabilities are conditional on surviving unpaid to the current age. Disputed balances receive an explicit 75% haircut. Due-date baseline collects undisputed overdue balances in week one and other balances at due date. Future new-business receipts use trailing 90-day issuance, group mix and historical curves. Future ordinary purchases assume 55% of sales and 30-day terms. Existing committed bills, including the equipment purchase when known, are separately scheduled. Payroll and overhead follow explicit calendar assumptions.

The downside delays existing-AR collections one week, reduces those receipts 20% and new invoicing 10%. Improvement accelerates undisputed existing balances seven days; it is a hypothetical scenario, not an estimated treatment effect. Priority ranks expected four-week cash, not invoice face value. This ranks potential receipts, not incremental causal benefit from contacting a customer.

Twelve monthly cutoffs in 2025 are backtested over thirteen weeks against simulated later cash. Windows overlap and the author knows the generating process. Performance is a synthetic experiment. No real savings are claimed. Forecasts omit taxes, interest, FX, financing facilities and inventory constraints. Editable opening cash is a scenario assumption and should not be confused with historical ledger cash.

## Data flow

Seeded coherent ledger → valuation cutoff → ageing + historical cash → censored collection curves / due-date baseline → weekly receipts and commitments → scenario and backtest comparison → cash planning workbook.
