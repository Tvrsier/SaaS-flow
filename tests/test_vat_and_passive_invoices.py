"""Tests for VAT and Passive Invoices functionality"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Generator
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.db.models.invoice import (
    PassiveInvoice,
    PassiveInvoiceLine,
    PassiveInvoiceVatSummary,
    VatMovement,
    VatPeriod,
    VatSettlement,
)
from app.db.models.user import AccountType, User
from app.modules.invoices.domain.enums import DocumentType, InvoiceStatus
from app.modules.passive_invoices.services.passive_invoice_import_service import PassiveInvoiceImportService
from app.modules.vat.services.vat_movement_service import VatMovementService
from app.modules.vat.services.vat_period_service import VatPeriodService
from app.modules.vat.services.vat_summary_service import VatSummaryService


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False)

SAMPLE_FATTURA_PA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12">
    <FatturaElettronicaHeader>
        <DatiTrasmissione>
            <IdTrasmittente>
                <IdPaese>IT</IdPaese>
                <IdCodice>12345678901</IdCodice>
            </IdTrasmittente>
            <ProgressivoInvio>00001</ProgressivoInvio>
            <FormatoTrasmissione>FPR12</FormatoTrasmissione>
            <CodiceDestinatario>0000000</CodiceDestinatario>
        </DatiTrasmissione>
        <CedentePrestatore>
            <DatiAnagrafici>
                <IdFiscaleIVA>
                    <IdPaese>IT</IdPaese>
                    <IdCodice>12345678901</IdCodice>
                </IdFiscaleIVA>
                <Anagrafica>
                    <Denominazione>Fornitore SRL</Denominazione>
                </Anagrafica>
                <RegimeFiscale>RF01</RegimeFiscale>
            </DatiAnagrafici>
            <Sede>
                <Indirizzo>Via Roma 1</Indirizzo>
                <CAP>00100</CAP>
                <Comune>Roma</Comune>
                <Provincia>RM</Provincia>
                <Nazione>IT</Nazione>
            </Sede>
        </CedentePrestatore>
        <CessionarioCommittente>
            <DatiAnagrafici>
                <IdFiscaleIVA>
                    <IdPaese>IT</IdPaese>
                    <IdCodice>98765432109</IdCodice>
                </IdFiscaleIVA>
                <Anagrafica>
                    <Denominazione>Cliente SRL</Denominazione>
                </Anagrafica>
            </DatiAnagrafici>
            <Sede>
                <Indirizzo>Via Milano 2</Indirizzo>
                <CAP>20100</CAP>
                <Comune>Milano</Comune>
                <Provincia>MI</Provincia>
                <Nazione>IT</Nazione>
            </Sede>
        </CessionarioCommittente>
    </FatturaElettronicaHeader>
    <FatturaElettronicaBody>
        <DatiGenerali>
            <DatiGeneraliDocumento>
                <TipoDocumento>TD01</TipoDocumento>
                <Divisa>EUR</Divisa>
                <Data>2026-01-15</Data>
                <Numero>A-15</Numero>
            </DatiGeneraliDocumento>
        </DatiGenerali>
        <DatiBeniServizi>
            <DettaglioLinee>
                <NumeroLinea>1</NumeroLinea>
                <Descrizione>Servizio di consulenza</Descrizione>
                <Quantita>1.00</Quantita>
                <UnitaMisura>ore</UnitaMisura>
                <PrezzoUnitario>300.00</PrezzoUnitario>
                <PrezzoTotale>300.00</PrezzoTotale>
                <AliquotaIVA>22.00</AliquotaIVA>
            </DettaglioLinee>
            <DatiRiepilogo>
                <AliquotaIVA>22.00</AliquotaIVA>
                <ImponibileImporto>300.00</ImponibileImporto>
                <Imposta>66.00</Imposta>
            </DatiRiepilogo>
        </DatiBeniServizi>
    </FatturaElettronicaBody>
</p:FatturaElettronica>
"""


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    db = TestingSessionLocal(bind=connection)
    transaction = connection.begin()
    db.begin_nested()

    @event.listens_for(db, "after_transaction_end")
    def _restart_savepoint(session: Session, trans) -> None:
        parent = getattr(trans, "parent", None)
        if trans.nested and (parent is None or not parent.nested):
            session.begin_nested()

    try:
        yield db
    finally:
        event.remove(db, "after_transaction_end", _restart_savepoint)
        db.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def test_company(db_session: Session) -> User:
    """Create a test company user"""
    company = User(
        email=f"testcompany_{uuid4()}@example.com",
        account_type=AccountType.azienda,
        partita_iva="98765432109",
        codice_fiscale="98765432109",
        company_name="Test Company SRL",
        phone="+39 02 12345678",
        is_active=True,
        is_verified=True,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def test_passive_invoice_import(db_session: Session, test_company: User):
    """Test importing a passive invoice from XML"""
    import_service = PassiveInvoiceImportService(db_session)

    # Import passive invoice
    result = import_service.import_from_xml(
        company_id=test_company.id,
        xml_content=SAMPLE_FATTURA_PA_XML,
        source_channel="TEST",
    )

    assert result.created is True
    assert result.passive_invoice is not None
    assert result.lines_count == 1
    assert result.vat_summaries_count == 1
    assert result.vat_movements_count == 1

    # Verify passive invoice
    passive_invoice = result.passive_invoice
    assert passive_invoice.company_id == test_company.id
    assert passive_invoice.supplier_name == "Fornitore SRL"
    assert passive_invoice.supplier_vat_number == "12345678901"
    assert passive_invoice.invoice_number == "A-15"
    assert passive_invoice.invoice_date == date(2026, 1, 15)
    assert passive_invoice.document_type == DocumentType.TD01
    assert passive_invoice.currency == "EUR"
    assert passive_invoice.taxable_amount == Decimal("300.00")
    assert passive_invoice.vat_amount == Decimal("66.00")
    assert passive_invoice.total_amount == Decimal("366.00")
    assert passive_invoice.status == InvoiceStatus.READY

    db_session.commit()
    print(f"\n✓ Passive invoice imported successfully: {passive_invoice.id}")


def test_passive_invoice_idempotency(db_session: Session, test_company: User):
    """Test that importing the same XML twice doesn't create duplicates"""
    import_service = PassiveInvoiceImportService(db_session)

    # First import
    result1 = import_service.import_from_xml(
        company_id=test_company.id,
        xml_content=SAMPLE_FATTURA_PA_XML,
        source_channel="TEST",
    )
    assert result1.created is True

    db_session.commit()

    # Second import with same XML
    result2 = import_service.import_from_xml(
        company_id=test_company.id,
        xml_content=SAMPLE_FATTURA_PA_XML,
        source_channel="TEST",
    )
    assert result2.created is False
    assert result2.passive_invoice.id == result1.passive_invoice.id

    print(f"\n✓ Idempotency test passed: same passive invoice returned")


def test_vat_period_creation(db_session: Session, test_company: User):
    """Test VAT period creation"""
    period_service = VatPeriodService(db_session)

    # Create Q1 2026 period
    period = period_service.get_or_create_period(
        company_id=test_company.id,
        competence_date=date(2026, 1, 15),
        frequency="QUARTERLY",
    )

    assert period is not None
    assert period.company_id == test_company.id
    assert period.year == 2026
    assert period.period_index == 1
    assert period.frequency == "QUARTERLY"
    assert period.start_date == date(2026, 1, 1)
    assert period.end_date == date(2026, 3, 31)
    assert period.status == "OPEN"
    assert period.previous_credit == Decimal("0.00")

    db_session.commit()
    print(f"\n✓ VAT period created: {period.year}-Q{period.period_index}")


def test_vat_movements_from_passive_invoice(db_session: Session, test_company: User):
    """Test VAT movements creation from passive invoice"""
    import_service = PassiveInvoiceImportService(db_session)

    movement_service = VatMovementService(db_session)

    # Import passive invoice (movements are created automatically)
    result = import_service.import_from_xml(
        company_id=test_company.id,
        xml_content=SAMPLE_FATTURA_PA_XML,
        source_channel="TEST",
    )

    db_session.commit()

    # Verify movements were created
    assert result.vat_movements_count == 1

    # Get movements
    from sqlalchemy import select

    query = select(VatMovement).where(
        VatMovement.source_passive_invoice_id == result.passive_invoice.id
    )
    movements = db_session.scalars(query).all()

    assert len(movements) == 1
    movement = movements[0]
    assert movement.movement_type == "CREDIT"
    assert movement.source_type == "PASSIVE_INVOICE"
    assert movement.vat_rate == Decimal("22.00")
    assert movement.taxable_amount == Decimal("300.00")
    assert movement.vat_amount == Decimal("66.00")

    print(f"\n✓ VAT movement created: CREDIT {movement.vat_amount}")


def test_vat_summary_calculation(db_session: Session, test_company: User):
    """Test VAT summary calculation for a period"""
    import_service = PassiveInvoiceImportService(db_session)
    summary_service = VatSummaryService(db_session)
    period_service = VatPeriodService(db_session)

    # Import passive invoice
    result = import_service.import_from_xml(
        company_id=test_company.id,
        xml_content=SAMPLE_FATTURA_PA_XML,
        source_channel="TEST",
    )

    db_session.commit()

    # Get period
    period = period_service.get_current_period(
        company_id=test_company.id,
        target_date=date(2026, 1, 15),
        frequency="QUARTERLY",
    )

    assert period is not None

    # Calculate summary
    summary = summary_service.calculate_period_summary(
        company_id=test_company.id,
        period_id=period.id,
    )

    assert summary["total_debit"] == Decimal("0.00")
    assert summary["total_credit"] == Decimal("66.00")
    assert summary["previous_credit"] == Decimal("0.00")
    assert summary["balance"] == Decimal("-66.00")
    assert summary["amount_to_pay"] == Decimal("0.00")
    assert summary["credit_to_carry"] == Decimal("66.00")

    print(f"\n✓ VAT summary calculated:")
    print(f"  Total debit:     {summary['total_debit']}")
    print(f"  Total credit:    {summary['total_credit']}")
    print(f"  Balance:         {summary['balance']}")
    print(f"  Credit to carry: {summary['credit_to_carry']}")


def test_vat_settlement_creation(db_session: Session, test_company: User):
    """Test VAT settlement creation"""
    import_service = PassiveInvoiceImportService(db_session)
    summary_service = VatSummaryService(db_session)
    period_service = VatPeriodService(db_session)

    # Import passive invoice
    result = import_service.import_from_xml(
        company_id=test_company.id,
        xml_content=SAMPLE_FATTURA_PA_XML,
        source_channel="TEST",
    )

    db_session.commit()

    # Get period
    period = period_service.get_current_period(
        company_id=test_company.id,
        target_date=date(2026, 1, 15),
        frequency="QUARTERLY",
    )

    assert period is not None

    # Create settlement
    settlement = summary_service.close_period_and_create_settlement(
        company_id=test_company.id,
        period_id=period.id,
    )

    assert settlement is not None
    assert settlement.company_id == test_company.id
    assert settlement.period_id == period.id
    assert settlement.total_debit == Decimal("0.00")
    assert settlement.total_credit == Decimal("66.00")
    assert settlement.balance == Decimal("-66.00")
    assert settlement.amount_to_pay == Decimal("0.00")
    assert settlement.credit_to_carry == Decimal("66.00")
    assert settlement.payment_status == "PAID"  # No amount to pay

    db_session.commit()
    print(f"\n✓ VAT settlement created: balance={settlement.balance}")


def test_vat_settlement_payment(db_session: Session, test_company: User):
    """Test VAT settlement payment recording"""
    # This test would create a scenario with debit > credit
    # For now, we skip implementation as it requires creating active invoices
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
