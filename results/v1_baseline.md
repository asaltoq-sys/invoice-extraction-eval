# Results: v1_baseline.txt

- Model: `claude-sonnet-5`
- Runs per document: 3
- Date: 2026-09-20 13:42

| Field | Accuracy |
|---|---|
| doc_type | 10% |
| supplier_name | 100% |
| supplier_tax_id | 100% |
| document_number | 100% |
| document_date | 10% |
| delivery_note_numbers | 90% |
| order_number | 100% |
| vat_rates | 80% |
| total | 83% |
| line_count | 90% |
| lines.quantity | 90% |
| lines.unit_price | 90% |
| lines.line_total | 90% |

**Documents fully correct: 10%**

## Failures

- inv_01: doc_type, document_date
- inv_02: doc_type, document_date, total
- inv_03: doc_type, document_date
- inv_04: doc_type, document_date
- inv_05: doc_type, document_date, line_count, lines.line_total, lines.quantity, lines.unit_price
- inv_06: delivery_note_numbers, doc_type, document_date, total, vat_rates
- inv_08: doc_type, document_date, vat_rates
- inv_09: doc_type, document_date
- inv_10: doc_type, document_date, vat_rates