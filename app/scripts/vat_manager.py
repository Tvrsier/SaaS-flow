"""
VAT Manager Script - Gestione IVA e Fatture Passive

Due modalità:
1. update-summary: Aggiorna il VAT summary creando i movimenti IVA dalle fatture attive esistenti
2. import-passive: Importa una fattura passiva da file XML

Esempi d'uso:
    # Aggiorna il summary IVA per un utente
    python -m app.scripts.vat_manager update-summary --user-id d79f01f3-3f48-47c0-85a8-e584f76e794b --frequency QUARTERLY --year 2026 --period 2

    # Importa una fattura passiva
    python -m app.scripts.vat_manager import-passive --user-id d79f01f3-3f48-47c0-85a8-e584f76e794b --xml-file resources/invoices/test/fattura_passiva_test.xml
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.invoice import Invoice, VatPeriod
from app.db.models.user import User
from app.db.session import SessionLocal
from app.modules.passive_invoices.services.passive_invoice_import_service import PassiveInvoiceImportService
from app.modules.vat.services.vat_movement_service import VatMovementService
from app.modules.vat.services.vat_period_service import VatPeriodService
from app.modules.vat.services.vat_summary_service import VatSummaryService
from app.scripts.vat_summary_console import print_vat_summary


def update_vat_summary(
    db: Session,
    user_id: UUID,
    frequency: str,
    year: int | None = None,
    period_index: int | None = None,
):
    """
    Aggiorna il VAT summary dell'utente creando movimenti IVA dalle fatture attive.

    Args:
        db: Database session
        user_id: ID dell'utente
        frequency: Frequenza periodo IVA (MONTHLY o QUARTERLY)
        year: Anno (opzionale, default anno corrente)
        period_index: Indice periodo (opzionale, default periodo corrente)
    """
    print("\n" + "=" * 80)
    print("AGGIORNAMENTO VAT SUMMARY")
    print("=" * 80)
    print()

    # Verifica utente
    user = db.get(User, user_id)
    if not user:
        print(f"✗ Errore: Utente {user_id} non trovato")
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
    today = date.today()

    if year and period_index:
        # Calcola start_date del periodo richiesto
        if frequency == "QUARTERLY":
            start_month = (period_index - 1) * 3 + 1
            target_date = date(year, start_month, 1)
        else:  # MONTHLY
            target_date = date(year, period_index, 1)
    else:
        target_date = today
        year = today.year
        if frequency == "QUARTERLY":
            period_index = ((today.month - 1) // 3) + 1
        else:
            period_index = today.month

    period = period_service.get_or_create_period(
        company_id=user_id,
        vat_competence_date=target_date,
        frequency=frequency,
    )

    period_label = f"{period.year}-Q{period.period_index}" if frequency == "QUARTERLY" else f"{period.year}-M{period.period_index:02d}"
    print(f"Periodo: {period_label} ({period.start_date} → {period.end_date})")
    print(f"Status: {period.status}")
    print()

    # Trova tutte le fatture attive dell'utente nel periodo
    query = select(Invoice).where(
        Invoice.company_id == user_id,
        Invoice.status.in_(["READY", "ISSUED", "SENT"]),
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
        # Verifica se esistono già movimenti per questa fattura
        existing_query = select(VatMovementService).where(
            VatMovementService.company_id == user_id,
            VatMovementService.source_type == "ACTIVE_INVOICE",
            VatMovementService.source_id == inv.id,
        )

        # Crea movimento IVA DEBIT per fattura attiva
        try:
            movements = movement_service.create_from_active_invoice(inv)
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
    print_vat_summary(db, user_id, period.id)


def import_passive_invoice(db: Session, user_id: UUID, xml_file_path: str):
    """
    Importa una fattura passiva da file XML.

    Args:
        db: Database session
        user_id: ID dell'utente
        xml_file_path: Percorso del file XML
    """
    print("\n" + "=" * 80)
    print("IMPORTAZIONE FATTURA PASSIVA")
    print("=" * 80)
    print()

    # Verifica utente
    user = db.get(User, user_id)
    if not user:
        print(f"✗ Errore: Utente {user_id} non trovato")
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
                company_id=user_id,
                target_date=result.passive_invoice.vat_competence_date,
                frequency="QUARTERLY",  # Default
            )

            if period:
                print_vat_summary(db, user_id, period.id)

    except Exception as e:
        print(f"✗ Errore durante l'importazione: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="VAT Manager - Gestione IVA e Fatture Passive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Aggiorna il summary IVA per Q2 2026
  python -m app.scripts.vat_manager update-summary --user-id d79f01f3-3f48-47c0-85a8-e584f76e794b --frequency QUARTERLY --year 2026 --period 2

  # Aggiorna il summary IVA per il periodo corrente
  python -m app.scripts.vat_manager update-summary --user-id d79f01f3-3f48-47c0-85a8-e584f76e794b --frequency QUARTERLY

  # Importa una fattura passiva
  python -m app.scripts.vat_manager import-passive --user-id d79f01f3-3f48-47c0-85a8-e584f76e794b --xml-file resources/invoices/test/fattura_passiva_test.xml
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando da eseguire")

    # Subcommand: update-summary
    update_parser = subparsers.add_parser(
        "update-summary",
        help="Aggiorna il VAT summary dalle fatture attive",
    )
    update_parser.add_argument(
        "--user-id",
        required=True,
        help="UUID dell'utente",
    )
    update_parser.add_argument(
        "--frequency",
        choices=["MONTHLY", "QUARTERLY"],
        default="QUARTERLY",
        help="Frequenza periodo IVA (default: QUARTERLY)",
    )
    update_parser.add_argument(
        "--year",
        type=int,
        help="Anno (opzionale, default anno corrente)",
    )
    update_parser.add_argument(
        "--period",
        type=int,
        help="Indice periodo (1-4 per QUARTERLY, 1-12 per MONTHLY, opzionale)",
    )

    # Subcommand: import-passive
    import_parser = subparsers.add_parser(
        "import-passive",
        help="Importa una fattura passiva da file XML",
    )
    import_parser.add_argument(
        "--user-id",
        required=True,
        help="UUID dell'utente",
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

    user_id = UUID(args.user_id)
    db = SessionLocal()

    try:
        if args.command == "update-summary":
            update_vat_summary(
                db=db,
                user_id=user_id,
                frequency=args.frequency,
                year=args.year,
                period_index=args.period,
            )
        elif args.command == "import-passive":
            import_passive_invoice(
                db=db,
                user_id=user_id,
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
