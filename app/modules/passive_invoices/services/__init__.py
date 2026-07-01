"""Passive invoice services"""
from app.modules.passive_invoices.services.passive_invoice_import_service import (
    PassiveInvoiceImportService,
    PassiveInvoiceImportResult,
)

__all__ = [
    "PassiveInvoiceImportService",
    "PassiveInvoiceImportResult",
]
