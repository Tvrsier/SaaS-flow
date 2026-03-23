"""
Pytest configuration and fixtures
"""
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator

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
    ContactsPayload,
    InvoiceCreatePayload,
    InvoiceLinePayload,
    PartyPayload,
    PaymentPayload,
    StampDutyPayload,
)


@pytest.fixture
def project_root() -> Path:
    """Radice del progetto"""
    return Path(__file__).parent.parent


@pytest.fixture
def xsd_schema_path(project_root: Path) -> Path:
    """Path dello schema XSD FatturaPA"""
    return project_root / "resources" / "invoices" / "schemas" / "fattura_pa_latest" / "Schema_VFPR12_v1.2.3_local.xsd.xml"


@pytest.fixture
def test_output_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Directory temporanea per output test"""
    output_dir = tmp_path / "xml_output"
    output_dir.mkdir()
    yield output_dir


@pytest.fixture
def issuer_company() -> PartyPayload:
    """Cedente: azienda standard"""
    return PartyPayload(
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
        contacts=ContactsPayload(
            email="amministrazione@tavernatech.it",
            phone="0131000000",
            pec="tavernatech@pec.it",
        ),
    )


@pytest.fixture
def issuer_individual() -> PartyPayload:
    """Cedente: persona fisica professionista"""
    return PartyPayload(
        subject_type=SubjectType.INDIVIDUAL,
        first_name="Giuseppe",
        last_name="Verdi",
        vat_number="98765432109",
        tax_code="VRDGPP70A01F205X",
        fiscal_regime=FiscalRegime.RF01,
        address=AddressPayload(
            street="Corso Italia",
            street_number="50",
            zip_code="10121",
            city="Torino",
            province="TO",
            country="IT",
        ),
    )


@pytest.fixture
def issuer_forfettario() -> PartyPayload:
    """Cedente: regime forfettario"""
    return PartyPayload(
        subject_type=SubjectType.INDIVIDUAL,
        first_name="Marco",
        last_name="Bianchi",
        vat_number="11122233344",
        tax_code="BNCMRC85M15F205K",
        fiscal_regime=FiscalRegime.RF19,  # Regime forfettario
        address=AddressPayload(
            street="Via Garibaldi",
            street_number="123",
            zip_code="20121",
            city="Milano",
            province="MI",
            country="IT",
        ),
    )


@pytest.fixture
def customer_company() -> PartyPayload:
    """Cliente: azienda"""
    return PartyPayload(
        subject_type=SubjectType.COMPANY,
        company_name="Acme Corporation SRL",
        vat_number="55566677788",
        tax_code="55566677788",
        recipient_code="ABCDEFG",
        address=AddressPayload(
            street="Via Milano",
            street_number="100",
            zip_code="20100",
            city="Milano",
            province="MI",
            country="IT",
        ),
    )


@pytest.fixture
def customer_individual() -> PartyPayload:
    """Cliente: privato cittadino"""
    return PartyPayload(
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
    )


@pytest.fixture
def customer_foreign() -> PartyPayload:
    """Cliente: estero"""
    return PartyPayload(
        subject_type=SubjectType.COMPANY,
        company_name="Foreign Company Ltd",
        vat_number="GB123456789",
        tax_code="GB123456789",
        recipient_code="XXXXXXX",
        address=AddressPayload(
            street="Oxford Street",
            street_number="50",
            zip_code="00000",  # CAP fittizio per indirizzi esteri secondo schema FatturaPA
            city="London",
            province=None,
            country="GB",
        ),
    )


@pytest.fixture
def items_standard() -> list[InvoiceLinePayload]:
    """Righe fattura standard con IVA"""
    return [
        InvoiceLinePayload(
            line_number=1,
            type=LineType.PRODUCT,
            sku="PROD-001",
            name="Licenza software annuale",
            description="Licenza annuale piattaforma gestionale",
            quantity=Decimal("1.00"),
            unit_of_measure="NR",
            unit_price=Decimal("199.00"),
            discount_percent=Decimal("0.00"),
            vat_rate=Decimal("22.00"),
        ),
        InvoiceLinePayload(
            line_number=2,
            type=LineType.SERVICE,
            sku="SERV-001",
            name="Consulenza tecnica",
            description="Configurazione iniziale e formazione utente",
            quantity=Decimal("2.00"),
            unit_of_measure="H",
            unit_price=Decimal("50.00"),
            discount_percent=Decimal("10.00"),
            vat_rate=Decimal("22.00"),
        ),
    ]


@pytest.fixture
def items_with_exempt() -> list[InvoiceLinePayload]:
    """Righe con operazioni esenti/non imponibili"""
    return [
        InvoiceLinePayload(
            line_number=1,
            type=LineType.SERVICE,
            name="Servizio esente IVA",
            description="Servizio esente ex art.10",
            quantity=Decimal("1.00"),
            unit_of_measure="NR",
            unit_price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            vat_rate=Decimal("0.00"),
            nature=NatureCode.N4,  # Esente
        ),
        InvoiceLinePayload(
            line_number=2,
            type=LineType.SERVICE,
            name="Servizio non imponibile",
            description="Servizio con inversione contabile",
            quantity=Decimal("1.00"),
            unit_of_measure="NR",
            unit_price=Decimal("200.00"),
            discount_percent=Decimal("0.00"),
            vat_rate=Decimal("0.00"),
            nature=NatureCode.N6_9,  # Inversione contabile
        ),
    ]


@pytest.fixture
def items_mixed_vat() -> list[InvoiceLinePayload]:
    """Righe con aliquote IVA diverse"""
    return [
        InvoiceLinePayload(
            line_number=1,
            type=LineType.PRODUCT,
            name="Prodotto aliquota 22%",
            description="Prodotto standard",
            quantity=Decimal("2.00"),
            unit_of_measure="NR",
            unit_price=Decimal("100.00"),
            discount_percent=Decimal("0.00"),
            vat_rate=Decimal("22.00"),
        ),
        InvoiceLinePayload(
            line_number=2,
            type=LineType.PRODUCT,
            name="Prodotto aliquota 10%",
            description="Prodotto ridotta",
            quantity=Decimal("1.00"),
            unit_of_measure="NR",
            unit_price=Decimal("50.00"),
            discount_percent=Decimal("0.00"),
            vat_rate=Decimal("10.00"),
        ),
        InvoiceLinePayload(
            line_number=3,
            type=LineType.PRODUCT,
            name="Prodotto aliquota 4%",
            description="Prodotto super-ridotta",
            quantity=Decimal("3.00"),
            unit_of_measure="NR",
            unit_price=Decimal("25.00"),
            discount_percent=Decimal("0.00"),
            vat_rate=Decimal("4.00"),
        ),
    ]


@pytest.fixture
def payment_bank_transfer() -> PaymentPayload:
    """Pagamento: bonifico bancario"""
    return PaymentPayload(
        payment_terms=PaymentTerms.TP02,
        payment_method=PaymentMethod.MP05,
        due_date=date(2026, 4, 23),
        iban="IT60X0542811101000000123456",
        beneficiary="Taverna Tech SRLS",
    )


@pytest.fixture
def payment_cash() -> PaymentPayload:
    """Pagamento: contanti"""
    return PaymentPayload(
        payment_terms=PaymentTerms.TP02,
        payment_method=PaymentMethod.MP01,
        due_date=date(2026, 3, 23),
    )


@pytest.fixture
def payment_installments() -> PaymentPayload:
    """Pagamento: rate"""
    return PaymentPayload(
        payment_terms=PaymentTerms.TP01,
        payment_method=PaymentMethod.MP05,
        iban="IT60X0542811101000000123456",
        beneficiary="Taverna Tech SRLS",
    )


@pytest.fixture
def stamp_duty_enabled() -> StampDutyPayload:
    """Bollo: abilitato"""
    return StampDutyPayload(enabled=True, amount=Decimal("2.00"))


@pytest.fixture
def stamp_duty_disabled() -> StampDutyPayload:
    """Bollo: disabilitato"""
    return StampDutyPayload(enabled=False)


@pytest.fixture
def invoice_standard(
    issuer_company: PartyPayload,
    customer_company: PartyPayload,
    items_standard: list[InvoiceLinePayload],
    payment_bank_transfer: PaymentPayload,
    stamp_duty_disabled: StampDutyPayload,
) -> InvoiceCreatePayload:
    """Fattura standard B2B"""
    return InvoiceCreatePayload(
        invoice_number="FE-2026-000001",
        invoice_date=date(2026, 3, 23),
        currency="EUR",
        language="it",
        document_type=DocumentType.TD01,
        issuer=issuer_company,
        customer=customer_company,
        items=items_standard,
        payment=payment_bank_transfer,
        stamp_duty=stamp_duty_disabled,
        causal=["Vendita prodotti e servizi"],
        notes=["Grazie per la preferenza"],
    )


@pytest.fixture
def invoice_b2c(
    issuer_company: PartyPayload,
    customer_individual: PartyPayload,
    items_standard: list[InvoiceLinePayload],
    payment_bank_transfer: PaymentPayload,
    stamp_duty_disabled: StampDutyPayload,
) -> InvoiceCreatePayload:
    """Fattura B2C (a privato)"""
    return InvoiceCreatePayload(
        invoice_number="FE-2026-000002",
        invoice_date=date(2026, 3, 23),
        currency="EUR",
        language="it",
        document_type=DocumentType.TD01,
        issuer=issuer_company,
        customer=customer_individual,
        items=items_standard,
        payment=payment_bank_transfer,
        stamp_duty=stamp_duty_disabled,
        causal=["Vendita prodotti"],
    )
