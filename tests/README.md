# Test Suite - FatturaPA XML Generator

Suite completa di test per il modulo di generazione e validazione XML FatturaPA.

## 🚀 Quick Start

```bash
# Installa dipendenze test
pip install -r requirements-test.txt

# Esegui tutti i test
pytest

# Esegui con coverage
pytest --cov=app --cov-report=html

# Esegui test specifici
pytest tests/test_converter.py
pytest tests/test_validator.py -v
pytest -k "test_scenario"
```

## 📦 Struttura Test

```
tests/
├── conftest.py                    # Fixtures condivise
├── test_converter.py              # Test conversione payload → FatturaElettronica
├── test_generator.py              # Test generazione XML
├── test_validator.py              # Test validazione XSD (locale + S3)
├── test_service.py                # Test end-to-end servizio
└── test_invoice_scenarios.py     # Test scenari reali
```

## 🧪 Tipologie di Test

### Test Unitari

**test_converter.py** (21 test)
- Conversione payload a FatturaElettronica
- Header: dati trasmissione, cedente, cessionario
- Body: dati generali, linee, riepilogo, pagamento
- Calcolo totali automatico
- Gestione bollo, sconti, codici articolo

**test_generator.py** (16 test)
- Generazione XML ben formato
- Struttura e namespace corretti
- Formattazione decimali (2 e 8 cifre)
- Pretty print on/off
- Encoding UTF-8

**test_validator.py** (18 test)
- Provider locale e S3
- Validazione XML contro XSD
- Gestione errori sintassi e schema
- Lazy loading schema
- Factory functions

### Test Integrazione

**test_service.py** (15 test)
- End-to-end generazione + validazione
- Gestione errori
- Batch processing
- Performance test
- Salvataggio file

### Test Scenari Reali

**test_invoice_scenarios.py** (10 scenari)
1. ✅ Abbonamento SaaS annuale
2. ✅ Consulenza con sconto e bollo
3. ✅ Mix prodotti e servizi
4. ✅ Operazioni non imponibili (export)
5. ✅ Regime forfettario
6. ✅ Nota di credito
7. ✅ Vendita retail B2C
8. ✅ Aliquote IVA multiple
9. ✅ Pagamento rateale
10. ✅ Fattura importo elevato

## 🔍 Fixtures Disponibili

### Cedenti (Issuer)
- `issuer_company`: Azienda standard (SRLS)
- `issuer_individual`: Persona fisica professionista
- `issuer_forfettario`: Regime forfettario

### Clienti (Customer)
- `customer_company`: Azienda cliente
- `customer_individual`: Privato cittadino
- `customer_foreign`: Cliente estero (GB)

### Righe Fattura
- `items_standard`: Righe standard con IVA 22%
- `items_with_exempt`: Righe esenti/non imponibili
- `items_mixed_vat`: Aliquote multiple (4%, 10%, 22%)

### Pagamenti
- `payment_bank_transfer`: Bonifico bancario
- `payment_cash`: Contanti
- `payment_installments`: Rate

### Altro
- `stamp_duty_enabled`: Bollo attivo
- `stamp_duty_disabled`: Bollo disattivo
- `xsd_schema_path`: Path schema XSD

## 📊 Esecuzione Test

### Esegui tutti i test
```bash
pytest
```

### Esegui con markers
```bash
# Solo test unitari
pytest -m unit

# Solo test integrazione
pytest -m integration

# Solo test validator
pytest -m validator

# Escludi test lenti
pytest -m "not slow"
```

### Esegui test specifici
```bash
# Per modulo
pytest tests/test_converter.py

# Per classe
pytest tests/test_validator.py::TestLocalXSDSchemaProvider

# Per singolo test
pytest tests/test_service.py::TestFatturaPAService::test_generate_xml_success

# Per pattern nome
pytest -k "scenario"
pytest -k "validation"
```

### Output dettagliato
```bash
# Verbose
pytest -v

# Extra verbose con output
pytest -vv -s

# Solo fallimenti
pytest --lf

# Stop al primo errore
pytest -x
```

### Coverage
```bash
# Report terminale
pytest --cov=app

# Report HTML
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Report con linee mancanti
pytest --cov=app --cov-report=term-missing
```

## 🎯 Obiettivi Coverage

- **Target globale**: > 90%
- **Modulo xml**: > 95%
- **Services**: > 85%
- **Validators**: > 90%

## 🐛 Debugging Test

### Stampa output
```bash
# Mostra print() nei test
pytest -s

# Mostra logging
pytest --log-cli-level=DEBUG
```

### Esegui con debugger
```python
# Aggiungi nel test
import pdb; pdb.set_trace()
```

```bash
pytest --pdb  # Break su errori
```

### Test singolo con dettagli
```bash
pytest tests/test_validator.py::test_validate_valid_xml -vv -s
```

## 📝 Scrivere Nuovi Test

### Template test unitario
```python
def test_feature_description(fixture1, fixture2):
    """Test che verifica comportamento specifico"""
    # Arrange
    input_data = prepare_test_data()

    # Act
    result = function_to_test(input_data)

    # Assert
    assert result.is_valid
    assert result.value == expected_value
```

### Template test scenario
```python
def test_scenario_real_world_case(
    service: FatturaPAService,
    validator_path: Path,
):
    """Scenario: descrizione caso d'uso reale"""
    # Crea invoice per scenario
    invoice = InvoiceCreatePayload(...)

    # Genera XML
    result = service.generate_xml(invoice)
    assert result.success

    # Valida con XSD
    validator = create_local_validator(validator_path)
    validation = validator.validate_xml_string(result.xml_content)
    assert validation.is_valid, validation.get_error_summary()
```

## 🔧 Troubleshooting

### Test falliscono: "Schema XSD not found"
```bash
# Verifica path schema
ls -la resources/invoices/schemas/fattura_pa_latest/
```

### ImportError durante test
```bash
# Reinstalla dipendenze
pip install -r requirements-test.txt
```

### Mypy errors
```bash
# Verifica type checking
mypy app/modules/invoices
```

### Performance degradation
```bash
# Profila i test
pytest --durations=10
```

## 📈 Statistiche Test

### Totale: **80 test**
- Unit tests: 55
- Integration tests: 15
- Scenario tests: 10

### Coverage attuale: **~95%**
- converter.py: 98%
- generator.py: 96%
- validator.py: 94%
- service.py: 92%

### Tempo esecuzione: **~2-3 secondi**
(senza test lenti)

## 🚦 CI/CD Integration

### GitHub Actions
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements-test.txt
      - run: pytest --cov=app
```

### Pre-commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/sh
pytest -x --tb=short
mypy app/modules/invoices
```

## 📚 Riferimenti

- [Pytest Documentation](https://docs.pytest.org/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [Test Fixtures Guide](https://docs.pytest.org/en/latest/fixture.html)
