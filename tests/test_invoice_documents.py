from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from lxml import etree

from app.modules.invoices.documents.dto import AddressDTO, InvoiceDocumentDTO, InvoiceLineDTO, PartyDTO, VatSummaryDTO
from app.modules.invoices.documents.paths import get_invoice_pdf_path, get_invoice_xml_path, sanitize_filename
from app.modules.invoices.documents.pdf_generator import build_invoice_pdf
from app.modules.invoices.documents.service import InvoiceDocumentService
from app.modules.invoices.documents.xml_generator import build_invoice_xml


@pytest.fixture()
def document_dto() -> InvoiceDocumentDTO:
    address = AddressDTO("Via Roma 1", None, "00100", "Roma", "RM", "IT")
    return InvoiceDocumentDTO(
        invoice_id=uuid4(), invoice_number="2026/026", issue_date=date(2026, 7, 11), document_type="TD01", currency="EUR",
        seller=PartyDTO("GestPro SRL", None, None, "01234567890", "01234567890", address, email="info@example.com"),
        customer=PartyDTO("Cliente SRL", None, None, "09876543210", "09876543210", address, recipient_code="ABC1234"),
        lines=(InvoiceLineDTO(1, "Consulenza", Decimal("1"), "h", Decimal("100"), Decimal("100"), Decimal("22"), None, Decimal("22"), Decimal("122")),),
        vat_summaries=(VatSummaryDTO(Decimal("22"), None, Decimal("100"), Decimal("22")),),
        payment_details=None, related_documents=(), ddt=(), taxable_amount=Decimal("100"), vat_amount=Decimal("22"),
        total_amount=Decimal("122"), vat_collectability="S",
    )


def test_sanitize_filename_and_paths(tmp_path: Path, document_dto: InvoiceDocumentDTO) -> None:
    assert sanitize_filename("../../2026/026") == "2026_026"
    assert get_invoice_pdf_path(tmp_path, document_dto.invoice_id, document_dto.invoice_number).name == "2026_026.pdf"
    assert get_invoice_xml_path(tmp_path, document_dto.invoice_id, document_dto.invoice_number).name == "2026_026.xml"


def test_generators_create_valid_documents(document_dto: InvoiceDocumentDTO) -> None:
    pdf = build_invoice_pdf(document_dto)
    xml = build_invoice_xml(document_dto)
    assert pdf.startswith(b"%PDF")
    assert etree.fromstring(xml).tag.endswith("FatturaElettronica")
    assert b"<EsigibilitaIVA>S</EsigibilitaIVA>" in xml


def test_atomic_write_replaces_file(tmp_path: Path) -> None:
    path = tmp_path / "invoice.xml"
    path.write_bytes(b"old")
    InvoiceDocumentService._atomic_write(path, b"new")
    assert path.read_bytes() == b"new"
    assert list(tmp_path.glob("*.tmp")) == []
