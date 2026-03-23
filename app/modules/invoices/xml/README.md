# Modulo XML FatturaPA

Modulo completo per la generazione e validazione di XML FatturaPA secondo schema VFPR12 v1.2.3.

## 📦 Installazione Dipendenze

```bash
# Dipendenze base (obbligatorie)
pip install lxml

# Per validazione con S3 (opzionale)
pip install boto3

# Type stubs per mypy (development)
pip install boto3-stubs[s3] types-lxml
```

## 🚀 Quick Start

### Generazione XML Completa

```python
from datetime import date
from decimal import Decimal
from app.modules.invoices.schemas.request import (
    InvoiceCreatePayload,
    PartyPayload,
    AddressPayload,
    InvoiceLinePayload,
    PaymentPayload,
    StampDutyPayload,
)
from app.modules.invoices.domain.enums import (
    SubjectType,
    DocumentType,
    FiscalRegime,
    LineType,
    PaymentTerms,
    PaymentMethod,
)
from app.modules.invoices.xml import FatturaPAService

# Crea payload fattura
invoice = InvoiceCreatePayload(
    invoice_number="FE-2026-000123",
    invoice_date=date(2026, 3, 23),
    currency="EUR",
    language="it",
    document_type=DocumentType.TD01,
    issuer=PartyPayload(
        subject_type=SubjectType.COMPANY,
        company_name="Taverna Tech SRLS",
        vat_number="12345678901",
        tax_code="12345678901",
        fiscal_regime=FiscalRegime.RF01,
        address=AddressPayload(
            street="Via Roma",
            street_number="10",
            zip_code="15121",
            city="Alessandria",
            province="AL",
            country="IT",
        ),
    ),
    customer=PartyPayload(
        subject_type=SubjectType.INDIVIDUAL,
        first_name="Mario",
        last_name="Rossi",
        tax_code="RSSMRA80A01F205X",
        recipient_code="0000000",
        pec="mario.rossi@pec.it",
        address=AddressPayload(
            street="Via Verdi",
            street_number="22",
            zip_code="20100",
            city="Milano",
            province="MI",
            country="IT",
        ),
    ),
    items=[
        InvoiceLinePayload(
            line_number=1,
            type=LineType.SERVICE,
            sku="SERV-001",
            name="Consulenza",
            description="Consulenza tecnica",
            quantity=Decimal("2.00"),
            unit_of_measure="H",
            unit_price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            vat_rate=Decimal("22.00"),
        )
    ],
    payment=PaymentPayload(
        payment_terms=PaymentTerms.TP02,
        payment_method=PaymentMethod.MP05,
        due_date=date(2026, 4, 23),
        iban="IT60X0542811101000000123456",
        beneficiary="Taverna Tech SRLS",
    ),
    stamp_duty=StampDutyPayload(enabled=False),
    causal=["Consulenza tecnica"],
)

# Genera XML
service = FatturaPAService()
result = service.generate_xml(invoice, validate=True, pretty_print=True)

if result.success:
    print("✓ XML generato con successo!")
    print(result.xml_content)

    # Salva su file
    with open("fattura.xml", "w", encoding="utf-8") as f:
        f.write(result.xml_content)
else:
    print(f"✗ Errore: {result.error_message}")
    if result.validation_result:
        for error in result.validation_result.errors:
            print(f"  - {error}")
```

## 🔍 Validazione XML

### Validazione Locale (Development)

```python
from app.modules.invoices.xml import create_local_validator

# Crea validatore con schema locale
validator = create_local_validator(
    "resources/invoices/schemas/fattura_pa_latest/Schema_VFPR12_v1.2.3.xsd.xml"
)

# Valida XML
result = validator.validate_xml_string(xml_content)

if result.is_valid:
    print("✓ XML valido secondo schema XSD!")
else:
    print("✗ XML non valido:")
    print(result.get_error_summary())

    # Dettagli errori
    for error in result.errors:
        print(f"Linea {error.line}: {error.message}")
```

### Validazione S3 (Production)

```python
from app.modules.invoices.xml import create_s3_validator

# Crea validatore con schema da S3
validator = create_s3_validator(
    bucket="my-saas-schemas",
    key="fatturapa/Schema_VFPR12_v1.2.3.xsd.xml",
    region_name="eu-south-1",
)

# Valida XML
result = validator.validate_xml_file("fattura.xml")

if result.is_valid:
    print("✓ XML valido!")
else:
    print(f"✗ Trovati {result.error_count} errori")
    print(result.get_error_summary())
```

### Validazione con Client S3 Custom

```python
import boto3
from app.modules.invoices.xml import create_s3_validator

# Client S3 con configurazione custom
s3_client = boto3.client(
    "s3",
    region_name="eu-south-1",
    aws_access_key_id="...",
    aws_secret_access_key="...",
)

validator = create_s3_validator(
    bucket="my-bucket",
    key="schemas/fatturapa.xsd",
    s3_client=s3_client,
)

result = validator.validate_xml_string(xml_content)
```

