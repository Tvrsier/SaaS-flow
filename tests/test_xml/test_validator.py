"""
Test per FatturaPAXSDValidator
"""
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from app.modules.invoices.schemas.request import InvoiceCreatePayload
from app.modules.invoices.xml import (
    FatturaPAService,
    FatturaPAXSDValidator,
    LocalXSDSchemaProvider,
    S3XSDSchemaProvider,
    create_local_validator,
    create_s3_validator,
    ValidationResult,
)


class TestLocalXSDSchemaProvider:
    """Test per LocalXSDSchemaProvider"""

    def test_get_schema_content_success(self, xsd_schema_path: Path):
        """Test caricamento schema da file locale"""
        provider = LocalXSDSchemaProvider(xsd_schema_path)
        content = provider.get_schema_content()

        assert isinstance(content, bytes)
        assert len(content) > 0
        assert b'<?xml' in content

    def test_get_schema_content_file_not_found(self):
        """Test errore quando file non esiste"""
        provider = LocalXSDSchemaProvider("/path/non/esistente/schema.xsd")

        with pytest.raises(FileNotFoundError):
            provider.get_schema_content()

    def test_get_schema_content_path_is_directory(self, tmp_path: Path):
        """Test errore quando il path è una directory"""
        provider = LocalXSDSchemaProvider(tmp_path)

        with pytest.raises(ValueError, match="Il path non è un file"):
            provider.get_schema_content()


class TestS3XSDSchemaProvider:
    """Test per S3XSDSchemaProvider"""

    def test_lazy_client_initialization(self):
        """Test lazy initialization del client S3"""
        provider = S3XSDSchemaProvider(
            bucket="test-bucket",
            key="test-key.xsd",
        )

        # Client non è ancora stato creato
        assert provider._s3_client is None

        # Accesso al property crea il client
        with patch('boto3.client') as mock_boto_client:
            mock_client = Mock()
            mock_boto_client.return_value = mock_client

            _ = provider.s3_client

            # Verifica che boto3.client sia stato chiamato
            mock_boto_client.assert_called_once_with('s3', region_name=None)

    def test_custom_s3_client(self):
        """Test uso di client S3 custom"""
        custom_client = Mock()

        provider = S3XSDSchemaProvider(
            bucket="test-bucket",
            key="test-key.xsd",
            s3_client=custom_client,
        )

        # Client custom è usato direttamente
        assert provider.s3_client is custom_client

    def test_get_schema_content_success(self):
        """Test download schema da S3"""
        mock_client = Mock()
        mock_response = {
            'Body': Mock()
        }
        mock_response['Body'].read.return_value = b'<?xml version="1.0"?><schema/>'
        mock_client.get_object.return_value = mock_response

        provider = S3XSDSchemaProvider(
            bucket="test-bucket",
            key="schemas/fatturapa.xsd",
            s3_client=mock_client,
        )

        content = provider.get_schema_content()

        assert isinstance(content, bytes)
        assert b'<?xml' in content

        # Verifica chiamata corretta a S3
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="schemas/fatturapa.xsd"
        )

    def test_get_schema_content_s3_error(self):
        """Test errore durante download da S3"""
        mock_client = Mock()
        mock_client.get_object.side_effect = Exception("S3 Error")

        provider = S3XSDSchemaProvider(
            bucket="test-bucket",
            key="test.xsd",
            s3_client=mock_client,
        )

        with pytest.raises(Exception, match="Errore nel recupero dello schema da S3"):
            provider.get_schema_content()


