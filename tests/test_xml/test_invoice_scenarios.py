"""
Test per diverse tipologie di fatture e scenari reali
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.modules.invoices.domain.enums import (
    DocumentType,
    FiscalRegime,
    LineType,
    NatureCode,
    PaymentMethod,
    PaymentTerms,
    SubjectType,
)
from app.modules.invoices.schemas.request import (
    AddressPayload,
    InvoiceCreatePayload,
    InvoiceLinePayload,
    PartyPayload,
    PaymentPayload,
    StampDutyPayload,
)
from app.modules.invoices.xml import FatturaPAService, create_local_validator


class TestInvoiceScenarios:
    """Test scenari realistici di fatturazione"""

    @pytest.fixture
    def service(self) -> FatturaPAService:
        return FatturaPAService()

    @pytest.fixture
    def validator_path(self, xsd_schema_path: Path):
        return xsd_schema_path

    def test_scenario_software_saas_subscription(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_company,
        payment_bank_transfer,
    ):
        """Scenario: abbonamento SaaS annuale"""
        invoice = InvoiceCreatePayload(
            invoice_number="2026-0001",
            invoice_date=date(2026, 3, 1),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.SERVICE,
                    name="Abbonamento annuale SaaS",
                    description="Licenza software gestionale - Piano Premium 2026",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("999.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
            ],
            payment=payment_bank_transfer,
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Abbonamento annuale piattaforma gestionale"],
            notes=["Pagamento anticipato per l'intero anno"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_consulting_services_with_discount(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_individual,
        customer_company,
        payment_bank_transfer,
    ):
        """Scenario: consulenza professionale con sconto"""
        invoice = InvoiceCreatePayload(
            invoice_number="CONS-2026-042",
            invoice_date=date(2026, 3, 15),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD06,  # Parcella
            issuer=issuer_individual,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.SERVICE,
                    name="Consulenza strategica",
                    description="Analisi e consulenza per ottimizzazione processi aziendali",
                    quantity=Decimal("10.00"),
                    unit_of_measure="H",
                    unit_price=Decimal("120.00"),
                    discount_percent=Decimal("15.00"),  # Sconto 15%
                    vat_rate=Decimal("22.00"),
                ),
                InvoiceLinePayload(
                    line_number=2,
                    type=LineType.SERVICE,
                    name="Stesura documentazione",
                    description="Redazione report conclusivo e raccomandazioni",
                    quantity=Decimal("4.00"),
                    unit_of_measure="H",
                    unit_price=Decimal("80.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
            ],
            payment=payment_bank_transfer,
            stamp_duty=StampDutyPayload(enabled=True, amount=Decimal("2.00")),
            causal=["Parcella professionale consulenza marzo 2026"],
            notes=["Sconto applicato come da accordi"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_mixed_products_services(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_company,
        payment_bank_transfer,
    ):
        """Scenario: mix prodotti e servizi"""
        invoice = InvoiceCreatePayload(
            invoice_number="2026-0042",
            invoice_date=date(2026, 3, 20),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.PRODUCT,
                    sku="HW-SERVER-001",
                    name="Server dedicato",
                    description="Server Dell PowerEdge R450",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("2500.00"),
                    discount_percent=Decimal("10.00"),
                    vat_rate=Decimal("22.00"),
                ),
                InvoiceLinePayload(
                    line_number=2,
                    type=LineType.SERVICE,
                    name="Installazione e configurazione",
                    description="Setup sistema operativo e applicativi",
                    quantity=Decimal("8.00"),
                    unit_of_measure="H",
                    unit_price=Decimal("80.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
                InvoiceLinePayload(
                    line_number=3,
                    type=LineType.SERVICE,
                    name="Formazione personale",
                    description="Training amministratori di sistema",
                    quantity=Decimal("4.00"),
                    unit_of_measure="H",
                    unit_price=Decimal("100.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
            ],
            payment=payment_bank_transfer,
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Vendita hardware e servizi correlati"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_exempt_operations(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_foreign,
        payment_bank_transfer,
    ):
        """Scenario: operazioni non imponibili (export)"""
        invoice = InvoiceCreatePayload(
            invoice_number="EXP-2026-001",
            invoice_date=date(2026, 3, 25),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_foreign,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.SERVICE,
                    name="Servizi IT esportazione",
                    description="Servizi informatici prestati a soggetto extra-UE",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("5000.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("0.00"),
                    nature=NatureCode.N3_1,  # Non imponibile - esportazione
                ),
            ],
            payment=payment_bank_transfer,
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Prestazione servizi extra-UE"],
            notes=["Operazione non imponibile art. 7-ter DPR 633/72"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_forfettario_regime(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_forfettario,
        customer_company,
    ):
        """Scenario: fattura regime forfettario"""
        invoice = InvoiceCreatePayload(
            invoice_number="FORF-2026-010",
            invoice_date=date(2026, 3, 10),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_forfettario,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.SERVICE,
                    name="Servizi professionali",
                    description="Consulenza e supporto tecnico",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("800.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("0.00"),
                    nature=NatureCode.N2_2,  # Non soggette - regime forfettario
                ),
            ],
            payment=PaymentPayload(
                payment_terms=PaymentTerms.TP02,
                payment_method=PaymentMethod.MP05,
                due_date=date(2026, 4, 10),
                iban="IT60X0542811101000000999888",
                beneficiary="Marco Bianchi",
            ),
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Prestazione servizi regime forfettario"],
            notes=["Operazione effettuata ai sensi dell'art.1 c.54-89 L.190/2014"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_credit_note(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_company,
        payment_bank_transfer,
    ):
        """Scenario: nota di credito"""
        invoice = InvoiceCreatePayload(
            invoice_number="NC-2026-005",
            invoice_date=date(2026, 3, 28),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD04,  # Nota di credito
            issuer=issuer_company,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.PRODUCT,
                    name="Storno prodotto difettoso",
                    description="Restituzione articolo non conforme",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("-299.00"),  # Prezzo negativo per nota credito
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
            ],
            payment=payment_bank_transfer,
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Nota di credito per reso merce"],
            notes=["Riferimento fattura originale: 2026-0035 del 15/03/2026"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_b2c_retail(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_individual,
    ):
        """Scenario: vendita al dettaglio B2C"""
        invoice = InvoiceCreatePayload(
            invoice_number="RET-2026-1234",
            invoice_date=date(2026, 3, 18),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_individual,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.PRODUCT,
                    sku="LAPTOP-PRO-001",
                    name="Laptop professionale",
                    description="Computer portatile 15 pollici",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("1299.00"),
                    discount_percent=Decimal("5.00"),  # Sconto promozionale
                    vat_rate=Decimal("22.00"),
                ),
                InvoiceLinePayload(
                    line_number=2,
                    type=LineType.PRODUCT,
                    sku="ACC-MOUSE-001",
                    name="Mouse wireless",
                    description="Mouse ottico senza fili",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("29.90"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
            ],
            payment=PaymentPayload(
                payment_terms=PaymentTerms.TP02,
                payment_method=PaymentMethod.MP08,  # Carta di pagamento
                due_date=date(2026, 3, 18),  # Pagamento contestuale
            ),
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Vendita al dettaglio"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_multiple_vat_rates(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_company,
        payment_bank_transfer,
    ):
        """Scenario: fattura con aliquote IVA multiple"""
        invoice = InvoiceCreatePayload(
            invoice_number="2026-0088",
            invoice_date=date(2026, 3, 22),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.PRODUCT,
                    name="Bene con IVA ordinaria",
                    description="Prodotto standard",
                    quantity=Decimal("5.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("100.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),  # IVA 22%
                ),
                InvoiceLinePayload(
                    line_number=2,
                    type=LineType.PRODUCT,
                    name="Bene con IVA ridotta",
                    description="Prodotto aliquota ridotta",
                    quantity=Decimal("10.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("50.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("10.00"),  # IVA 10%
                ),
                InvoiceLinePayload(
                    line_number=3,
                    type=LineType.PRODUCT,
                    name="Bene con IVA minima",
                    description="Prodotto aliquota minima",
                    quantity=Decimal("20.00"),
                    unit_of_measure="KG",
                    unit_price=Decimal("15.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("4.00"),  # IVA 4%
                ),
            ],
            payment=payment_bank_transfer,
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Vendita beni con aliquote miste"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_installment_payment(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_company,
    ):
        """Scenario: pagamento rateale"""
        invoice = InvoiceCreatePayload(
            invoice_number="2026-RATE-001",
            invoice_date=date(2026, 3, 1),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.SERVICE,
                    name="Progetto sviluppo software",
                    description="Realizzazione applicazione custom",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("12000.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
            ],
            payment=PaymentPayload(
                payment_terms=PaymentTerms.TP01,  # Pagamento a rate
                payment_method=PaymentMethod.MP05,
                iban="IT60X0542811101000000123456",
                beneficiary="Taverna Tech SRLS",
            ),
            stamp_duty=StampDutyPayload(enabled=False),
            causal=["Progetto sviluppo software custom"],
            notes=[
                "Pagamento in 3 rate:",
                "- 30% alla firma (€4.880,00)",
                "- 40% a metà progetto (€6.506,67)",
                "- 30% a consegna (€4.880,00)",
            ],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()

    def test_scenario_high_value_invoice(
        self,
        service: FatturaPAService,
        validator_path: Path,
        issuer_company,
        customer_company,
        payment_bank_transfer,
    ):
        """Scenario: fattura di importo elevato con bollo"""
        invoice = InvoiceCreatePayload(
            invoice_number="2026-HIGH-001",
            invoice_date=date(2026, 3, 30),
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=[
                InvoiceLinePayload(
                    line_number=1,
                    type=LineType.SERVICE,
                    name="Licenza enterprise multi-year",
                    description="Licenza software enterprise 3 anni - 100 utenti",
                    quantity=Decimal("1.00"),
                    unit_of_measure="NR",
                    unit_price=Decimal("45000.00"),
                    discount_percent=Decimal("12.00"),  # Sconto volume
                    vat_rate=Decimal("22.00"),
                ),
                InvoiceLinePayload(
                    line_number=2,
                    type=LineType.SERVICE,
                    name="Supporto premium",
                    description="Assistenza 24/7 e formazione inclusa",
                    quantity=Decimal("36.00"),
                    unit_of_measure="MESE",
                    unit_price=Decimal("500.00"),
                    discount_percent=Decimal("0.00"),
                    vat_rate=Decimal("22.00"),
                ),
            ],
            payment=payment_bank_transfer,
            stamp_duty=StampDutyPayload(enabled=True, amount=Decimal("2.00")),
            causal=["Contratto enterprise multi-year"],
            notes=["Pagamento entro 60 giorni data fattura"],
        )

        result = service.generate_xml(invoice)
        assert result.success

        validator = create_local_validator(validator_path)
        validation = validator.validate_xml_string(result.xml_content)
        assert validation.is_valid, validation.get_error_summary()