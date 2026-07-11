class InvoiceDocumentError(Exception):
    """Base exception for invoice document operations."""


class InvoiceNotFoundError(InvoiceDocumentError):
    pass


class InvalidInvoiceNumberError(InvoiceDocumentError):
    pass


class InvoiceDocumentGenerationError(InvoiceDocumentError):
    pass
