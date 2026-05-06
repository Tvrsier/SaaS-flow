"""
Test per FatturaPAService (end-to-end)
"""
from pathlib import Path

import pytest

from app.modules.invoices.schemas.request import InvoiceCreatePayload
from app.modules.invoices.xml import (
    FatturaPAService,
    XMLGenerationResult,
    create_local_validator,
)


class TestFatturaPAService:
    """Test end-to-end per il servizio completo"""

    @pytest.fixture
    def service(self) -> FatturaPAService:
        return FatturaPAService()

    def test_generate_xml_success(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test generazione XML con successo"""
        result = service.generate_xml(invoice_standard, validate=True)

        assert isinstance(result, XMLGenerationResult)
        assert result.success is True
        assert result.xml_content is not None
        assert result.error_message is None
        assert len(result.xml_content) > 0

    def test_generate_xml_without_validation(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test generazione XML senza validazione payload"""
        result = service.generate_xml(invoice_standard, validate=False)

        assert result.success is True
        assert result.xml_content is not None
        assert result.validation_result is None

    def test_generate_xml_with_validation_success(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test generazione XML con validazione payload che passa"""
        result = service.generate_xml(invoice_standard, validate=True)

        assert result.success is True
        assert result.validation_result is not None
        assert result.validation_result.is_valid is True

    def test_generate_xml_with_validation_failure(
        self,
        service: FatturaPAService,
        issuer_company,
        customer_company,
        payment_bank_transfer,
        stamp_duty_disabled,
    ):
        """Test generazione XML con validazione payload che fallisce"""
        from app.modules.invoices.domain.enums import DocumentType

        # Fattura senza righe (invalida)
        invalid_invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-INVALID",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=[],  # Nessuna riga!
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_disabled,
            causal=["Test"],
        )

        result = service.generate_xml(invalid_invoice, validate=True)

        assert result.success is False
        assert result.xml_content is None
        assert result.error_message is not None
        assert "Validation failed" in result.error_message

    def test_generate_xml_pretty_print(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test generazione XML formattato"""
        result = service.generate_xml(invoice_standard, pretty_print=True)

        assert result.success
        # XML formattato ha indentazioni
        assert '\n  ' in result.xml_content or '\n    ' in result.xml_content

    def test_generate_xml_no_pretty_print(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test generazione XML compatto"""
        result = service.generate_xml(invoice_standard, pretty_print=False)

        assert result.success
        # XML compatto ha meno newline
        lines = result.xml_content.split('\n')
        assert len(lines) < 100

    def test_convert_to_fattura_elettronica(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test conversione a FatturaElettronica"""
        from app.modules.invoices.xml.models import FatturaElettronica

        fattura = service.convert_to_fattura_elettronica(invoice_standard)

        assert isinstance(fattura, FatturaElettronica)
        assert fattura.versione == "FPR12"
        assert len(fattura.FatturaElettronicaBody) == 1

    def test_generate_xml_from_fattura(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test generazione XML da FatturaElettronica già convertita"""
        # Converti
        fattura = service.convert_to_fattura_elettronica(invoice_standard)

        # Genera XML
        xml = service.generate_xml_from_fattura(fattura, pretty_print=True)

        assert isinstance(xml, str)
        assert len(xml) > 0
        assert '<?xml' in xml

    def test_validate_invoice(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test validazione payload senza generare XML"""
        result = service.validate_invoice(invoice_standard)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_invoice_with_errors(
        self,
        service: FatturaPAService,
        issuer_company,
        customer_company,
        payment_bank_transfer,
        stamp_duty_disabled,
    ):
        """Test validazione payload con errori"""
        from app.modules.invoices.domain.enums import DocumentType

        # Fattura invalida: nessuna riga
        invalid_invoice = InvoiceCreatePayload(
            invoice_number="FE-INVALID",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=[],
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_disabled,
            causal=["Test"],
        )

        result = service.validate_invoice(invalid_invoice)

        assert result.is_valid is False
        assert len(result.errors) > 0


class TestServiceEndToEndWithValidator:
    """Test end-to-end con validazione XSD"""

    @pytest.fixture
    def service(self) -> FatturaPAService:
        return FatturaPAService()

    def test_generate_and_validate_with_xsd(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
        xsd_schema_path: Path,
    ):
        """Test completo: genera XML e valida con XSD"""
        # Genera XML
        result = service.generate_xml(invoice_standard, validate=True)
        assert result.success

        # Valida con XSD
        validator = create_local_validator(xsd_schema_path)
        xsd_validation = validator.validate_xml_string(result.xml_content)

        assert xsd_validation.is_valid, xsd_validation.get_error_summary()

    def test_save_and_validate_xml_file(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
        xsd_schema_path: Path,
        test_output_dir: Path,
    ):
        """Test salvataggio file XML e validazione"""
        # Genera XML
        result = service.generate_xml(invoice_standard)
        assert result.success

        # Salva su file
        xml_file = test_output_dir / f"{invoice_standard.invoice_number}.xml"
        xml_file.write_text(result.xml_content, encoding="utf-8")

        assert xml_file.exists()
        assert xml_file.stat().st_size > 0

        # Valida file
        validator = create_local_validator(xsd_schema_path)
        validation = validator.validate_xml_file(xml_file)

        assert validation.is_valid, validation.get_error_summary()

    def test_multiple_invoices_batch_validation(
        self,
        service: FatturaPAService,
        xsd_schema_path: Path,
        test_output_dir: Path,
        invoice_standard,
        invoice_b2c,
    ):
        """Test generazione e validazione batch di fatture"""
        invoices = [
            ("standard", invoice_standard),
            ("b2c", invoice_b2c),
        ]

        validator = create_local_validator(xsd_schema_path)
        results = {}

        for name, invoice in invoices:
            # Genera
            result = service.generate_xml(invoice)
            assert result.success, f"Generazione fallita per {name}"

            # Salva
            xml_file = test_output_dir / f"invoice_{name}.xml"
            xml_file.write_text(result.xml_content, encoding="utf-8")

            # Valida
            validation = validator.validate_xml_file(xml_file)
            results[name] = validation

        # Verifica tutte valide
        for name, validation in results.items():
            assert validation.is_valid, f"{name}: {validation.get_error_summary()}"

    def test_xml_content_correctness(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test correttezza contenuto XML generato"""
        result = service.generate_xml(invoice_standard)
        xml = result.xml_content

        # Verifica presenza dati chiave
        assert invoice_standard.invoice_number in xml
        assert invoice_standard.issuer.company_name in xml
        assert invoice_standard.customer.company_name in xml

        # Verifica namespace
        assert 'xmlns="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"' in xml

        # Verifica versione
        assert 'versione="FPR12"' in xml

    def test_error_handling_exception(
        self,
        service: FatturaPAService,
    ):
        """Test gestione eccezioni durante generazione"""
        # Crea un mock che solleva eccezione
        from unittest.mock import patch, Mock

        with patch.object(service.converter, 'convert', side_effect=Exception("Test error")):
            result = service.generate_xml(Mock())

            assert result.success is False
            assert "Test error" in result.error_message


class TestServicePerformance:
    """Test performance del servizio"""

    @pytest.fixture
    def service(self) -> FatturaPAService:
        return FatturaPAService()

    def test_generate_multiple_invoices_performance(
        self,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test generazione multipla di fatture"""
        import time

        count = 10
        start = time.time()

        for i in range(count):
            invoice = invoice_standard.model_copy(deep=True)
            invoice.invoice_number = f"FE-2026-{i:06d}"

            result = service.generate_xml(invoice, validate=False)
            assert result.success

        elapsed = time.time() - start

        # Dovrebbe essere veloce (< 1 secondo per 10 fatture)
        assert elapsed < 1.0, f"Troppo lento: {elapsed:.2f}s per {count} fatture"

        # Media per fattura
        avg_per_invoice = elapsed / count
        print(f"\nPerformance: {avg_per_invoice*1000:.2f}ms per fattura")
