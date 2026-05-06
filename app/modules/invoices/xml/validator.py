"""
Validatore XML per FatturaPA usando schema XSD
Supporta validazione locale e da S3
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from lxml import etree

from app.logger import logger

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client


@dataclass(slots=True)
class ValidationError:
    """Singolo errore di validazione"""

    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    domain: Optional[str] = None
    type: Optional[str] = None
    level: Optional[str] = None

    def __str__(self) -> str:
        location = ""
        if self.line is not None:
            location = f" (line {self.line}"
            if self.column is not None:
                location += f", column {self.column}"
            location += ")"
        return f"{self.message}{location}"


@dataclass(slots=True)
class ValidationResult:
    """Risultato della validazione XML"""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Numero totale di errori"""
        return len(self.errors)

    def get_error_summary(self) -> str:
        """Ritorna un sommario degli errori"""
        if self.is_valid:
            return "✓ XML valido"

        summary = f"✗ XML non valido - {self.error_count} errori trovati:\n"
        for i, error in enumerate(self.errors, 1):
            summary += f"  {i}. {error}\n"
        return summary.rstrip()


class XSDSchemaProvider(ABC):
    """Interfaccia astratta per provider di schema XSD"""

    @abstractmethod
    def get_schema_content(self) -> bytes:
        """
        Recupera il contenuto dello schema XSD

        Returns:
            Contenuto dello schema XSD come bytes

        Raises:
            FileNotFoundError: Se lo schema non è trovato
            Exception: Per altri errori di recupero
        """
        pass


class LocalXSDSchemaProvider(XSDSchemaProvider):
    """Provider per schema XSD da file system locale"""

    def __init__(self, xsd_path: str | Path):
        """
        Args:
            xsd_path: Path del file XSD locale
        """
        self.xsd_path = Path(xsd_path) if isinstance(xsd_path, str) else xsd_path

    def get_schema_content(self) -> bytes:
        """Legge lo schema XSD da file locale"""
        logger.debug(f"Loading XSD schema from local file: {self.xsd_path}")

        if not self.xsd_path.exists():
            logger.error(f"XSD schema file not found: {self.xsd_path}")
            raise FileNotFoundError(f"Schema XSD non trovato: {self.xsd_path}")

        if not self.xsd_path.is_file():
            logger.error(f"XSD path is not a file: {self.xsd_path}")
            raise ValueError(f"Il path non è un file: {self.xsd_path}")

        logger.debug(f"XSD schema loaded successfully from {self.xsd_path}")
        return self.xsd_path.read_bytes()


class S3XSDSchemaProvider(XSDSchemaProvider):
    """Provider per schema XSD da AWS S3"""

    def __init__(
        self,
        bucket: str,
        key: str,
        s3_client: Optional[S3Client] = None,
        region_name: Optional[str] = None,
    ):
        """
        Args:
            bucket: Nome del bucket S3
            key: Chiave dell'oggetto S3 (path del file)
            s3_client: Client boto3 S3 (opzionale, viene creato se non fornito)
            region_name: Regione AWS (opzionale, default dalla configurazione)
        """
        self.bucket = bucket
        self.key = key
        self._s3_client: Optional[S3Client] = s3_client
        self.region_name = region_name

    @property
    def s3_client(self) -> S3Client:
        """Lazy initialization del client S3"""
        if self._s3_client is None:
            try:
                import boto3
            except ImportError:
                logger.error("boto3 not installed for S3 operations")
                raise ImportError(
                    "boto3 is required for S3XSDSchemaProvider. "
                    "Install it with: pip install boto3"
                )

            logger.debug(f"Creating S3 client for region: {self.region_name}")
            self._s3_client = boto3.client("s3", region_name=self.region_name)  # type: ignore[assignment]

        return self._s3_client

    def get_schema_content(self) -> bytes:
        """Scarica lo schema XSD da S3"""
        logger.debug(f"Downloading XSD schema from S3: s3://{self.bucket}/{self.key}")
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=self.key)
            schema_bytes = response["Body"].read()
            logger.debug(f"XSD schema downloaded successfully from S3, size: {len(schema_bytes)} bytes")
            return schema_bytes
        except Exception as e:
            logger.error(f"Failed to download XSD schema from S3: {self.bucket}/{self.key}", exc_info=True)
            raise Exception(f"Errore nel recupero dello schema da S3 ({self.bucket}/{self.key}): {e}")


