from __future__ import annotations

from lxml import etree

from app.modules.invoices.documents.dto import InvoiceDocumentDTO, PartyDTO
from app.modules.invoices.documents.exceptions import InvoiceDocumentGenerationError

NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"


def _element(parent, name: str, value: object | None = None):
    child = etree.SubElement(parent, name)
    if value is not None:
        child.text = str(value)
    return child


def _party(parent, party: PartyDTO, *, seller: bool) -> None:
    dati = _element(parent, "DatiAnagrafici")
    if party.vat_number:
        iva = _element(dati, "IdFiscaleIVA")
        _element(iva, "IdPaese", party.address.country)
        _element(iva, "IdCodice", party.vat_number)
    if party.tax_code:
        _element(dati, "CodiceFiscale", party.tax_code)
    anagrafica = _element(dati, "Anagrafica")
    if party.first_name and party.last_name:
        _element(anagrafica, "Nome", party.first_name)
        _element(anagrafica, "Cognome", party.last_name)
    else:
        _element(anagrafica, "Denominazione", party.name)
    if seller:
        _element(dati, "RegimeFiscale", "RF01")
    sede = _element(parent, "Sede")
    _element(sede, "Indirizzo", party.address.street or "N/D")
    if party.address.street_number:
        _element(sede, "NumeroCivico", party.address.street_number)
    _element(sede, "CAP", party.address.postal_code or "00000")
    _element(sede, "Comune", party.address.city or "N/D")
    if party.address.province:
        _element(sede, "Provincia", party.address.province)
    _element(sede, "Nazione", party.address.country)


def build_invoice_xml(invoice: InvoiceDocumentDTO) -> bytes:
    try:
        root = etree.Element(
            f"{{{NS}}}FatturaElettronica",
            nsmap={"p": NS},
            versione="FPR12",
        )
        header = _element(root, "FatturaElettronicaHeader")
        transmission = _element(header, "DatiTrasmissione")
        sender = _element(transmission, "IdTrasmittente")
        _element(sender, "IdPaese", invoice.seller.address.country)
        _element(sender, "IdCodice", invoice.seller.vat_number or invoice.seller.tax_code or "00000000000")
        _element(transmission, "ProgressivoInvio", str(invoice.invoice_id).replace("-", "")[:10])
        _element(transmission, "FormatoTrasmissione", "FPR12")
        _element(transmission, "CodiceDestinatario", invoice.customer.recipient_code or "0000000")
        if invoice.customer.pec:
            _element(transmission, "PECDestinatario", invoice.customer.pec)
        seller = _element(header, "CedentePrestatore")
        _party(seller, invoice.seller, seller=True)
        customer = _element(header, "CessionarioCommittente")
        _party(customer, invoice.customer, seller=False)

        body = _element(root, "FatturaElettronicaBody")
        general = _element(body, "DatiGenerali")
        document = _element(general, "DatiGeneraliDocumento")
        _element(document, "TipoDocumento", invoice.document_type)
        _element(document, "Divisa", invoice.currency)
        _element(document, "Data", invoice.issue_date.isoformat())
        _element(document, "Numero", invoice.invoice_number)
        _element(document, "ImportoTotaleDocumento", f"{invoice.total_amount:.2f}")
        allowed_related_blocks = {
            "DatiOrdineAcquisto", "DatiContratto", "DatiConvenzione",
            "DatiRicezione", "DatiFattureCollegate",
        }
        for related in invoice.related_documents:
            if related.document_type not in allowed_related_blocks:
                continue
            node = _element(general, related.document_type)
            for line_number in related.line_numbers:
                _element(node, "RiferimentoNumeroLinea", line_number)
            _element(node, "IdDocumento", related.document_number)
            if related.document_date:
                _element(node, "Data", related.document_date.isoformat())
            metadata = dict(related.metadata)
            field_map = {
                "numItem": "NumItem",
                "codiceCommessaConvenzione": "CodiceCommessaConvenzione",
                "codiceCUP": "CodiceCUP",
                "codiceCIG": "CodiceCIG",
            }
            for source, target in field_map.items():
                if metadata.get(source) is not None:
                    _element(node, target, metadata[source])
        for ddt in invoice.ddt:
            node = _element(general, "DatiDDT")
            for line_number in ddt.get("riferimento_linee", []) or []:
                _element(node, "RiferimentoNumeroLinea", line_number)
            _element(node, "NumeroDDT", ddt.get("numero"))
            _element(node, "DataDDT", ddt.get("data"))

        goods = _element(body, "DatiBeniServizi")
        for line in invoice.lines:
            node = _element(goods, "DettaglioLinee")
            _element(node, "NumeroLinea", line.number)
            _element(node, "Descrizione", line.description)
            _element(node, "Quantita", f"{line.quantity:.2f}")
            if line.unit_of_measure:
                _element(node, "UnitaMisura", line.unit_of_measure)
            _element(node, "PrezzoUnitario", f"{line.unit_price:.2f}")
            _element(node, "PrezzoTotale", f"{line.taxable_amount:.2f}")
            _element(node, "AliquotaIVA", f"{line.vat_rate:.2f}")
            if line.vat_nature:
                _element(node, "Natura", line.vat_nature)
        for summary in invoice.vat_summaries:
            node = _element(goods, "DatiRiepilogo")
            _element(node, "AliquotaIVA", f"{summary.vat_rate:.2f}")
            if summary.vat_nature:
                _element(node, "Natura", summary.vat_nature)
            _element(node, "ImponibileImporto", f"{summary.taxable_amount:.2f}")
            _element(node, "Imposta", f"{summary.vat_amount:.2f}")
            _element(node, "EsigibilitaIVA", invoice.vat_collectability)

        if invoice.payment_details:
            payment = _element(body, "DatiPagamento")
            _element(payment, "CondizioniPagamento", "TP02")
            detail = _element(payment, "DettaglioPagamento")
            _element(detail, "ModalitaPagamento", invoice.payment_details.method)
            _element(detail, "DataScadenzaPagamento", invoice.payment_details.due_date.isoformat())
            _element(detail, "ImportoPagamento", f"{invoice.payment_details.amount:.2f}")
            if invoice.payment_details.iban:
                _element(detail, "IBAN", invoice.payment_details.iban)
            if invoice.payment_details.bic:
                _element(detail, "BIC", invoice.payment_details.bic)

        return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    except Exception as exc:
        raise InvoiceDocumentGenerationError("XML generation failed") from exc
