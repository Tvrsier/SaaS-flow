"""
Test script for VAT flow with console output
This script demonstrates the full VAT flow:
1. Import a passive invoice
2. Create VAT period
3. Calculate VAT summary
4. Print console output
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.settings import get_settings
from app.db.models.user import AccountType, User
from app.db.session import SessionLocal
from app.modules.passive_invoices.services.passive_invoice_import_service import PassiveInvoiceImportService
from app.modules.vat.services.vat_period_service import VatPeriodService
from app.modules.vat.services.vat_summary_service import VatSummaryService
from app.scripts.vat_summary_console import print_vat_summary


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
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
                    <Denominazione>Test Company SRL</Denominazione>
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


def create_test_company(db):
    """Create or get test company"""
    from sqlalchemy import select

    # Try to find existing test company
    query = select(User).where(User.email == "testcompany@example.com")
    company = db.scalar(query)

    if company:
        print(f"Using existing test company: {company.id}")
        return company

    # Create new test company
    from datetime import datetime, timezone

    company = User(
        email="testcompany@example.com",
        account_type=AccountType.azienda,
        partita_iva="98765432109",
        codice_fiscale="98765432109",
        company_name="Test Company SRL",
        phone="+39 02 12345678",
        is_active=True,
        is_verified=True,
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    print(f"Created test company: {company.id}")
    return company


def main():
    """Main function"""
    db = SessionLocal()

    try:
        print("\n" + "=" * 80)
        print("VAT FLOW TEST")
        print("=" * 80)
        print()

        # Create test company
        print("Step 1: Creating/getting test company...")
        company = create_test_company(db)
        print(f"✓ Company: {company.company_name} ({company.id})")
        print()

        # Import passive invoice
        print("Step 2: Importing passive invoice from XML...")
        import_service = PassiveInvoiceImportService(db)
        result = import_service.import_from_xml(
            company_id=company.id,
            xml_content=SAMPLE_XML,
            source_channel="TEST_SCRIPT",
        )

        db.commit()

        if result.created:
            print(f"✓ Passive invoice imported: {result.passive_invoice.invoice_number}")
        else:
            print(f"✓ Passive invoice already exists: {result.passive_invoice.invoice_number}")

        print(f"  - Lines: {result.lines_count}")
        print(f"  - VAT summaries: {result.vat_summaries_count}")
        print(f"  - VAT movements: {result.vat_movements_count}")
        print()

        # Get period
        print("Step 3: Getting VAT period...")
        period_service = VatPeriodService(db)
        period = period_service.get_current_period(
            company_id=company.id,
            target_date=date(2026, 1, 15),
            frequency="QUARTERLY",
        )

        if not period:
            print("✗ Period not found (this should not happen)")
            return

        print(f"✓ Period: {period.year}-Q{period.period_index} (status: {period.status})")
        print()

        # Print VAT summary
        print("Step 4: Printing VAT summary...")
        print_vat_summary(db, company.id, period.id)

        # Optionally create settlement
        print("\n" + "=" * 80)
        print("Step 5: Creating settlement...")
        summary_service = VatSummaryService(db)

        try:
            settlement = summary_service.close_period_and_create_settlement(
                company_id=company.id,
                period_id=period.id,
            )
            db.commit()
            print(f"✓ Settlement created: {settlement.id}")
            print()

            # Print again with settlement
            print("Step 6: Printing VAT summary with settlement...")
            print_vat_summary(db, company.id, period.id)

        except ValueError as e:
            print(f"✗ Settlement already exists or error: {e}")
            print()

        print("\n" + "=" * 80)
        print("TEST COMPLETED")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    main()