class FatturaPAXSDValidator:
    """
    Validatore XML FatturaPA usando schema XSD

    Supporta validazione da file locale o S3 tramite provider configurabili
    """

    def __init__(self, schema_provider: XSDSchemaProvider):
        """
        Args:
            schema_provider: Provider per recuperare lo schema XSD
        """
        self.schema_provider = schema_provider
        self._xsd_schema: Optional[etree.XMLSchema] = None

    @property
    def xsd_schema(self) -> etree.XMLSchema:
        """Lazy loading dello schema XSD"""
        if self._xsd_schema is None:
            logger.debug("Loading XSD schema for validation")
            # Se il provider è Local, usa il file direttamente per risolvere import relativi
            if isinstance(self.schema_provider, LocalXSDSchemaProvider):
                schema_doc = etree.parse(str(self.schema_provider.xsd_path))
            else:
                # Per S3 o altri provider, carica il contenuto in memoria
                schema_content = self.schema_provider.get_schema_content()
                parser = etree.XMLParser(no_network=True)
                schema_doc = etree.parse(BytesIO(schema_content), parser)

            self._xsd_schema = etree.XMLSchema(schema_doc)
            logger.debug("XSD schema loaded and compiled successfully")

        return self._xsd_schema

    def validate_xml_string(self, xml_content: str) -> ValidationResult:
        """
        Valida una stringa XML contro lo schema XSD

        Args:
            xml_content: Contenuto XML come stringa

        Returns:
            ValidationResult con esito e eventuali errori
        """
        logger.debug(f"Validating XML string, size: {len(xml_content)} bytes")
        try:
            # Parse XML
            xml_doc = etree.fromstring(xml_content.encode("utf-8"))

            # Valida contro schema
            is_valid = self.xsd_schema.validate(xml_doc)

            if is_valid:
                logger.info("XML validation successful")
                return ValidationResult(is_valid=True)

            # Estrai errori
            errors = self._extract_errors(self.xsd_schema.error_log)
            logger.warning(f"XML validation failed with {len(errors)} error(s)")
            return ValidationResult(is_valid=False, errors=errors)

        except etree.XMLSyntaxError as e:
            # Errore di parsing XML
            logger.error(f"XML syntax error at line {e.lineno}: {e.msg}")
            error = ValidationError(
                message=f"Errore di sintassi XML: {e.msg}",
                line=e.lineno,
                column=e.offset,
            )
            return ValidationResult(is_valid=False, errors=[error])

        except Exception as e:
            # Altri errori
            logger.error(f"Validation error: {str(e)}", exc_info=True)
            error = ValidationError(message=f"Errore durante la validazione: {str(e)}")
            return ValidationResult(is_valid=False, errors=[error])

    def validate_xml_file(self, xml_path: str | Path) -> ValidationResult:
        """
        Valida un file XML contro lo schema XSD

        Args:
            xml_path: Path del file XML da validare

        Returns:
            ValidationResult con esito e eventuali errori
        """
        xml_path = Path(xml_path) if isinstance(xml_path, str) else xml_path

        logger.info(f"Validating XML file: {xml_path}")

        if not xml_path.exists():
            logger.error(f"XML file not found: {xml_path}")
            error = ValidationError(message=f"File XML non trovato: {xml_path}")
            return ValidationResult(is_valid=False, errors=[error])

        xml_content = xml_path.read_text(encoding="utf-8")
        return self.validate_xml_string(xml_content)

    def validate_xml_bytes(self, xml_bytes: bytes) -> ValidationResult:
        """
        Valida XML da bytes contro lo schema XSD

        Args:
            xml_bytes: Contenuto XML come bytes

        Returns:
            ValidationResult con esito e eventuali errori
        """
        try:
            xml_content = xml_bytes.decode("utf-8")
            return self.validate_xml_string(xml_content)
        except UnicodeDecodeError as e:
            error = ValidationError(message=f"Errore decodifica UTF-8: {str(e)}")
            return ValidationResult(is_valid=False, errors=[error])

    @staticmethod
    def _extract_errors(error_log) -> list[ValidationError]:
        """Estrae errori dal log di lxml"""
        errors = []
        for error in error_log:
            validation_error = ValidationError(
                message=error.message,
                line=error.line,
                column=error.column,
                domain=error.domain_name,
                type=error.type_name,
                level=error.level_name,
            )
            errors.append(validation_error)

        return errors

    def clear_schema_cache(self) -> None:
        """Pulisce la cache dello schema (utile se lo schema cambia)"""
        self._xsd_schema = None


# Factory functions per comodità

def create_local_validator(xsd_path: str | Path) -> FatturaPAXSDValidator:
    """
    Crea un validatore con schema da file locale

    Args:
        xsd_path: Path del file XSD

    Returns:
        FatturaPAXSDValidator configurato

    Example:
        >>> validator = create_local_validator("path/to/schema.xsd")
        >>> result = validator.validate_xml_string(xml_content)
    """
    provider = LocalXSDSchemaProvider(xsd_path)
    return FatturaPAXSDValidator(provider)


def create_s3_validator(
    bucket: str,
    key: str,
    s3_client: Optional[S3Client] = None,
    region_name: Optional[str] = None,
) -> FatturaPAXSDValidator:
    """
    Crea un validatore con schema da S3

    Args:
        bucket: Nome del bucket S3
        key: Chiave dell'oggetto S3
        s3_client: Client boto3 S3 (opzionale)
        region_name: Regione AWS (opzionale)

    Returns:
        FatturaPAXSDValidator configurato

    Example:
        >>> validator = create_s3_validator(
        ...     bucket="my-bucket",
        ...     key="schemas/fatturapa.xsd"
        ... )
        >>> result = validator.validate_xml_string(xml_content)
    """
    provider = S3XSDSchemaProvider(bucket, key, s3_client, region_name)
    return FatturaPAXSDValidator(provider)