## 🔧 Uso Avanzato

### Provider Custom per Schema XSD

Implementa `XSDSchemaProvider` per casi d'uso specifici (es. caching Redis):

```python
from app.modules.invoices.xml import (
    XSDSchemaProvider,
    FatturaPAXSDValidator,
)
import redis

class CachedSchemaProvider(XSDSchemaProvider):
    """Provider con cache Redis"""

    def __init__(self, s3_bucket: str, s3_key: str, redis_client):
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 ora

    def get_schema_content(self) -> bytes:
        cache_key = f"xsd_schema:{self.s3_key}"

        # Controlla cache
        cached = self.redis.get(cache_key)
        if cached:
            return cached

        # Scarica da S3
        import boto3
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=self.s3_bucket, Key=self.s3_key)
        schema_content = response["Body"].read()

        # Salva in cache
        self.redis.setex(cache_key, self.cache_ttl, schema_content)

        return schema_content

# Usa provider custom
redis_client = redis.Redis(host="localhost", port=6379)
provider = CachedSchemaProvider(
    s3_bucket="my-bucket",
    s3_key="schemas/fatturapa.xsd",
    redis_client=redis_client,
)
validator = FatturaPAXSDValidator(provider)
```

### Conversione Separata

Puoi separare conversione e generazione XML:

```python
from app.modules.invoices.xml import FatturaPAConverter, FatturaPAXMLGenerator

# Converti payload in struttura FatturaElettronica
converter = FatturaPAConverter()
fattura_elettronica = converter.convert(invoice)

# Modifica se necessario
fattura_elettronica.FatturaElettronicaBody[0].DatiGenerali.DatiGeneraliDocumento.Causale.append(
    "Causale aggiuntiva"
)

# Genera XML
generator = FatturaPAXMLGenerator()
xml_content = generator.generate_xml(fattura_elettronica, pretty_print=True)
```

### Validazione Multiple Files

```python
from pathlib import Path
from app.modules.invoices.xml import create_local_validator

validator = create_local_validator("path/to/schema.xsd")

xml_dir = Path("invoices/xml")
results = {}

for xml_file in xml_dir.glob("*.xml"):
    result = validator.validate_xml_file(xml_file)
    results[xml_file.name] = result

    if not result.is_valid:
        print(f"✗ {xml_file.name}: {result.error_count} errori")

# Statistiche
total = len(results)
valid = sum(1 for r in results.values() if r.is_valid)
print(f"\n{valid}/{total} file XML validi")
```

## 📊 Costanti e Configurazione

Il modulo usa costanti configurabili per mantenere il codice pulito:

```python
from app.modules.invoices.xml.constants import (
    XMLNamespace,
    XMLTag,
    DecimalPrecision,
)

# Namespace
print(XMLNamespace.FATTURA_PA.value)
# "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

# Tag XML
print(XMLTag.FATTURA_ELETTRONICA.value)  # "FatturaElettronica"
print(XMLTag.DATI_GENERALI.value)        # "DatiGenerali"

# Precisione decimali
print(DecimalPrecision.STANDARD)  # 2 (importi, IVA)
print(DecimalPrecision.EXTENDED)  # 8 (prezzi unitari, quantità)
```

## 🧪 Testing

```python
import pytest
from app.modules.invoices.xml import FatturaPAService, create_local_validator

def test_generate_and_validate():
    """Test end-to-end: genera e valida XML"""

    # Genera XML
    service = FatturaPAService()
    result = service.generate_xml(sample_invoice)

    assert result.success
    assert result.xml_content is not None

    # Valida contro XSD
    validator = create_local_validator("path/to/schema.xsd")
    validation = validator.validate_xml_string(result.xml_content)

    assert validation.is_valid
    assert validation.error_count == 0
```

## 🐛 Troubleshooting

### Errore: "boto3 is required for S3XSDSchemaProvider"

```bash
pip install boto3 boto3-stubs[s3]
```

### Errore: "cannot import name 'etree' from 'lxml'"

```bash
pip install --upgrade lxml
```

### XML non valido: "Element not allowed"

Verifica che tutti i campi obbligatori siano compilati:
- `RegimeFiscale` per il cedente
- `CodiceFiscale` o `PartitaIVA` per il cliente
- `CodiceDestinatario` o `PEC` per il cliente

### Performance: schema XSD caricato ogni volta

Usa il pattern singleton o implementa un provider con cache:

```python
# Singleton validator
_validator_instance = None

def get_validator():
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = create_local_validator("path/to/schema.xsd")
    return _validator_instance
```

## 📚 Riferimenti

- [Specifiche FatturaPA](https://www.fatturapa.gov.it/it/norme-e-regole/documentazione-fattura-elettronica/formato-fatturapa/)
- [Schema XSD v1.2.3](http://www.fatturapa.gov.it/export/documenti/fatturapa/v1.2.3/Schema_del_file_xml_FatturaPA_v1.2.3.xsd)
- [Codici IPA](https://www.indicepa.gov.it/)
