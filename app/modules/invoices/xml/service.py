"""
Servizio principale per la generazione e validazione XML FatturaPA
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.logger import logger

from app.modules.invoices.schemas.request import InvoiceCreatePayload
from app.modules.invoices.services.invoice_validator import InvoiceValidator, ValidationResult
from app.modules.invoices.xml.converter import FatturaPAConverter
from app.modules.invoices.xml.generator import FatturaPAXMLGenerator
from app.modules.invoices.xml.models import FatturaElettronica


@dataclass(slots=True)
class XMLGenerationResult:
    """Risultato della generazione XML"""

    success: bool
    xml_content: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    error_message: Optional[str] = None


class FatturaPAService:
    """
    Servizio orchestratore per la generazione di XML FatturaPA

    Questo servizio coordina:
    1. Validazione dei dati in ingresso
    2. Conversione da InvoiceCreatePayload a FatturaElettronica
    3. Generazione dell'XML secondo schema v1.2.3
    """

    def __init__(self):
        self.validator = InvoiceValidator()
        self.converter = FatturaPAConverter()
        self.generator = FatturaPAXMLGenerator()

    def generate_xml(
        self,
        invoice: InvoiceCreatePayload,
        validate: bool = True,
        pretty_print: bool = True,
    ) -> XMLGenerationResult:
        """
        Genera XML FatturaPA da una fattura

        Args:
            invoice: Dati della fattura
            validate: Se True, valida i dati prima di generare l'XML
            pretty_print: Se True, formatta l'XML con indentazione

        Returns:
            XMLGenerationResult con l'XML generato o eventuali errori
        """
        logger.info("Starting XML generation process")

        # Validazione (se richiesta)
        validation_result = None
        if validate:
            logger.debug("Validating invoice data")
            validation_result = self.validator.validate(invoice)
            if not validation_result.is_valid:
                logger.warning(f"Invoice validation failed: {len(validation_result.errors)} error(s)")
                return XMLGenerationResult(
                    success=False,
                    validation_result=validation_result,
                    error_message=f"Validation failed: {', '.join(validation_result.errors)}",
                )
            logger.debug("Invoice validation passed")

        try:
            # Conversione
            logger.debug("Converting invoice to FatturaElettronica structure")
            fattura_elettronica = self.converter.convert(invoice)

            # Generazione XML
            logger.debug("Generating XML from FatturaElettronica")
            xml_content = self.generator.generate_xml(fattura_elettronica, pretty_print=pretty_print)

            logger.info("XML generation completed successfully")
            return XMLGenerationResult(
                success=True,
                xml_content=xml_content,
                validation_result=validation_result,
            )

        except Exception as e:
            logger.error(f"XML generation failed: {str(e)}", exc_info=True)
            return XMLGenerationResult(
                success=False,
                validation_result=validation_result,
                error_message=f"XML generation failed: {str(e)}",
            )

    def convert_to_fattura_elettronica(self, invoice: InvoiceCreatePayload) -> FatturaElettronica:
        """
        Converte una fattura in struttura FatturaElettronica

        Args:
            invoice: Dati della fattura

        Returns:
            FatturaElettronica pronta per la generazione XML
        """
        return self.converter.convert(invoice)

    def generate_xml_from_fattura(
        self, fattura: FatturaElettronica, pretty_print: bool = True
    ) -> str:
        """
        Genera XML da una struttura FatturaElettronica già creata

        Args:
            fattura: Struttura FatturaElettronica
            pretty_print: Se True, formatta l'XML con indentazione

        Returns:
            Stringa XML
        """
        return self.generator.generate_xml(fattura, pretty_print=pretty_print)

    def validate_invoice(self, invoice: InvoiceCreatePayload) -> ValidationResult:
        """
        Valida una fattura senza generare XML

        Args:
            invoice: Dati della fattura

        Returns:
            ValidationResult con errori ed warning
        """
        return self.validator.validate(invoice)
