# Data dictionary and provenance

Fully simulated INR business ledger, seed 73. Invoice issuance spans 2024-01-01 to 2026-06-30; payments may occur later. Customer groups have simulated payment patterns, partial payments, credit notes and non-payment. A simulated INR 2,200,000 equipment purchase is committed on 2025-10-15 and due 2026-01-20. It is a capital outflow, not an operating expense. No real customer or bank records are used.

| Ledger | Grain | Key columns |
| --- | --- | --- |
| customers | Customer | customer, group |
| invoices | Invoice | invoice, customer, group, issued, due, amount, disputed |
| payments | Partial cash receipt | invoice, date, amount |
| credits | Credit note | invoice, date, amount |
| bills | Supplier/capital commitment | bill, issued, due, paid_date, amount |
| operating | Operating cash payment | date, category, amount |

All records are synthetic; currency is INR. Receivables use cash and credit postings at
or before valuation. Fixed operating expenses are INR 90,000 on day 28 and INR 26,000 on
day 5 each month. Opening ledger cash on 2024-01-01 is INR 200,000. CAPEX-001 is an
INR 2,200,000 equipment commitment, known from 2025-10-15 and paid on 2026-01-20. It is
included in supplier/committed cash outflows, not interpreted as an operating expense.
The disputed flag is a synthetic invoice attribute known at issuance.
