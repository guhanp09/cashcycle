# Engineering notes

Receivables and ledger cash are reconstructed at a valuation cutoff. Later cash, credit notes,
invoices and uncommitted bills do not enter the historical forecast. Overallocated payments
fail validation. Partial payments and credit notes are separately traceable.

Collection curves condition expected receipts on invoice age and the unpaid balance. The
forecast combines existing receivables, assumed new-business receipts, committed payments
and calendar-based operating costs. Each weekly opening balance plus net movement must
equal closing cash. Workbook formulas expose the same roll-forward and sensitivity drivers.

Fixtures check as-of isolation, partial settlements, future-record invariance and bounded
collections. Historical forecast windows overlap. All ledger records and scenario outcomes
are simulated; methodology.md documents the generating and forecasting assumptions.

Tested dependency versions are recorded in constraints.txt and environment.json.
