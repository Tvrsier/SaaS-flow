"""
Parser for FatturaPA XML files
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from app.modules.invoices.domain.enums import DocumentType, EsigibilitaIVA, NatureCode

logger = logging.getLogger("GestPro")


@dataclass
class ParsedAddress:
    street: str
    city: str
    postal_code: str
    province: Optional[str] = None
    country: str = "IT"


@dataclass
class ParsedParty:
    vat_number: Optional[str]
    tax_code: Optional[str]
    name: Optional[str]  # Denominazione or Nome + Cognome
    first_name: Optional[str]
    last_name: Optional[str]
    address: Optional[ParsedAddress]


@dataclass
class ParsedInvoiceLine:
    line_number: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    taxable_amount: Decimal
    vat_rate: Decimal
    vat_nature: Optional[NatureCode]
    vat_amount: Decimal
    total_amount: Decimal
    unit_of_measure: Optional[str]
    discount_percentage: Optional[Decimal] = None


@dataclass
class ParsedVatSummary:
    vat_rate: Decimal
    vat_nature: Optional[NatureCode]
    taxable_amount: Decimal
    vat_amount: Decimal
    esigibilita_iva: Optional[EsigibilitaIVA] = None


@dataclass
class ParsedInvoice:
    cedente_prestatore: ParsedParty  # Supplier (who issues the invoice)
    cessionario_committente: ParsedParty  # Customer (who receives the invoice)
    invoice_number: str
    invoice_date: date
    document_type: DocumentType
    currency: str
    taxable_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    lines: list[ParsedInvoiceLine]
    vat_summaries: list[ParsedVatSummary]
    esigibilita_iva: Optional[EsigibilitaIVA] = None


class FatturaPAParser:
    """Parser for FatturaPA XML files"""

    def __init__(self):
        self.namespaces = {
            "p": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2",
            "": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2",
        }

    def parse(self, xml_content: str | bytes) -> ParsedInvoice:
        """
        Parse a FatturaPA XML string or bytes.

        Args:
            xml_content: XML content as string or bytes

        Returns:
            ParsedInvoice instance

        Raises:
            ValueError: If XML is invalid or cannot be parsed
        """
        try:
            if isinstance(xml_content, bytes):
                xml_content = xml_content.decode("utf-8")

            root = ET.fromstring(xml_content)
            ns = self._detect_namespace(root)

            # Parse header
            header = self._find_element(root, f".//{{{ns}}}FatturaElettronicaHeader")
            if header is None:
                raise ValueError("FatturaElettronicaHeader not found")

            cedente = self._parse_cedente_prestatore(header, ns)
            cessionario = self._parse_cessionario_committente(header, ns)

            # Parse body
            body = self._find_element(root, f".//{{{ns}}}FatturaElettronicaBody")
            if body is None:
                raise ValueError("FatturaElettronicaBody not found")

            dati_generali = self._find_element(body, f".//{{{ns}}}DatiGenerali")
            if dati_generali is None:
                raise ValueError("DatiGenerali not found")

            dati_generali_doc = self._find_element(dati_generali, f".//{{{ns}}}DatiGeneraliDocumento")
            if dati_generali_doc is None:
                raise ValueError("DatiGeneraliDocumento not found")

            invoice_number = self._get_text(dati_generali_doc, f"{{{ns}}}Numero", ns)
            if not invoice_number:
                raise ValueError("Invoice number not found")

            invoice_date_str = self._get_text(dati_generali_doc, f"{{{ns}}}Data", ns)
            if not invoice_date_str:
                raise ValueError("Invoice date not found")
            invoice_date = date.fromisoformat(invoice_date_str)

            document_type_str = self._get_text(dati_generali_doc, f"{{{ns}}}TipoDocumento", ns)
            if not document_type_str:
                raise ValueError("Document type not found")
            document_type = DocumentType(document_type_str)

            currency = self._get_text(dati_generali_doc, f"{{{ns}}}Divisa", ns, default="EUR") or "EUR"

            # Parse lines
            dati_beni_servizi = self._find_element(body, f".//{{{ns}}}DatiBeniServizi")
            if dati_beni_servizi is None:
                raise ValueError("DatiBeniServizi not found")

            lines = self._parse_lines(dati_beni_servizi, ns)
            vat_summaries = self._parse_vat_summaries(dati_beni_servizi, ns)

            # Calculate totals
            taxable_amount = Decimal(sum(s.taxable_amount for s in vat_summaries))
            vat_amount = Decimal(sum(s.vat_amount for s in vat_summaries))
            total_amount = Decimal(taxable_amount + vat_amount)

            # Use EsigibilitaIVA from the first VAT summary that has it set
            esigibilita_iva = next(
                (s.esigibilita_iva for s in vat_summaries if s.esigibilita_iva is not None),
                None,
            )

            parsed_invoice = ParsedInvoice(
                cedente_prestatore=cedente,
                cessionario_committente=cessionario,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                document_type=document_type,
                currency=currency,
                taxable_amount=taxable_amount,
                vat_amount=vat_amount,
                total_amount=total_amount,
                lines=lines,
                vat_summaries=vat_summaries,
                esigibilita_iva=esigibilita_iva,
            )

            logger.info(f"Successfully parsed FatturaPA: {invoice_number}, date={invoice_date}")

            return parsed_invoice

        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}")
        except Exception as e:
            logger.error(f"Error parsing FatturaPA XML: {e}")
            raise ValueError(f"Failed to parse FatturaPA: {e}")

    def _detect_namespace(self, root: ET.Element) -> str:
        """Detect namespace from root element"""
        if root.tag.startswith("{"):
            return root.tag[1:root.tag.index("}")]
        return "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    @staticmethod
    def _strip_namespace_from_path(path: str) -> str:
        return re.sub(r"\{[^}]+}", "", path)

    def _find_element(self, parent: ET.Element, path: str) -> ET.Element | None:
        elem = parent.find(path, self.namespaces)
        if elem is not None:
            return elem

        path_without_ns = self._strip_namespace_from_path(path)
        return parent.find(path_without_ns)

    def _findall_elements(self, parent: ET.Element, path: str) -> list[ET.Element]:
        elems = parent.findall(path, self.namespaces)
        if elems:
            return elems

        path_without_ns = self._strip_namespace_from_path(path)
        return parent.findall(path_without_ns)

    def _parse_cedente_prestatore(self, header: ET.Element, ns: str) -> ParsedParty:
        """Parse CedentePrestatore (supplier)"""
        cedente = self._find_element(header, f".//{{{ns}}}CedentePrestatore")
        if cedente is None:
            raise ValueError("CedentePrestatore not found")

        dati_anagrafici = self._find_element(cedente, f".//{{{ns}}}DatiAnagrafici")
        id_fiscale_iva = self._find_element(dati_anagrafici, f".//{{{ns}}}IdFiscaleIVA") if dati_anagrafici else None
        vat_number = self._get_text(id_fiscale_iva, f"{{{ns}}}IdCodice", ns) if id_fiscale_iva else None
        tax_code = self._get_text(dati_anagrafici, f"{{{ns}}}CodiceFiscale", ns) if dati_anagrafici else None

        anagrafica = self._find_element(dati_anagrafici, f".//{{{ns}}}Anagrafica") if dati_anagrafici else None
        denominazione = self._get_text(anagrafica, f"{{{ns}}}Denominazione", ns) if anagrafica else None
        first_name = self._get_text(anagrafica, f"{{{ns}}}Nome", ns) if anagrafica else None
        last_name = self._get_text(anagrafica, f"{{{ns}}}Cognome", ns) if anagrafica else None

        name = denominazione if denominazione else f"{first_name or ''} {last_name or ''}".strip()

        sede = self._find_element(cedente, f".//{{{ns}}}Sede")
        address = self._parse_address(sede, ns) if sede else None

        return ParsedParty(
            vat_number=vat_number,
            tax_code=tax_code,
            name=name,
            first_name=first_name,
            last_name=last_name,
            address=address,
        )

    def _parse_cessionario_committente(self, header: ET.Element, ns: str) -> ParsedParty:
        """Parse CessionarioCommittente (customer)"""
        cessionario = self._find_element(header, f".//{{{ns}}}CessionarioCommittente")
        if cessionario is None:
            raise ValueError("CessionarioCommittente not found")

        dati_anagrafici = self._find_element(cessionario, f".//{{{ns}}}DatiAnagrafici")
        id_fiscale_iva = self._find_element(dati_anagrafici, f".//{{{ns}}}IdFiscaleIVA") if dati_anagrafici else None
        vat_number = self._get_text(id_fiscale_iva, f"{{{ns}}}IdCodice", ns) if id_fiscale_iva else None
        tax_code = self._get_text(dati_anagrafici, f"{{{ns}}}CodiceFiscale", ns) if dati_anagrafici else None

        anagrafica = self._find_element(dati_anagrafici, f".//{{{ns}}}Anagrafica") if dati_anagrafici else None
        denominazione = self._get_text(anagrafica, f"{{{ns}}}Denominazione", ns) if anagrafica else None
        first_name = self._get_text(anagrafica, f"{{{ns}}}Nome", ns) if anagrafica else None
        last_name = self._get_text(anagrafica, f"{{{ns}}}Cognome", ns) if anagrafica else None

        name = denominazione if denominazione else f"{first_name or ''} {last_name or ''}".strip()

        sede = self._find_element(cessionario, f".//{{{ns}}}Sede")
        address = self._parse_address(sede, ns) if sede else None

        return ParsedParty(
            vat_number=vat_number,
            tax_code=tax_code,
            name=name,
            first_name=first_name,
            last_name=last_name,
            address=address,
        )

    def _parse_address(self, sede: ET.Element, ns: str) -> ParsedAddress:
        """Parse Sede (address)"""
        street = self._get_text(sede, f"{{{ns}}}Indirizzo", ns, default="") or ""
        city = self._get_text(sede, f"{{{ns}}}Comune", ns, default="") or ""
        postal_code = self._get_text(sede, f"{{{ns}}}CAP", ns, default="") or ""
        province = self._get_text(sede, f"{{{ns}}}Provincia", ns)
        country = self._get_text(sede, f"{{{ns}}}Nazione", ns, default="IT") or "IT"

        return ParsedAddress(
            street=street,
            city=city,
            postal_code=postal_code,
            province=province,
            country=country,
        )

    def _parse_lines(self, dati_beni_servizi: ET.Element, ns: str) -> list[ParsedInvoiceLine]:
        """Parse DettaglioLinee"""
        lines = []
        for dettaglio in self._findall_elements(dati_beni_servizi, f".//{{{ns}}}DettaglioLinee"):
            line_number_str = self._get_text(dettaglio, f"{{{ns}}}NumeroLinea", ns, default="0") or "0"
            line_number = int(line_number_str)

            description = self._get_text(dettaglio, f"{{{ns}}}Descrizione", ns, default="") or ""

            quantity_str = self._get_text(dettaglio, f"{{{ns}}}Quantita", ns, default="1") or "1"
            quantity = Decimal(quantity_str)

            unit_price_str = self._get_text(dettaglio, f"{{{ns}}}PrezzoUnitario", ns, default="0") or "0"
            unit_price = Decimal(unit_price_str)

            taxable_amount_str = self._get_text(dettaglio, f"{{{ns}}}PrezzoTotale", ns, default="0") or "0"
            taxable_amount = Decimal(taxable_amount_str)

            vat_rate_str = self._get_text(dettaglio, f"{{{ns}}}AliquotaIVA", ns, default="0") or "0"
            vat_rate = Decimal(vat_rate_str)

            vat_nature_str = self._get_text(dettaglio, f"{{{ns}}}Natura", ns)
            vat_nature = NatureCode(vat_nature_str) if vat_nature_str else None
            unit_of_measure = self._get_text(dettaglio, f"{{{ns}}}UnitaMisura", ns)

            vat_amount = (taxable_amount * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
            total_amount = taxable_amount + vat_amount

            lines.append(
                ParsedInvoiceLine(
                    line_number=line_number,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    taxable_amount=taxable_amount,
                    vat_rate=vat_rate,
                    vat_nature=vat_nature,
                    vat_amount=vat_amount,
                    total_amount=total_amount,
                    unit_of_measure=unit_of_measure,
                )
            )

        return lines

    def _parse_vat_summaries(self, dati_beni_servizi: ET.Element, ns: str) -> list[ParsedVatSummary]:
        """Parse DatiRiepilogo (VAT summaries)"""
        summaries = []
        for riepilogo in self._findall_elements(dati_beni_servizi, f".//{{{ns}}}DatiRiepilogo"):
            vat_rate_str = self._get_text(riepilogo, f"{{{ns}}}AliquotaIVA", ns, default="0") or "0"
            vat_rate = Decimal(vat_rate_str)

            vat_nature_str = self._get_text(riepilogo, f"{{{ns}}}Natura", ns)
            vat_nature = NatureCode(vat_nature_str) if vat_nature_str else None

            taxable_amount_str = self._get_text(riepilogo, f"{{{ns}}}ImponibileImporto", ns, default="0") or "0"
            taxable_amount = Decimal(taxable_amount_str)

            vat_amount_str = self._get_text(riepilogo, f"{{{ns}}}Imposta", ns, default="0") or "0"
            vat_amount = Decimal(vat_amount_str)

            esigibilita_iva_str = self._get_text(riepilogo, f"{{{ns}}}EsigibilitaIVA", ns)
            esigibilita_iva = EsigibilitaIVA(esigibilita_iva_str) if esigibilita_iva_str else None

            summaries.append(
                ParsedVatSummary(
                    vat_rate=vat_rate,
                    vat_nature=vat_nature,
                    taxable_amount=taxable_amount,
                    vat_amount=vat_amount,
                    esigibilita_iva=esigibilita_iva,
                )
            )

        return summaries

    def _get_text(self, element: ET.Element | None, tag: str, ns: str, default: str | None = None) -> str | None:
        """Get text from element, return default if not found"""
        if element is None:
            return default

        # Try with namespace first
        child = element.find(tag, self.namespaces)
        if child is not None and child.text:
            return child.text.strip()

        # Try without namespace (for elements without prefix)
        tag_without_ns = tag.split("}")[1] if "}" in tag else tag
        child = element.find(tag_without_ns)
        if child is not None and child.text:
            return child.text.strip()

        return default
