"""
Convertitore da InvoiceCreatePayload a FatturaElettronica XML
"""
from __future__ import annotations

import uuid
from datetime import date

from app.logger import logger

from app.modules.invoices.domain.enums import (
    FormatoTrasmissione,
    SubjectType,
    TipoDocumento,
    CondizioniPagamento,
    RegimeFiscale,
)
from app.modules.invoices.schemas.request import InvoiceCreatePayload, PartyPayload
from app.modules.invoices.services.invoice_calculator import InvoiceCalculator, CalculatedInvoiceTotals
from app.modules.invoices.xml.models import (
    FatturaElettronica,
    FatturaElettronicaHeader,
    FatturaElettronicaBody,
    DatiTrasmissione,
    IdTrasmittente,
    CedentePrestatore,
    CessionarioCommittente,
    DatiAnagraficiCedente,
    DatiAnagraficiCommittente,
    IdFiscaleIVA,
    Anagrafica,
    Sede,
    Contatti,
    DatiGenerali,
    DatiGeneraliDocumento,
    DatiBollo,
    DatiBeniServizi,
    DettaglioLinee,
    DatiRiepilogo,
    DatiPagamento,
    DettaglioPagamento,
)


class FatturaPAConverter:
    """Converte InvoiceCreatePayload in struttura FatturaElettronica XML"""

    def __init__(self):
        self.calculator = InvoiceCalculator()

    def convert(self, invoice: InvoiceCreatePayload) -> FatturaElettronica:
        """
        Converte una fattura dal formato API a FatturaElettronica XML

        Args:
            invoice: Dati fattura in formato API

        Returns:
            FatturaElettronica pronta per la generazione XML
        """
        logger.info(f"Converting invoice from API format to FatturaElettronica XML")
        logger.debug(f"Invoice data: issuer={invoice.issuer.vat_number}, customer={invoice.customer.vat_number}, lines={len(invoice.lines)}")

        # Calcola i totali
        calculated = self.calculator.calculate(invoice)
        logger.debug(f"Calculated totals: total={calculated.total_amount}, vat={calculated.total_vat}")

        # Determina formato trasmissione (semplificato: sempre FPR12 per privati)
        formato = FormatoTrasmissione.FPR12

        # Genera header
        header = self._build_header(invoice, formato)

        # Genera body
        body = self._build_body(invoice, calculated)

        logger.info("Invoice conversion completed successfully")
        return FatturaElettronica(
            versione=formato.value,
            FatturaElettronicaHeader=header,
            FatturaElettronicaBody=[body],
        )

    def _build_header(self, invoice: InvoiceCreatePayload, formato: FormatoTrasmissione) -> FatturaElettronicaHeader:
        """Costruisce l'header della fattura"""

        # Dati trasmissione
        dati_trasmissione = DatiTrasmissione(
            IdTrasmittente=IdTrasmittente(
                IdPaese=invoice.issuer.address.country,
                IdCodice=invoice.issuer.vat_number or invoice.issuer.tax_code or "",
            ),
            ProgressivoInvio=self._generate_progressive_id(invoice),
            FormatoTrasmissione=formato,
            CodiceDestinatario=invoice.customer.recipient_code or "0000000",
            PECDestinatario=invoice.customer.pec if invoice.customer.pec else None,
        )

        # Cedente/Prestatore
        cedente = self._build_cedente(invoice.issuer)

        # Cessionario/Committente
        cessionario = self._build_cessionario(invoice.customer)

        return FatturaElettronicaHeader(
            DatiTrasmissione=dati_trasmissione,
            CedentePrestatore=cedente,
            CessionarioCommittente=cessionario,
        )

    def _build_cedente(self, issuer: PartyPayload) -> CedentePrestatore:
        """Costruisce i dati del cedente/prestatore"""

        # IdFiscaleIVA obbligatorio per cedente
        id_fiscale_iva = IdFiscaleIVA(
            IdPaese=issuer.address.country,
            IdCodice=issuer.vat_number or "",
        )

        # Anagrafica
        anagrafica = Anagrafica(
            Denominazione=issuer.company_name if issuer.subject_type == SubjectType.COMPANY else None,
            Nome=issuer.first_name if issuer.subject_type == SubjectType.INDIVIDUAL else None,
            Cognome=issuer.last_name if issuer.subject_type == SubjectType.INDIVIDUAL else None,
        )

        # Dati anagrafici
        # RegimeFiscale è obbligatorio, usa RF01 (ordinario) come default se non specificato
        regime_fiscale = issuer.fiscal_regime if issuer.fiscal_regime else RegimeFiscale.RF01

        dati_anagrafici = DatiAnagraficiCedente(
            IdFiscaleIVA=id_fiscale_iva,
            CodiceFiscale=issuer.tax_code if issuer.tax_code != issuer.vat_number else None,
            Anagrafica=anagrafica,
            RegimeFiscale=regime_fiscale,
        )

        # Sede
        sede = Sede(
            Indirizzo=issuer.address.street,
            NumeroCivico=issuer.address.street_number,
            CAP=issuer.address.zip_code,
            Comune=issuer.address.city,
            Provincia=issuer.address.province,
            Nazione=issuer.address.country,
        )

        # Contatti (opzionale)
        contatti = None
        if issuer.contacts:
            contatti = Contatti(
                Telefono=issuer.contacts.phone,
                Email=issuer.contacts.email,
            )

        return CedentePrestatore(
            DatiAnagrafici=dati_anagrafici,
            Sede=sede,
            Contatti=contatti,
        )

    def _build_cessionario(self, customer: PartyPayload) -> CessionarioCommittente:
        """Costruisce i dati del cessionario/committente"""

        # IdFiscaleIVA (opzionale per il cessionario)
        id_fiscale_iva = None
        if customer.vat_number:
            id_fiscale_iva = IdFiscaleIVA(
                IdPaese=customer.address.country,
                IdCodice=customer.vat_number,
            )

        # Anagrafica
        anagrafica = Anagrafica(
            Denominazione=customer.company_name if customer.subject_type == SubjectType.COMPANY else None,
            Nome=customer.first_name if customer.subject_type == SubjectType.INDIVIDUAL else None,
            Cognome=customer.last_name if customer.subject_type == SubjectType.INDIVIDUAL else None,
        )

        # Dati anagrafici
        dati_anagrafici = DatiAnagraficiCommittente(
            IdFiscaleIVA=id_fiscale_iva,
            CodiceFiscale=customer.tax_code,
            Anagrafica=anagrafica,
        )

        # Sede
        sede = Sede(
            Indirizzo=customer.address.street,
            NumeroCivico=customer.address.street_number,
            CAP=customer.address.zip_code,
            Comune=customer.address.city,
            Provincia=customer.address.province,
            Nazione=customer.address.country,
        )

        return CessionarioCommittente(
            DatiAnagrafici=dati_anagrafici,
            Sede=sede,
        )

    def _build_body(self, invoice: InvoiceCreatePayload, calculated: CalculatedInvoiceTotals) -> FatturaElettronicaBody:
        """Costruisce il body della fattura"""

        # Dati generali
        dati_generali = self._build_dati_generali(invoice, calculated)

        # Dati beni/servizi
        dati_beni_servizi = self._build_dati_beni_servizi(invoice, calculated)

        # Dati pagamento
        dati_pagamento = self._build_dati_pagamento(invoice, calculated)

        return FatturaElettronicaBody(
            DatiGenerali=dati_generali,
            DatiBeniServizi=dati_beni_servizi,
            DatiPagamento=[dati_pagamento] if dati_pagamento else [],
        )

    def _build_dati_generali(self, invoice: InvoiceCreatePayload, calculated: CalculatedInvoiceTotals) -> DatiGenerali:
        """Costruisce i dati generali del documento"""

        # Bollo (se presente)
        dati_bollo = None
        if invoice.stamp_duty.enabled and invoice.stamp_duty.amount > 0:
            dati_bollo = DatiBollo(
                BolloVirtuale="SI",
                ImportoBollo=invoice.stamp_duty.amount,
            )

        # Dati generali documento
        dati_generali_doc = DatiGeneraliDocumento(
            TipoDocumento=TipoDocumento(invoice.document_type.value),
            Divisa=invoice.currency,
            Data=invoice.invoice_date.strftime("%Y-%m-%d"),
            Numero=invoice.invoice_number,
            DatiBollo=dati_bollo,
            ImportoTotaleDocumento=calculated.grand_total,
            Causale=invoice.causal if invoice.causal else [],
        )

        return DatiGenerali(
            DatiGeneraliDocumento=dati_generali_doc,
        )

    def _build_dati_beni_servizi(
        self, invoice: InvoiceCreatePayload, calculated: CalculatedInvoiceTotals
    ) -> DatiBeniServizi:
        """Costruisce i dati dei beni e servizi"""

        # Dettaglio linee
        dettaglio_linee = []
        for calc_line in calculated.lines:
            # Trova la linea originale per recuperare SKU e unità di misura
            original_line = next(item for item in invoice.items if item.line_number == calc_line.line_number)

            # Crea codice articolo se presente SKU
            codice_articolo = []
            if original_line.sku:
                from app.modules.invoices.xml.models import CodiceArticolo

                codice_articolo = [
                    CodiceArticolo(
                        CodiceTipo="SKU",
                        CodiceValore=original_line.sku,
                    )
                ]

            # Sconto/maggiorazione (se presente)
            sconto_maggiorazione = []
            if original_line.discount_percent > 0:
                from app.modules.invoices.xml.models import ScontoMaggiorazioneDettaglio
                from app.modules.invoices.domain.enums import ScontoMaggiorazione

                sconto_maggiorazione = [
                    ScontoMaggiorazioneDettaglio(
                        Tipo=ScontoMaggiorazione.SC,
                        Percentuale=original_line.discount_percent,
                    )
                ]

            dettaglio = DettaglioLinee(
                NumeroLinea=calc_line.line_number,
                Descrizione=calc_line.description,
                Quantita=calc_line.quantity,
                UnitaMisura=original_line.unit_of_measure,
                PrezzoUnitario=calc_line.unit_price,
                ScontoMaggiorazione=sconto_maggiorazione,
                PrezzoTotale=calc_line.taxable_amount,
                AliquotaIVA=calc_line.vat_rate,
                Natura=calc_line.nature,
                CodiceArticolo=codice_articolo,
            )

            dettaglio_linee.append(dettaglio)

        # Dati riepilogo IVA
        dati_riepilogo = []
        for summary in calculated.vat_summaries:
            riepilogo = DatiRiepilogo(
                AliquotaIVA=summary.vat_rate,
                Natura=summary.nature,
                ImponibileImporto=summary.taxable_amount,
                Imposta=summary.tax_amount,
            )
            dati_riepilogo.append(riepilogo)

        return DatiBeniServizi(
            DettaglioLinee=dettaglio_linee,
            DatiRiepilogo=dati_riepilogo,
        )

    def _build_dati_pagamento(
        self, invoice: InvoiceCreatePayload, calculated: CalculatedInvoiceTotals
    ) -> DatiPagamento | None:
        """Costruisce i dati di pagamento"""

        # Dettaglio pagamento
        dettaglio = DettaglioPagamento(
            Beneficiario=invoice.payment.beneficiary,
            ModalitaPagamento=invoice.payment.payment_method,
            DataScadenzaPagamento=invoice.payment.due_date.strftime("%Y-%m-%d") if invoice.payment.due_date else None,
            ImportoPagamento=calculated.grand_total,
            IBAN=invoice.payment.iban,
        )

        return DatiPagamento(
            CondizioniPagamento=invoice.payment.payment_terms,
            DettaglioPagamento=[dettaglio],
        )

    @staticmethod
    def _generate_progressive_id(invoice: InvoiceCreatePayload) -> str:
        """
        Genera un ID progressivo univoco per la trasmissione
        In produzione, questo dovrebbe essere gestito da un sistema di numerazione sequenziale
        """
        # Usa una combinazione di data e numero fattura
        date_part = invoice.invoice_date.strftime("%Y%m%d")
        # Prendi solo caratteri alfanumerici dal numero fattura
        invoice_part = "".join(c for c in invoice.invoice_number if c.isalnum())[:5]
        # Aggiungi un UUID corto per univocità
        unique_part = str(uuid.uuid4())[:4].upper()

        progressive = f"{date_part}{invoice_part}{unique_part}"

        # Tronca a 10 caratteri massimi come richiesto dallo schema
        return progressive[:10]
