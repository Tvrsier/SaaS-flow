# VAT Management and Passive Invoices

This document describes the implementation of VAT management and passive invoice import functionality.

## Overview

The system now supports:
- **Passive Invoices**: Import and management of invoices received from suppliers
- **VAT Periods**: Management of monthly and quarterly VAT periods
- **VAT Movements**: Automatic tracking of VAT debit (from active invoices) and credit (from passive invoices)
- **VAT Summary**: Calculation of VAT balance for each period
- **VAT Settlement**: Closing and settlement of VAT periods with payment tracking

## Database Models

### Passive Invoices

- **PassiveInvoice**: Main table for received invoices
- **PassiveInvoiceLine**: Line items of passive invoices
- **PassiveInvoiceVatSummary**: VAT summaries grouped by rate/nature

### VAT Management

- **VatPeriod**: Fiscal periods (monthly or quarterly)
- **VatMovement**: Atomic VAT movements (debit/credit)
- **VatSettlement**: Frozen snapshot of period liquidation

## Services

### PassiveInvoiceImportService

Handles import of passive invoices from FatturaPA XML files.

```python
from app.modules.passive_invoices.services import PassiveInvoiceImportService

service = PassiveInvoiceImportService(db)
result = service.import_from_xml(
    company_id=company_id,
    xml_content=xml_string,
    source_channel="SDI"
)
```

Features:
- XML parsing using FatturaPAParser
- Idempotency based on XML hash
- Automatic creation of VAT movements
- Supplier matching (placeholder for future implementation)

### VatPeriodService

Manages VAT periods.

```python
from app.modules.vat.services import VatPeriodService

service = VatPeriodService(db)
period = service.get_or_create_period(
    company_id=company_id,
    competence_date=date(2026, 1, 15),
    frequency="QUARTERLY"
)
```

Features:
- Automatic period creation
- Support for MONTHLY and QUARTERLY frequencies
- Previous credit carryover
- Period closure and settlement

### VatMovementService

Creates and manages VAT movements.

```python
from app.modules.vat.services import VatMovementService

service = VatMovementService(db)

# From passive invoice
movements = service.create_from_passive_invoice(passive_invoice_id)

# From active invoice
movements = service.create_from_active_invoice(invoice_id)
```

Features:
- Automatic period assignment based on VAT competence date
- DEBIT movements for active invoices
- CREDIT movements for passive invoices
- Protection against modifying closed/settled periods

### VatSummaryService

Calculates VAT summaries and manages settlements.

```python
from app.modules.vat.services import VatSummaryService

service = VatSummaryService(db)

# Calculate summary
summary = service.calculate_period_summary(company_id, period_id)

# Close period and create settlement
settlement = service.close_period_and_create_settlement(company_id, period_id)

# Record payment
settlement = service.record_settlement_payment(
    settlement_id=settlement_id,
    amount_paid=Decimal("300.00"),
    payment_date=date(2026, 5, 16),
    reference="PAYMENT-001"
)
```

## VAT Calculation Logic

The system follows Italian VAT rules:

```
balance = total_debit - total_credit - previous_credit

if balance > 0:
    amount_to_pay = balance
    credit_to_carry = 0
else:
    amount_to_pay = 0
    credit_to_carry = abs(balance)
```

Key points:
- Debit and credit are kept separate (not offset at invoice level)
- Compensation happens only at period closing
- Historical balance is preserved even after payment
- Credit is carried forward to next period

## Scripts

### Test VAT Flow

Run a complete test of the VAT flow:

```bash
python app/scripts/test_vat_flow.py
```

This script:
1. Creates a test company
2. Imports a sample passive invoice
3. Creates VAT movements
4. Calculates VAT summary
5. Creates settlement
6. Prints console output

### Print VAT Summary

Print VAT summary for a specific period:

```bash
python app/scripts/vat_summary_console.py \
    --company-id <company-uuid> \
    --period-id <period-uuid>
```

Example output:

```
================================================================================
VAT SUMMARY 2026-Q1
================================================================================
Company:          12345678-1234-1234-1234-123456789012
Period:           2026-Q1 (2026-01-01 -> 2026-03-31)
Status:           OPEN

Movements:
--------------------------------------------------------------------------------
- DEBIT  | TD01 active invoice          | rate  22.00% | taxable      1000.00 | VAT       220.00
- CREDIT | passive invoice A-15          | rate  22.00% | taxable       300.00 | VAT        66.00

Totals:
--------------------------------------------------------------------------------
Total debit:           220.00
Total credit:           66.00
Previous credit:         0.00
Balance:               154.00
Amount to pay:         154.00
Credit to carry:         0.00
================================================================================
```

## Testing

Run tests with pytest:

```bash
# Run all VAT tests
pytest tests/test_vat_and_passive_invoices.py -v

# Run with console output
pytest tests/test_vat_and_passive_invoices.py -v -s

# Run specific test
pytest tests/test_vat_and_passive_invoices.py::test_passive_invoice_import -v -s
```

## Migration

Apply the database migration:

```bash
# If using alembic_backups directory
alembic -c alembic.ini upgrade head
```

The migration creates:
- passive_invoices table
- passive_invoice_lines table
- passive_invoice_vat_summary table
- vat_periods table
- vat_movements table
- vat_settlements table

## Future Enhancements

### Automatic Period Opening
- Implement background job to automatically open new periods
- Trigger on user login after period expiration
- Configuration per company for frequency (MONTHLY/QUARTERLY)

### SDI Integration
- Connect passive invoice import to SDI notifications
- Update passive invoice status when SDI approves
- Automatic VAT movement creation on SDI approval

### Automatic Settlement
- Schedule automatic period closure
- Email notifications for settlements
- Integration with payment systems

### Supplier Matching
- Match suppliers from passive invoices with existing clients
- Create new supplier records automatically
- Duplicate detection

### Manual Adjustments
- Support for manual VAT movements
- Corrections and adjustments
- Notes and audit trail

## Notes

- The current implementation assumes **QUARTERLY** VAT periods by default
- Company VAT frequency should be configurable (future enhancement)
- Passive invoice registration_date and vat_competence_date default to invoice_date
- These dates should be configurable by user (future enhancement)
- XML storage to S3 is not yet implemented
- Supplier/client matching is not yet implemented
