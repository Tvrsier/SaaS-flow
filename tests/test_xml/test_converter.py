"""
Test per FatturaPAConverter
"""
import pytest
from decimal import Decimal

from app.modules.invoices.domain.enums import (
    FormatoTrasmissione,
    SubjectType,
    TipoDocumento,
)
from app.modules.invoices.schemas.request import InvoiceCreatePayload
from app.modules.invoices.xml.converter import FatturaPAConverter
from app.modules.invoices.xml.models import (
    FatturaElettronica,
    Anagrafica,
)


class TestFatturaPAConverter:
    """Test per conversione da InvoiceCreatePayload a FatturaElettronica"""

    @pytest.fixture
    def converter(self) -> FatturaPAConverter:
        return FatturaPAConverter()

    def test_convert_standard_invoice(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test conversione fattura standard"""
        result = converter.convert(invoice_standard)

        assert isinstance(result, FatturaElettronica)
        assert result.versione == FormatoTrasmissione.FPR12.value
        assert len(result.FatturaElettronicaBody) == 1

    def test_header_dati_trasmissione(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test dati trasmissione nell'header"""
        result = converter.convert(invoice_standard)
        header = result.FatturaElettronicaHeader

        # Verifica dati trasmissione
        assert header.DatiTrasmissione.IdTrasmittente.IdPaese == "IT"
        assert header.DatiTrasmissione.IdTrasmittente.IdCodice == "12345678901"
        assert header.DatiTrasmissione.FormatoTrasmissione == FormatoTrasmissione.FPR12
        assert header.DatiTrasmissione.CodiceDestinatario == "ABCDEFG"
        assert len(header.DatiTrasmissione.ProgressivoInvio) == 10

    def test_header_cedente_company(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test cedente persona giuridica"""
        result = converter.convert(invoice_standard)
        cedente = result.FatturaElettronicaHeader.CedentePrestatore

        # Verifica dati anagrafici
        assert cedente.DatiAnagrafici.IdFiscaleIVA.IdPaese == "IT"
        assert cedente.DatiAnagrafici.IdFiscaleIVA.IdCodice == "12345678901"
        assert cedente.DatiAnagrafici.Anagrafica.Denominazione == "Taverna Tech SRLS"
        assert cedente.DatiAnagrafici.Anagrafica.Nome is None
        assert cedente.DatiAnagrafici.Anagrafica.Cognome is None

        # Verifica sede
        assert cedente.Sede.Indirizzo == "Via Roma"
        assert cedente.Sede.NumeroCivico == "10"
        assert cedente.Sede.CAP == "15121"
        assert cedente.Sede.Comune == "Alessandria"
        assert cedente.Sede.Provincia == "AL"
        assert cedente.Sede.Nazione == "IT"

    def test_header_cedente_individual(
        self,
        converter: FatturaPAConverter,
        issuer_individual,
        customer_company,
        items_standard,
        payment_bank_transfer,
        stamp_duty_disabled,
    ):
        """Test cedente persona fisica"""
        invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-000010",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=TipoDocumento.TD01,
            issuer=issuer_individual,
            customer=customer_company,
            items=items_standard,
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_disabled,
            causal=["Test"],
        )

        result = converter.convert(invoice)
        anagrafica = result.FatturaElettronicaHeader.CedentePrestatore.DatiAnagrafici.Anagrafica

        assert anagrafica.Denominazione is None
        assert anagrafica.Nome == "Giuseppe"
        assert anagrafica.Cognome == "Verdi"

    def test_header_cessionario_company(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test cessionario persona giuridica"""
        result = converter.convert(invoice_standard)
        cessionario = result.FatturaElettronicaHeader.CessionarioCommittente

        # Verifica dati anagrafici
        assert cessionario.DatiAnagrafici.IdFiscaleIVA.IdPaese == "IT"
        assert cessionario.DatiAnagrafici.IdFiscaleIVA.IdCodice == "55566677788"
        assert cessionario.DatiAnagrafici.CodiceFiscale == "55566677788"
        assert cessionario.DatiAnagrafici.Anagrafica.Denominazione == "Acme Corporation SRL"

    def test_header_cessionario_individual(
        self, converter: FatturaPAConverter, invoice_b2c: InvoiceCreatePayload
    ):
        """Test cessionario persona fisica"""
        result = converter.convert(invoice_b2c)
        cessionario = result.FatturaElettronicaHeader.CessionarioCommittente

        # Verifica anagrafica persona fisica
        anagrafica = cessionario.DatiAnagrafici.Anagrafica
        assert anagrafica.Denominazione is None
        assert anagrafica.Nome == "Mario"
        assert anagrafica.Cognome == "Rossi"

        # Cliente privato può non avere P.IVA
        assert cessionario.DatiAnagrafici.IdFiscaleIVA is None
        assert cessionario.DatiAnagrafici.CodiceFiscale == "RSSMRA80A01F205X"

    def test_body_dati_generali(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test dati generali documento"""
        result = converter.convert(invoice_standard)
        doc = result.FatturaElettronicaBody[0].DatiGenerali.DatiGeneraliDocumento

        assert doc.TipoDocumento == TipoDocumento.TD01
        assert doc.Divisa == "EUR"
        assert doc.Data == "2026-03-23"
        assert doc.Numero == "FE-2026-000001"
        assert doc.Causale == ["Vendita prodotti e servizi"]
        assert doc.ImportoTotaleDocumento is not None

    def test_body_dati_bollo(
        self,
        converter: FatturaPAConverter,
        issuer_company,
        customer_company,
        items_standard,
        payment_bank_transfer,
        stamp_duty_enabled,
    ):
        """Test dati bollo quando abilitato"""
        invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-000011",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=TipoDocumento.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=items_standard,
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_enabled,
            causal=["Test bollo"],
        )

        result = converter.convert(invoice)
        doc = result.FatturaElettronicaBody[0].DatiGenerali.DatiGeneraliDocumento

        assert doc.DatiBollo is not None
        assert doc.DatiBollo.BolloVirtuale == "SI"
        assert doc.DatiBollo.ImportoBollo == Decimal("2.00")

    def test_body_dettaglio_linee(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test dettaglio linee fattura"""
        result = converter.convert(invoice_standard)
        linee = result.FatturaElettronicaBody[0].DatiBeniServizi.DettaglioLinee

        assert len(linee) == 2

        # Prima linea
        linea1 = linee[0]
        assert linea1.NumeroLinea == 1
        assert linea1.Descrizione == "Licenza annuale piattaforma gestionale"
        assert linea1.Quantita == Decimal("1.00")
        assert linea1.UnitaMisura == "NR"
        assert linea1.PrezzoUnitario == Decimal("199.00")
        assert linea1.AliquotaIVA == Decimal("22.00")
        assert linea1.Natura is None

        # Seconda linea con sconto
        linea2 = linee[1]
        assert linea2.NumeroLinea == 2
        assert len(linea2.ScontoMaggiorazione) == 1
        assert linea2.ScontoMaggiorazione[0].Percentuale == Decimal("10.00")

    def test_body_codice_articolo(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test presenza codice articolo (SKU)"""
        result = converter.convert(invoice_standard)
        linee = result.FatturaElettronicaBody[0].DatiBeniServizi.DettaglioLinee

        # Prima linea ha SKU
        assert len(linee[0].CodiceArticolo) == 1
        assert linee[0].CodiceArticolo[0].CodiceTipo == "SKU"
        assert linee[0].CodiceArticolo[0].CodiceValore == "PROD-001"

    def test_body_dati_riepilogo_single_vat(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test riepilogo IVA con aliquota singola"""
        result = converter.convert(invoice_standard)
        riepilogo = result.FatturaElettronicaBody[0].DatiBeniServizi.DatiRiepilogo

        # Entrambe le righe hanno IVA 22%, quindi un solo riepilogo
        assert len(riepilogo) == 1
        assert riepilogo[0].AliquotaIVA == Decimal("22.00")
        assert riepilogo[0].Natura is None

    def test_body_dati_riepilogo_multiple_vat(
        self,
        converter: FatturaPAConverter,
        issuer_company,
        customer_company,
        items_mixed_vat,
        payment_bank_transfer,
        stamp_duty_disabled,
    ):
        """Test riepilogo IVA con aliquote multiple"""
        invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-000012",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=TipoDocumento.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=items_mixed_vat,
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_disabled,
            causal=["Test aliquote multiple"],
        )

        result = converter.convert(invoice)
        riepilogo = result.FatturaElettronicaBody[0].DatiBeniServizi.DatiRiepilogo

        # Tre aliquote diverse: 4%, 10%, 22%
        assert len(riepilogo) == 3

        # Verifica ordine crescente
        aliquote = [r.AliquotaIVA for r in riepilogo]
        assert aliquote == [Decimal("4.00"), Decimal("10.00"), Decimal("22.00")]

    def test_body_dati_riepilogo_with_nature(
        self,
        converter: FatturaPAConverter,
        issuer_company,
        customer_company,
        items_with_exempt,
        payment_bank_transfer,
        stamp_duty_disabled,
    ):
        """Test riepilogo con natura operazioni"""
        invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-000013",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=TipoDocumento.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=items_with_exempt,
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_disabled,
            causal=["Operazioni esenti"],
        )

        result = converter.convert(invoice)
        riepilogo = result.FatturaElettronicaBody[0].DatiBeniServizi.DatiRiepilogo

        # Due nature diverse: N4, N6.9
        assert len(riepilogo) == 2

        for r in riepilogo:
            assert r.AliquotaIVA == Decimal("0.00")
            assert r.Natura is not None

    def test_body_dati_pagamento(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test dati pagamento"""
        result = converter.convert(invoice_standard)
        pagamento = result.FatturaElettronicaBody[0].DatiPagamento

        assert len(pagamento) == 1
        assert pagamento[0].DettaglioPagamento[0].IBAN == "IT60X0542811101000000123456"
        assert pagamento[0].DettaglioPagamento[0].Beneficiario == "Taverna Tech SRLS"
        assert pagamento[0].DettaglioPagamento[0].DataScadenzaPagamento == "2026-04-23"

    def test_calcolo_totali_automatico(
        self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload
    ):
        """Test calcolo automatico totali"""
        result = converter.convert(invoice_standard)
        doc = result.FatturaElettronicaBody[0].DatiGenerali.DatiGeneraliDocumento

        # Verifica che ImportoTotaleDocumento sia calcolato
        assert doc.ImportoTotaleDocumento is not None
        assert doc.ImportoTotaleDocumento > Decimal("0")

    def test_progressive_id_uniqueness(self, converter: FatturaPAConverter, invoice_standard: InvoiceCreatePayload):
        """Test unicità ProgressivoInvio"""
        result1 = converter.convert(invoice_standard)
        result2 = converter.convert(invoice_standard)

        # Ogni conversione genera un ProgressivoInvio diverso
        prog1 = result1.FatturaElettronicaHeader.DatiTrasmissione.ProgressivoInvio
        prog2 = result2.FatturaElettronicaHeader.DatiTrasmissione.ProgressivoInvio

        assert prog1 != prog2
        assert len(prog1) <= 10
        assert len(prog2) <= 10