class TestFatturaPAXSDValidator:
    """Test per FatturaPAXSDValidator"""

    @pytest.fixture
    def validator(self, xsd_schema_path: Path) -> FatturaPAXSDValidator:
        """Validator con schema locale"""
        provider = LocalXSDSchemaProvider(xsd_schema_path)
        return FatturaPAXSDValidator(provider)

    @pytest.fixture
    def valid_xml(self, invoice_standard: InvoiceCreatePayload) -> str:
        """XML valido generato da una fattura"""
        service = FatturaPAService()
        result = service.generate_xml(invoice_standard, validate=False)
        return result.xml_content

    def test_validate_valid_xml(self, validator: FatturaPAXSDValidator, valid_xml: str):
        """Test validazione XML valido"""
        result = validator.validate_xml_string(valid_xml)

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.error_count == 0
        assert len(result.errors) == 0

    def test_validate_invalid_xml_syntax(self, validator: FatturaPAXSDValidator):
        """Test validazione XML con errori di sintassi"""
        invalid_xml = "<?xml version='1.0'?><root>non chiuso"

        result = validator.validate_xml_string(invalid_xml)

        assert result.is_valid is False
        assert result.error_count > 0
        assert "sintassi" in result.errors[0].message.lower()

    def test_validate_invalid_xml_schema(self, validator: FatturaPAXSDValidator):
        """Test validazione XML non conforme allo schema"""
        # XML ben formato ma non conforme allo schema FatturaPA
        invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <FatturaElettronica xmlns="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12">
            <ElementoNonEsistente>valore</ElementoNonEsistente>
        </FatturaElettronica>"""

        result = validator.validate_xml_string(invalid_xml)

        assert result.is_valid is False
        assert result.error_count > 0

    def test_validate_xml_file_success(
        self,
        validator: FatturaPAXSDValidator,
        valid_xml: str,
        test_output_dir: Path,
    ):
        """Test validazione da file"""
        xml_file = test_output_dir / "test.xml"
        xml_file.write_text(valid_xml, encoding="utf-8")

        result = validator.validate_xml_file(xml_file)

        assert result.is_valid is True
        assert result.error_count == 0

    def test_validate_xml_file_not_found(self, validator: FatturaPAXSDValidator):
        """Test validazione file non esistente"""
        result = validator.validate_xml_file("/path/non/esistente/file.xml")

        assert result.is_valid is False
        assert result.error_count == 1
        assert "non trovato" in result.errors[0].message

    def test_validate_xml_bytes(self, validator: FatturaPAXSDValidator, valid_xml: str):
        """Test validazione da bytes"""
        xml_bytes = valid_xml.encode("utf-8")

        result = validator.validate_xml_bytes(xml_bytes)

        assert result.is_valid is True
        assert result.error_count == 0

    def test_validation_result_error_summary(self, validator: FatturaPAXSDValidator):
        """Test formattazione error summary"""
        invalid_xml = "<?xml version='1.0'?><root>non chiuso"

        result = validator.validate_xml_string(invalid_xml)

        summary = result.get_error_summary()

        assert "✗" in summary
        assert "errori trovati" in summary
        assert str(result.error_count) in summary

    def test_validation_result_success_summary(
        self,
        validator: FatturaPAXSDValidator,
        valid_xml: str,
    ):
        """Test summary per validazione OK"""
        result = validator.validate_xml_string(valid_xml)

        summary = result.get_error_summary()

        assert "✓" in summary
        assert "valido" in summary

    def test_schema_lazy_loading(self, xsd_schema_path: Path):
        """Test lazy loading dello schema XSD"""
        provider = LocalXSDSchemaProvider(xsd_schema_path)
        validator = FatturaPAXSDValidator(provider)

        # Schema non ancora caricato
        assert validator._xsd_schema is None

        # Primo accesso carica lo schema
        _ = validator.xsd_schema
        assert validator._xsd_schema is not None

        # Secondo accesso usa lo schema in cache
        schema1 = validator.xsd_schema
        schema2 = validator.xsd_schema
        assert schema1 is schema2

    def test_clear_schema_cache(self, xsd_schema_path: Path):
        """Test pulizia cache schema"""
        provider = LocalXSDSchemaProvider(xsd_schema_path)
        validator = FatturaPAXSDValidator(provider)

        # Carica schema
        _ = validator.xsd_schema
        assert validator._xsd_schema is not None

        # Pulisci cache
        validator.clear_schema_cache()
        assert validator._xsd_schema is None

    def test_validation_error_with_line_info(self, validator: FatturaPAXSDValidator):
        """Test che gli errori contengano informazioni su linea/colonna"""
        # XML con errore di sintassi su una linea specifica
        invalid_xml = """<?xml version="1.0"?>
        <root>
            <element>
        </root>"""

        result = validator.validate_xml_string(invalid_xml)

        assert result.error_count > 0
        error = result.errors[0]

        # L'errore dovrebbe avere info sulla linea
        assert error.line is not None
        assert error.line > 0


class TestValidatorFactoryFunctions:
    """Test per factory functions"""

    def test_create_local_validator(self, xsd_schema_path: Path):
        """Test create_local_validator"""
        validator = create_local_validator(xsd_schema_path)

        assert isinstance(validator, FatturaPAXSDValidator)
        assert isinstance(validator.schema_provider, LocalXSDSchemaProvider)

    def test_create_s3_validator(self):
        """Test create_s3_validator"""
        mock_client = Mock()

        validator = create_s3_validator(
            bucket="test-bucket",
            key="test.xsd",
            s3_client=mock_client,
            region_name="eu-south-1",
        )

        assert isinstance(validator, FatturaPAXSDValidator)
        assert isinstance(validator.schema_provider, S3XSDSchemaProvider)


class TestValidatorIntegration:
    """Test di integrazione validator con diversi tipi di fatture"""

    @pytest.fixture
    def validator(self, xsd_schema_path: Path) -> FatturaPAXSDValidator:
        return create_local_validator(xsd_schema_path)

    @pytest.fixture
    def service(self) -> FatturaPAService:
        return FatturaPAService()

    def test_validate_standard_b2b_invoice(
        self,
        validator: FatturaPAXSDValidator,
        service: FatturaPAService,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test validazione fattura B2B standard"""
        xml_result = service.generate_xml(invoice_standard, validate=False)
        assert xml_result.success

        validation = validator.validate_xml_string(xml_result.xml_content)
        assert validation.is_valid, f"Errori: {validation.get_error_summary()}"

    def test_validate_b2c_invoice(
        self,
        validator: FatturaPAXSDValidator,
        service: FatturaPAService,
        invoice_b2c: InvoiceCreatePayload,
    ):
        """Test validazione fattura B2C"""
        xml_result = service.generate_xml(invoice_b2c, validate=False)
        assert xml_result.success

        validation = validator.validate_xml_string(xml_result.xml_content)
        assert validation.is_valid, f"Errori: {validation.get_error_summary()}"

    def test_validate_invoice_with_stamp_duty(
        self,
        validator: FatturaPAXSDValidator,
        service: FatturaPAService,
        issuer_company,
        customer_company,
        items_standard,
        payment_bank_transfer,
        stamp_duty_enabled,
    ):
        """Test validazione fattura con bollo"""
        from app.modules.invoices.schemas.request import InvoiceCreatePayload
        from app.modules.invoices.domain.enums import DocumentType

        invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-BOLLO",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=items_standard,
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_enabled,
            causal=["Fattura con bollo"],
        )

        xml_result = service.generate_xml(invoice, validate=False)
        assert xml_result.success

        validation = validator.validate_xml_string(xml_result.xml_content)
        assert validation.is_valid, f"Errori: {validation.get_error_summary()}"

    def test_validate_invoice_with_exempt_operations(
        self,
        validator: FatturaPAXSDValidator,
        service: FatturaPAService,
        issuer_company,
        customer_company,
        items_with_exempt,
        payment_bank_transfer,
        stamp_duty_disabled,
    ):
        """Test validazione fattura con operazioni esenti"""
        from app.modules.invoices.schemas.request import InvoiceCreatePayload
        from app.modules.invoices.domain.enums import DocumentType

        invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-ESENTI",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=items_with_exempt,
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_disabled,
            causal=["Operazioni esenti/non imponibili"],
        )

        xml_result = service.generate_xml(invoice, validate=False)
        assert xml_result.success

        validation = validator.validate_xml_string(xml_result.xml_content)
        assert validation.is_valid, f"Errori: {validation.get_error_summary()}"
