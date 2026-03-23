"""
Modulo per la generazione di XML FatturaPA secondo schema VFPR12 v1.2.3

Questo modulo fornisce:
- Modelli dataclass per tutte le strutture FatturaPA
- Conversione da InvoiceCreatePayload a FatturaElettronica
- Generazione XML conforme allo schema SDI
- Validazione XML contro schema XSD
- Servizio orchestratore per la gestione completa del processo
"""

from app.modules.invoices.xml.models import FatturaElettronica
from app.modules.invoices.xml.converter import FatturaPAConverter
from app.modules.invoices.xml.generator import FatturaPAXMLGenerator
from app.modules.invoices.xml.service import FatturaPAService, XMLGenerationResult
from app.modules.invoices.xml.validator import (
    FatturaPAXSDValidator,
    ValidationResult,
    ValidationError,
    XSDSchemaProvider,
    LocalXSDSchemaProvider,
    S3XSDSchemaProvider,
    create_local_validator,
    create_s3_validator,
)
from app.modules.invoices.xml.constants import (
    XMLNamespace,
    XMLTag,
    XMLAttribute,
    DecimalPrecision,
)

__all__ = [
    # Core
    "FatturaElettronica",
    "FatturaPAConverter",
    "FatturaPAXMLGenerator",
    "FatturaPAService",
    "XMLGenerationResult",
    # Validazione
    "FatturaPAXSDValidator",
    "ValidationResult",
    "ValidationError",
    "XSDSchemaProvider",
    "LocalXSDSchemaProvider",
    "S3XSDSchemaProvider",
    "create_local_validator",
    "create_s3_validator",
    # Costanti
    "XMLNamespace",
    "XMLTag",
    "XMLAttribute",
    "DecimalPrecision",
]
