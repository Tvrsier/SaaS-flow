"""
VAT Summary Console Script - Gestione IVA e Fatture Passive

Tre modalità:
1. show: Visualizza il VAT summary di un periodo specifico
2. update-summary: Aggiorna il VAT summary creando i movimenti IVA dalle fatture attive esistenti
3. import-passive: Importa una fattura passiva da file XML

Esempi d'uso:
    # Visualizza il summary di un periodo
    python -m app.scripts.vat_summary_console show --company-id <uuid> --period-id <uuid>

    # Aggiorna il summary IVA per un utente
    python -m app.scripts.vat_summary_console update-summary --user-id d79f01f3-3f48-47c0-85a8-e584f76e794b --frequency QUARTERLY --year 2026 --period 2

    # Importa una fattura passiva
    python -m app.scripts.vat_summary_console import-passive --user-id d79f01f3-3f48-47c0-85a8-e584f76e794b --xml-file resources/invoices/test/fattura_passiva_test.xml
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.invoice import Invoice, VatMovement, VatPeriod, VatSettlement
from app.db.models.user import User
from app.db.session import SessionLocal
from app.modules.passive_invoices.services.passive_invoice_import_service import PassiveInvoiceImportService
from app.modules.vat.services.vat_movement_service import VatMovementService
from app.modules.vat.services.vat_period_service import VatPeriodService
from app.modules.vat.services.vat_summary_service import VatSummaryService


def format_decimal(value: Decimal) -> str:
    """Format decimal for console output"""
    return f"{value:>12.2f}"


def format_date(dt: date | datetime) -> str:
    """Format date for console output"""
    if isinstance(dt, datetime):
        dt = dt.date()
    return dt.strftime("%Y-%m-%d")


def print_vat_summary(db: Session, company_id: UUID, period_id: UUID):
    """Print VAT summary for a period"""
    # Get period
    period = db.get(VatPeriod, period_id)
    if not period or period.company_id != company_id:
        print(f"Error: Period {period_id} not found for company {company_id}")
        return

    # Get movements
    query = select(VatMovement).where(
        VatMovement.company_id == company_id,
        VatMovement.period_id == period_id,
    ).order_by(VatMovement.document_date, VatMovement.created_at)
    movements = db.scalars(query).all()

    # Calculate summary
    summary_service = VatSummaryService(db)
    summary = summary_service.calculate_period_summary(company_id, period_id)

    # Get settlement if exists
    settlement_query = select(VatSettlement).where(VatSettlement.period_id == period_id)
    settlement = db.scalar(settlement_query)

    # Print header
    period_label = f"{period.year}-Q{period.period_index}" if period.frequency == "QUARTERLY" else f"{period.year}-M{period.period_index:02d}"
    print("\n" + "=" * 80)
    print(f"VAT SUMMARY {period_label}")
    print("=" * 80)
    print(f"Company:          {company_id}")
    print(f"Period:           {period_label} ({format_date(period.start_date)} -> {format_date(period.end_date)})")
    print(f"Status:           {period.status}")
    print()

    # Print movements
    if movements:
        print("Movements:")
        print("-" * 80)
        for mov in movements:
            movement_type = mov.movement_type.ljust(6)
            if mov.source_type == "ACTIVE_INVOICE":
                source_label = "active invoice"
            elif mov.source_type == "PASSIVE_INVOICE":
                source_label = "passive invoice"
            else:
                source_label = mov.source_type

            taxable_str = format_decimal(mov.taxable_amount)
            vat_str = format_decimal(mov.vat_amount)
            rate_str = f"{mov.vat_rate}%".rjust(6)

            print(f"- {movement_type} | {source_label:30} | rate {rate_str} | taxable {taxable_str} | VAT {vat_str}")

        print()
    else:
        print("No movements found.")
        print()

    # Print totals
    print("Totals:")
    print("-" * 80)
    print(f"Total debit:      {format_decimal(summary['total_debit'])}")
    print(f"Total credit:     {format_decimal(summary['total_credit'])}")
    print(f"Previous credit:  {format_decimal(summary['previous_credit'])}")
    print(f"Balance:          {format_decimal(summary['balance'])}")
    print(f"Amount to pay:    {format_decimal(summary['amount_to_pay'])}")
    print(f"Credit to carry:  {format_decimal(summary['credit_to_carry'])}")
    print()

    # Print settlement info
    if settlement:
        print("=" * 80)
        print("VAT SETTLEMENT")
        print("=" * 80)
        print(f"Balance:          {format_decimal(settlement.balance)}")
        print(f"Amount to pay:    {format_decimal(settlement.amount_to_pay)}")
        print(f"Amount paid:      {format_decimal(settlement.amount_paid)}")
        print(f"Payment status:   {settlement.payment_status}")
        if settlement.payment_date:
            print(f"Payment date:     {format_date(settlement.payment_date)}")
        if settlement.payment_reference:
            print(f"Payment ref:      {settlement.payment_reference}")
        print()

    print("=" * 80)


def find_user_by_tax_id(db: Session, tax_id: str) -> User | None:
    """
    Cerca un utente per Partita IVA o Codice Fiscale.

    Args:
        db: Database session
        tax_id: Partita IVA o Codice Fiscale

    Returns:
        User o None se non trovato
    """
    query = select(User).where(
        (User.partita_iva == tax_id) | (User.codice_fiscale == tax_id)
    )
    return db.scalar(query)


def update_vat_summary(
    db: Session,
    tax_id: str,
    frequency: str,
    period_start_date: date | None = None,
):
    """
    Aggiorna il VAT summary dell'utente creando movimenti IVA dalle fatture attive.

    Args:
        db: Database session
        tax_id: Partita IVA o Codice Fiscale dell'utente
        frequency: Frequenza periodo IVA (MONTHLY o QUARTERLY)
        period_start_date: Data inizio periodo (opzionale, default periodo corrente)
    """
    print("\n" + "=" * 80)
    print("AGGIORNAMENTO VAT SUMMARY")
    print("=" * 80)
    print()

    # Cerca utente per P.IVA o CF
    user = find_user_by_tax_id(db, tax_id)
    if not user:
        print(f"✗ Errore: Utente non trovato con P.IVA/CF: {tax_id}")
        return

    print(f"Utente: {user.email}")
    if user.company_name:
        print(f"Azienda: {user.company_name}")
    print(f"CF: {user.codice_fiscale}")
    if user.partita_iva:
        print(f"P.IVA: {user.partita_iva}")
    print()

    # Determina periodo
    period_service = VatPeriodService(db)

    if period_start_date:
        target_date = period_start_date
    else:
        target_date = date.today()

    period = period_service.get_or_create_period(
        company_id=user.id,
        competence_date=target_date,
        frequency=frequency,
    )

    period_label = f"{period.year}-Q{period.period_index}" if frequency == "QUARTERLY" else f"{period.year}-M{period.period_index:02d}"
    print(f"Periodo: {period_label} ({period.start_date} → {period.end_date})")
    print(f"Status: {period.status}")
    print()

    # Trova tutte le fatture attive dell'utente nel periodo
    query = select(Invoice).where(
        Invoice.company_id == user_id,
        Invoice.status.in_(["READY", "ISSUED"]),
        Invoice.issue_date >= period.start_date,
        Invoice.issue_date <= period.end_date,
    ).order_by(Invoice.issue_date, Invoice.invoice_number)

    invoices = db.scalars(query).all()

    if not invoices:
        print(f"✗ Nessuna fattura attiva trovata nel periodo {period_label}")
        print()
        return

    print(f"Trovate {len(invoices)} fatture attive nel periodo:")
    print("-" * 80)

    movement_service = VatMovementService(db)
    created_count = 0
    skipped_count = 0

    for inv in invoices:
        # Crea movimento IVA DEBIT per fattura attiva
        try:
            movements = movement_service.create_from_active_invoice(inv.id)
            if movements:
                created_count += len(movements)
                print(f"✓ {inv.invoice_number} - {inv.issue_date} - Imponibile: €{inv.taxable_amount:.2f}, IVA: €{inv.vat_amount:.2f} - {len(movements)} movimenti creati")
            else:
                skipped_count += 1
                print(f"○ {inv.invoice_number} - {inv.issue_date} - Già processata")
        except Exception as e:
            skipped_count += 1
            print(f"✗ {inv.invoice_number} - Errore: {e}")

    print()
    print(f"Riepilogo: {created_count} movimenti creati, {skipped_count} fatture già processate/errori")
    print()

    if created_count > 0:
        db.commit()
        print("✓ Movimenti IVA salvati nel database")
        print()

    # Stampa il summary aggiornato
    print_vat_summary(db, user.id, period.id)


def import_passive_invoice(db: Session, tax_id: str, xml_file_path: str):
    """
    Importa una fattura passiva da file XML.

    Args:
        db: Database session
        tax_id: Partita IVA o Codice Fiscale dell'utente
        xml_file_path: Percorso del file XML
    """
    print("\n" + "=" * 80)
    print("IMPORTAZIONE FATTURA PASSIVA")
    print("=" * 80)
    print()

    # Cerca utente per P.IVA o CF
    user = find_user_by_tax_id(db, tax_id)
    if not user:
        print(f"✗ Errore: Utente non trovato con P.IVA/CF: {tax_id}")
        return

    print(f"Utente: {user.email}")
    if user.company_name:
        print(f"Azienda: {user.company_name}")
    print(f"CF: {user.codice_fiscale}")
    if user.partita_iva:
        print(f"P.IVA: {user.partita_iva}")
    print()

    # Leggi file XML
    xml_path = Path(xml_file_path)
    if not xml_path.exists():
        print(f"✗ Errore: File {xml_file_path} non trovato")
        return

    print(f"File XML: {xml_file_path}")

    try:
        xml_content = xml_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"✗ Errore nella lettura del file: {e}")
        return

    print(f"Dimensione: {len(xml_content)} bytes")
    print()

    # Importa fattura passiva
    import_service = PassiveInvoiceImportService(db)

    try:
        print("Importazione in corso...")
        result = import_service.import_from_xml(
            company_id=user_id,
            xml_content=xml_content,
            source_channel="MANUAL_IMPORT",
        )

        db.commit()

        print()
        if result.created:
            print("✓ Fattura passiva importata con successo!")
        else:
            print("○ Fattura passiva già esistente nel sistema (import idempotente)")

        print()
        print("Dettagli fattura:")
        print("-" * 80)
        print(f"Numero:              {result.passive_invoice.invoice_number}")
        print(f"Data:                {result.passive_invoice.invoice_date}")
        print(f"Fornitore:           {result.passive_invoice.supplier_name}")
        print(f"Tipo documento:      {result.passive_invoice.document_type}")
        print(f"Imponibile:          €{result.passive_invoice.taxable_amount:.2f}")
        print(f"IVA:                 €{result.passive_invoice.vat_amount:.2f}")
        print(f"Totale:              €{result.passive_invoice.total_amount:.2f}")
        print()
        print(f"Righe importate:     {result.lines_count}")
        print(f"Riepiloghi IVA:      {result.vat_summaries_count}")
        print(f"Movimenti IVA:       {result.vat_movements_count}")
        print()

        # Trova e stampa il periodo IVA
        if result.vat_movements_count > 0:
            period_service = VatPeriodService(db)
            period = period_service.get_current_period(
                company_id=user.id,
                target_date=result.passive_invoice.vat_competence_date,
                frequency="QUARTERLY",  # Default
            )

            if period:
                print_vat_summary(db, user.id, period.id)

    except Exception as e:
        print(f"✗ Errore durante l'importazione: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="VAT Summary Console - Gestione IVA e Fatture Passive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Visualizza il summary di un periodo specifico
  python -m app.scripts.vat_summary_console show --company-id <uuid> --period-id <uuid>

  # Aggiorna il summary IVA per il periodo corrente
  python -m app.scripts.vat_summary_console update-summary --tax-id DMTGCM00R01F839J --frequency QUARTERLY

  # Aggiorna il summary IVA per un periodo specifico (es. Q2 2026)
  python -m app.scripts.vat_summary_console update-summary --tax-id DMTGCM00R01F839J --frequency QUARTERLY --period-start 2026-04-01

  # Importa una fattura passiva
  python -m app.scripts.vat_summary_console import-passive --tax-id DMTGCM00R01F839J --xml-file resources/invoices/test/fattura_passiva_test.xml
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando da eseguire")

    # Subcommand: show
    show_parser = subparsers.add_parser(
        "show",
        help="Visualizza il VAT summary di un periodo",
    )
    show_parser.add_argument(
        "--company-id",
        required=True,
        help="UUID dell'azienda/utente",
    )
    show_parser.add_argument(
        "--period-id",
        required=True,
        help="UUID del periodo IVA",
    )

    # Subcommand: update-summary
    update_parser = subparsers.add_parser(
        "update-summary",
        help="Aggiorna il VAT summary dalle fatture attive",
    )
    update_parser.add_argument(
        "--tax-id",
        required=True,
        help="Partita IVA o Codice Fiscale dell'utente",
    )
    update_parser.add_argument(
        "--frequency",
        choices=["MONTHLY", "QUARTERLY"],
        default="QUARTERLY",
        help="Frequenza periodo IVA (default: QUARTERLY)",
    )
    update_parser.add_argument(
        "--period-start",
        type=str,
        help="Data inizio periodo (formato: YYYY-MM-DD, es. 2026-04-01 per Q2 2026). Se non specificato, usa il periodo corrente.",
    )

    # Subcommand: import-passive
    import_parser = subparsers.add_parser(
        "import-passive",
        help="Importa una fattura passiva da file XML",
    )
    import_parser.add_argument(
        "--tax-id",
        required=True,
        help="Partita IVA o Codice Fiscale dell'utente",
    )
    import_parser.add_argument(
        "--xml-file",
        required=True,
        help="Percorso del file XML FatturaPA",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    db = SessionLocal()

    try:
        if args.command == "show":
            company_id = UUID(args.company_id)
            period_id = UUID(args.period_id)
            print_vat_summary(db, company_id, period_id)
        elif args.command == "update-summary":
            period_start_date = None
            if args.period_start:
                try:
                    period_start_date = date.fromisoformat(args.period_start)
                except ValueError:
                    print(f"✗ Errore: Formato data non valido. Usa YYYY-MM-DD (es. 2026-04-01)")
                    return

            update_vat_summary(
                db=db,
                tax_id=args.tax_id,
                frequency=args.frequency,
                period_start_date=period_start_date,
            )
        elif args.command == "import-passive":
            import_passive_invoice(
                db=db,
                tax_id=args.tax_id,
                xml_file_path=args.xml_file,
            )
    except Exception as e:
        print(f"\n✗ Errore: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
