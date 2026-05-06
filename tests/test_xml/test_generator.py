"""
Test per FatturaPAXMLGenerator
"""
import pytest
from lxml import etree

from app.modules.invoices.schemas.request import InvoiceCreatePayload
from app.modules.invoices.xml.converter import FatturaPAConverter
from app.modules.invoices.xml.generator import FatturaPAXMLGenerator
from app.modules.invoices.xml.constants import XMLNamespace, XMLTag


class TestFatturaPAXMLGenerator:
    """Test per generazione XML FatturaPA"""

    @pytest.fixture
    def generator(self) -> FatturaPAXMLGenerator:
        return FatturaPAXMLGenerator()

    @pytest.fixture
    def converter(self) -> FatturaPAConverter:
        return FatturaPAConverter()

    def test_generate_xml_returns_string(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test che generate_xml ritorna una stringa"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        assert isinstance(xml, str)
        assert len(xml) > 0
        assert xml.startswith('<?xml')

    def test_xml_well_formed(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test che l'XML sia ben formato"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        # Parse XML per verificare che sia ben formato
        try:
            etree.fromstring(xml.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            pytest.fail(f"XML malformato: {e}")

    def test_xml_has_correct_root(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test elemento root corretto"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))

        # Verifica tag root
        expected_tag = f"{{{XMLNamespace.FATTURA_PA.value}}}FatturaElettronica"
        assert root.tag == expected_tag

        # Verifica attributo versione
        assert root.get('versione') == 'FPR12'

    def test_xml_has_correct_namespace(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test namespace corretto"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))

        # Verifica namespace
        nsmap = root.nsmap
        assert None in nsmap
        assert nsmap[None] == XMLNamespace.FATTURA_PA.value

    def test_xml_structure_header(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test struttura header XML"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        # Verifica presenza header
        header = root.find('p:FatturaElettronicaHeader', ns)
        assert header is not None

        # Verifica sottoelementi header
        assert header.find('p:DatiTrasmissione', ns) is not None
        assert header.find('p:CedentePrestatore', ns) is not None
        assert header.find('p:CessionarioCommittente', ns) is not None

    def test_xml_structure_body(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test struttura body XML"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        # Verifica presenza body
        body = root.find('p:FatturaElettronicaBody', ns)
        assert body is not None

        # Verifica sottoelementi body
        assert body.find('p:DatiGenerali', ns) is not None
        assert body.find('p:DatiBeniServizi', ns) is not None
        assert body.find('p:DatiPagamento', ns) is not None

    def test_xml_dati_trasmissione(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test dati trasmissione nel XML"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        dt = root.find('.//p:DatiTrasmissione', ns)
        assert dt is not None

        # Verifica IdTrasmittente
        id_paese = dt.find('.//p:IdPaese', ns)
        assert id_paese is not None
        assert id_paese.text == "IT"

        # Verifica CodiceDestinatario
        cod_dest = dt.find('.//p:CodiceDestinatario', ns)
        assert cod_dest is not None
        assert cod_dest.text == "ABCDEFG"

    def test_xml_cedente_company(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test cedente azienda nel XML"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        anagrafica = root.find('.//p:CedentePrestatore//p:Anagrafica', ns)
        assert anagrafica is not None

        # Persona giuridica: ha Denominazione
        denominazione = anagrafica.find('p:Denominazione', ns)
        assert denominazione is not None
        assert denominazione.text == "Taverna Tech SRLS"

        # Non ha Nome/Cognome
        assert anagrafica.find('p:Nome', ns) is None
        assert anagrafica.find('p:Cognome', ns) is None

    def test_xml_dettaglio_linee(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test dettaglio linee nel XML"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        linee = root.findall('.//p:DettaglioLinee', ns)
        assert len(linee) == 2

        # Prima linea
        linea1 = linee[0]
        numero_linea = linea1.find('p:NumeroLinea', ns)
        assert numero_linea is not None
        assert numero_linea.text == "1"

        descrizione = linea1.find('p:Descrizione', ns)
        assert descrizione is not None
        assert "Licenza annuale" in descrizione.text

    def test_xml_dati_riepilogo(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test dati riepilogo IVA nel XML"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        riepilogo = root.findall('.//p:DatiRiepilogo', ns)
        assert len(riepilogo) > 0

        # Verifica presenza campi obbligatori
        for r in riepilogo:
            assert r.find('p:AliquotaIVA', ns) is not None
            assert r.find('p:ImponibileImporto', ns) is not None
            assert r.find('p:Imposta', ns) is not None

    def test_xml_decimal_formatting_standard(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test formattazione decimali standard (2 cifre)"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        # AliquotaIVA deve avere 2 decimali
        aliquota = root.find('.//p:AliquotaIVA', ns)
        assert aliquota is not None
        assert '.' in aliquota.text
        decimals = aliquota.text.split('.')[1]
        assert len(decimals) == 2

    def test_xml_decimal_formatting_extended(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test formattazione decimali estesa (8 cifre)"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        # PrezzoUnitario deve avere fino a 8 decimali
        prezzo = root.find('.//p:PrezzoUnitario', ns)
        assert prezzo is not None
        assert '.' in prezzo.text
        decimals = prezzo.text.split('.')[1]
        assert len(decimals) == 8

    def test_pretty_print_enabled(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test formattazione pretty print"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura, pretty_print=True)

        # Con pretty print ci sono indentazioni
        assert '\n  ' in xml or '\n    ' in xml

    def test_pretty_print_disabled(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test senza formattazione pretty print"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura, pretty_print=False)

        # Senza pretty print è più compatto (meno newline)
        lines = xml.split('\n')
        # Con pretty_print=False ci sono molte meno righe
        assert len(lines) < 100  # Molto compatto

    def test_xml_contains_bollo_when_enabled(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        issuer_company,
        customer_company,
        items_standard,
        payment_bank_transfer,
        stamp_duty_enabled,
    ):
        """Test presenza bollo nel XML quando abilitato"""
        from app.modules.invoices.schemas.request import InvoiceCreatePayload
        from app.modules.invoices.domain.enums import DocumentType

        invoice = InvoiceCreatePayload(
            invoice_number="FE-2026-000020",
            invoice_date="2026-03-23",
            currency="EUR",
            language="it",
            document_type=DocumentType.TD01,
            issuer=issuer_company,
            customer=customer_company,
            items=items_standard,
            payment=payment_bank_transfer,
            stamp_duty=stamp_duty_enabled,
            causal=["Test bollo"],
        )

        fattura = converter.convert(invoice)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        # Verifica presenza DatiBollo
        bollo = root.find('.//p:DatiBollo', ns)
        assert bollo is not None

        bollo_virtuale = bollo.find('p:BolloVirtuale', ns)
        assert bollo_virtuale is not None
        assert bollo_virtuale.text == "SI"

        importo_bollo = bollo.find('p:ImportoBollo', ns)
        assert importo_bollo is not None
        assert importo_bollo.text == "2.00"

    def test_xml_no_bollo_when_disabled(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test assenza bollo nel XML quando disabilitato"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        root = etree.fromstring(xml.encode('utf-8'))
        ns = {'p': XMLNamespace.FATTURA_PA.value}

        # DatiBollo non deve essere presente
        bollo = root.find('.//p:DatiBollo', ns)
        assert bollo is None

    def test_xml_encoding_utf8(
        self,
        generator: FatturaPAXMLGenerator,
        converter: FatturaPAConverter,
        invoice_standard: InvoiceCreatePayload,
    ):
        """Test encoding UTF-8 nell'XML"""
        fattura = converter.convert(invoice_standard)
        xml = generator.generate_xml(fattura)

        # Verifica dichiarazione XML con encoding
        assert 'encoding="UTF-8"' in xml

        # Verifica che caratteri speciali siano gestiti
        assert 'Taverna Tech' in xml  # Contiene caratteri normali
