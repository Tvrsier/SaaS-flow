"""
Generatore XML per FatturaPA secondo schema VFPR12 v1.2.3
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from app.logger import logger

if TYPE_CHECKING:
    try:
        from mypy_boto3_s3.client import S3Client
    except ImportError:
        S3Client = object  # type: ignore[misc,assignment]

from app.modules.invoices.xml.models import (
    FatturaElettronica,
    FatturaElettronicaHeader,
    FatturaElettronicaBody,
    DatiTrasmissione,
    CedentePrestatore,
    CessionarioCommittente,
    DatiGenerali,
    DatiBeniServizi,
    DatiPagamento,
    DettaglioLinee,
    DatiRiepilogo,
    DettaglioPagamento,
    DatiBollo,
    Sede,
    StabileOrganizzazione,
    Anagrafica,
    Contatti,
    IdFiscaleIVA,
    DatiAnagraficiCedente,
    DatiAnagraficiCommittente,
    CodiceArticolo,
    ScontoMaggiorazioneDettaglio,
)
from app.modules.invoices.xml.constants import (
    XMLNamespace,
    XMLSchemaLocation,
    XMLTag,
    XMLAttribute,
    XMLDeclaration,
    DecimalPrecision,
)


class FatturaPAXMLGenerator:
    """Genera XML FatturaPA secondo schema v1.2.3"""

    def __init__(self):
        self.namespace = XMLNamespace.FATTURA_PA.value
        self.namespace_xsi = XMLNamespace.XSI.value
        self.schema_location = XMLSchemaLocation.FATTURA_PA

    def generate_xml(self, fattura: FatturaElettronica, pretty_print: bool = True) -> str:
        """
        Genera XML dalla struttura FatturaElettronica

        Args:
            fattura: Struttura dati della fattura
            pretty_print: Se True, formatta l'XML con indentazione

        Returns:
            Stringa XML
        """
        logger.debug(f"Generating XML for invoice {self._get_filename(fattura)}")

        # Registra il namespace di default
        from xml.etree.ElementTree import register_namespace
        register_namespace("", self.namespace)
        register_namespace("xsi", self.namespace_xsi)

        # Crea elemento root con namespace di default
        root = Element(
            f"{{{self.namespace}}}{XMLTag.FATTURA_ELETTRONICA.value}",
            attrib={
                XMLAttribute.VERSIONE.value: fattura.versione,
                f"{{{self.namespace_xsi}}}{XMLAttribute.SCHEMA_LOCATION.value}": self.schema_location,
            },
        )

        # Aggiungi header
        self._add_header(root, fattura.FatturaElettronicaHeader)

        # Aggiungi body (può essere multiplo)
        for body in fattura.FatturaElettronicaBody:
            self._add_body(root, body)

        # Converti in stringa
        xml_str = tostring(root, encoding="unicode", method="xml")

        # Pretty print se richiesto
        if pretty_print:
            dom = minidom.parseString(xml_str)
            # toprettyxml aggiunge dichiarazione con encoding, la rimuoviamo e aggiungiamo la nostra
            xml_str = dom.toprettyxml(indent="  ", encoding=None)
            # Rimuovi righe vuote extra
            xml_str = "\n".join([line for line in xml_str.split("\n") if line.strip()])
            # Rimuovi dichiarazione XML generata da minidom se presente
            if xml_str.startswith("<?xml"):
                xml_str = xml_str.split("?>", 1)[1].lstrip()

        # Aggiungi dichiarazione XML con encoding standard
        xml_str = f'<?xml version="{XMLDeclaration.VERSION}" encoding="{XMLDeclaration.ENCODING}"?>\n' + xml_str

        logger.debug(f"XML generated successfully, size: {len(xml_str)} bytes")
        return xml_str

    def _add_header(self, parent: Element, header: FatturaElettronicaHeader) -> None:
        """Aggiunge FatturaElettronicaHeader all'XML"""
        header_elem = SubElement(parent, self._ns_tag(XMLTag.FATTURA_ELETTRONICA_HEADER))

        # 1.1 Dati trasmissione
        self._add_dati_trasmissione(header_elem, header.DatiTrasmissione)

        # 1.2 Cedente/Prestatore
        self._add_cedente_prestatore(header_elem, header.CedentePrestatore)

        # 1.3 Rappresentante fiscale (opzionale)
        if header.RappresentanteFiscale:
            self._add_rappresentante_fiscale(header_elem, header.RappresentanteFiscale)

        # 1.4 Cessionario/Committente
        if header.CessionarioCommittente:
            self._add_cessionario_committente(header_elem, header.CessionarioCommittente)

        # 1.5 Terzo intermediario (opzionale)
        if header.TerzoIntermediarioOSoggettoEmittente:
            # TODO: implementare se necessario
            pass

        # 1.6 Soggetto emittente (opzionale)
        if header.SoggettoEmittente:
            self._add_element(header_elem, XMLTag.SOGGETTO_EMITTENTE, header.SoggettoEmittente)

    def _add_dati_trasmissione(self, parent: Element, dati: DatiTrasmissione) -> None:
        """Aggiunge DatiTrasmissione (1.1)"""
        dt_elem = SubElement(parent, self._ns_tag(XMLTag.DATI_TRASMISSIONE))

        # 1.1.1 IdTrasmittente
        id_trasmittente = SubElement(dt_elem, self._ns_tag(XMLTag.ID_TRASMITTENTE))
        self._add_element(id_trasmittente, XMLTag.ID_PAESE, dati.IdTrasmittente.IdPaese)
        self._add_element(id_trasmittente, XMLTag.ID_CODICE, dati.IdTrasmittente.IdCodice)

        # 1.1.2 ProgressivoInvio
        self._add_element(dt_elem, XMLTag.PROGRESSIVO_INVIO, dati.ProgressivoInvio)

        # 1.1.3 FormatoTrasmissione
        self._add_element(dt_elem, XMLTag.FORMATO_TRASMISSIONE, dati.FormatoTrasmissione.value)

        # 1.1.4 CodiceDestinatario
        self._add_element(dt_elem, XMLTag.CODICE_DESTINATARIO, dati.CodiceDestinatario)

        # 1.1.5 ContattiTrasmittente (opzionale)
        if dati.ContattiTrasmittente:
            contatti_elem = SubElement(dt_elem, self._ns_tag(XMLTag.CONTATTI_TRASMITTENTE))
            if dati.ContattiTrasmittente.Telefono:
                self._add_element(contatti_elem, XMLTag.TELEFONO, dati.ContattiTrasmittente.Telefono)
            if dati.ContattiTrasmittente.Email:
                self._add_element(contatti_elem, XMLTag.EMAIL, dati.ContattiTrasmittente.Email)

        # 1.1.6 PECDestinatario (opzionale)
        if dati.PECDestinatario:
            self._add_element(dt_elem, XMLTag.PEC_DESTINATARIO, dati.PECDestinatario)

    def _add_cedente_prestatore(self, parent: Element, cedente: CedentePrestatore) -> None:
        """Aggiunge CedentePrestatore (1.2)"""
        cp_elem = SubElement(parent, self._ns_tag(XMLTag.CEDENTE_PRESTATORE))

        # 1.2.1 DatiAnagrafici
        self._add_dati_anagrafici_cedente(cp_elem, cedente.DatiAnagrafici)

        # 1.2.2 Sede
        self._add_sede(cp_elem, cedente.Sede, XMLTag.SEDE)

        # 1.2.3 Stabile organizzazione (opzionale)
        if cedente.StabileOrganizzazione:
            self._add_sede(cp_elem, cedente.StabileOrganizzazione, XMLTag.STABILE_ORGANIZZAZIONE)

        # 1.2.4 IscrizioneREA (opzionale)
        if cedente.IscrizioneREA:
            rea_elem = SubElement(cp_elem, self._ns_tag(XMLTag.ISCRIZIONE_REA))
            self._add_element(rea_elem, XMLTag.UFFICIO, cedente.IscrizioneREA.Ufficio)
            self._add_element(rea_elem, XMLTag.NUMERO_REA, cedente.IscrizioneREA.NumeroREA)
            if cedente.IscrizioneREA.CapitaleSociale is not None:
                self._add_decimal(rea_elem, XMLTag.CAPITALE_SOCIALE, cedente.IscrizioneREA.CapitaleSociale, DecimalPrecision.STANDARD)
            if cedente.IscrizioneREA.SocioUnico:
                self._add_element(rea_elem, XMLTag.SOCIO_UNICO, cedente.IscrizioneREA.SocioUnico)
            self._add_element(rea_elem, XMLTag.STATO_LIQUIDAZIONE, cedente.IscrizioneREA.StatoLiquidazione)

        # 1.2.5 Contatti (opzionale)
        if cedente.Contatti:
            self._add_contatti(cp_elem, cedente.Contatti)

        # 1.2.6 RiferimentoAmministrazione (opzionale)
        if cedente.RiferimentoAmministrazione:
            self._add_element(cp_elem, XMLTag.RIFERIMENTO_AMMINISTRAZIONE, cedente.RiferimentoAmministrazione)

    def _add_dati_anagrafici_cedente(self, parent: Element, dati: DatiAnagraficiCedente) -> None:
        """Aggiunge DatiAnagrafici del cedente (1.2.1)"""
        da_elem = SubElement(parent, self._ns_tag(XMLTag.DATI_ANAGRAFICI))

        # 1.2.1.1 IdFiscaleIVA
        self._add_id_fiscale_iva(da_elem, dati.IdFiscaleIVA)

        # 1.2.1.2 CodiceFiscale (opzionale)
        if dati.CodiceFiscale:
            self._add_element(da_elem, XMLTag.CODICE_FISCALE, dati.CodiceFiscale)

        # 1.2.1.3 Anagrafica
        self._add_anagrafica(da_elem, dati.Anagrafica)

        # 1.2.1.4-7 Albo professionale (opzionale)
        if dati.AlboProfessionale:
            self._add_element(da_elem, XMLTag.ALBO_PROFESSIONALE, dati.AlboProfessionale)
        if dati.ProvinciaAlbo:
            self._add_element(da_elem, XMLTag.PROVINCIA_ALBO, dati.ProvinciaAlbo)
        if dati.NumeroIscrizioneAlbo:
            self._add_element(da_elem, XMLTag.NUMERO_ISCRIZIONE_ALBO, dati.NumeroIscrizioneAlbo)
        if dati.DataIscrizioneAlbo:
            self._add_element(da_elem, XMLTag.DATA_ISCRIZIONE_ALBO, dati.DataIscrizioneAlbo)

        # 1.2.1.8 RegimeFiscale
        self._add_element(da_elem, XMLTag.REGIME_FISCALE, dati.RegimeFiscale.value)

    def _add_cessionario_committente(self, parent: Element, cessionario: CessionarioCommittente) -> None:
        """Aggiunge CessionarioCommittente (1.4)"""
        cc_elem = SubElement(parent, self._ns_tag(XMLTag.CESSIONARIO_COMMITTENTE))

        # 1.4.1 DatiAnagrafici
        self._add_dati_anagrafici_committente(cc_elem, cessionario.DatiAnagrafici)

        # 1.4.2 Sede
        self._add_sede(cc_elem, cessionario.Sede, XMLTag.SEDE)

        # 1.4.3 Stabile organizzazione (opzionale)
        if cessionario.StabileOrganizzazione:
            self._add_sede(cc_elem, cessionario.StabileOrganizzazione, XMLTag.STABILE_ORGANIZZAZIONE)

    def _add_dati_anagrafici_committente(self, parent: Element, dati: DatiAnagraficiCommittente) -> None:
        """Aggiunge DatiAnagrafici del committente (1.4.1)"""
        da_elem = SubElement(parent, self._ns_tag(XMLTag.DATI_ANAGRAFICI))

        # 1.4.1.1 IdFiscaleIVA (opzionale)
        if dati.IdFiscaleIVA:
            self._add_id_fiscale_iva(da_elem, dati.IdFiscaleIVA)

        # 1.4.1.2 CodiceFiscale (opzionale)
        if dati.CodiceFiscale:
            self._add_element(da_elem, XMLTag.CODICE_FISCALE, dati.CodiceFiscale)

        # 1.4.1.3 Anagrafica
        if dati.Anagrafica:
            self._add_anagrafica(da_elem, dati.Anagrafica)

    def _add_body(self, parent: Element, body: FatturaElettronicaBody) -> None:
        """Aggiunge FatturaElettronicaBody all'XML"""
        body_elem = SubElement(parent, self._ns_tag(XMLTag.FATTURA_ELETTRONICA_BODY))

        # 2.1 Dati generali
        self._add_dati_generali(body_elem, body.DatiGenerali)

        # 2.2 Dati beni servizi
        self._add_dati_beni_servizi(body_elem, body.DatiBeniServizi)

        # 2.3 Dati veicoli (opzionale)
        if body.DatiVeicoli:
            dv_elem = SubElement(body_elem, self._ns_tag(XMLTag.DATI_VEICOLI))
            self._add_element(dv_elem, XMLTag.DATA, body.DatiVeicoli.Data)
            self._add_element(dv_elem, XMLTag.TOTALE_PERCORSO, body.DatiVeicoli.TotalePercorso)

        # 2.4 Dati pagamento
        for dati_pagamento in body.DatiPagamento:
            self._add_dati_pagamento(body_elem, dati_pagamento)

        # 2.5 Allegati (opzionale)
        for allegato in body.Allegati:
            allegato_elem = SubElement(body_elem, self._ns_tag(XMLTag.ALLEGATI))
            self._add_element(allegato_elem, XMLTag.NOME_ATTACHMENT, allegato.NomeAttachment)
            if allegato.AlgoritmoCompressione:
                self._add_element(allegato_elem, XMLTag.ALGORITMO_COMPRESSIONE, allegato.AlgoritmoCompressione)
            if allegato.FormatoAttachment:
                self._add_element(allegato_elem, XMLTag.FORMATO_ATTACHMENT, allegato.FormatoAttachment)
            if allegato.DescrizioneAttachment:
                self._add_element(allegato_elem, XMLTag.DESCRIZIONE_ATTACHMENT, allegato.DescrizioneAttachment)
            self._add_element(allegato_elem, XMLTag.ATTACHMENT, allegato.Attachment)

    def _add_dati_generali(self, parent: Element, dati: DatiGenerali) -> None:
        """Aggiunge DatiGenerali (2.1)"""
        dg_elem = SubElement(parent, self._ns_tag(XMLTag.DATI_GENERALI))

        # 2.1.1 DatiGeneraliDocumento
        dgd_elem = SubElement(dg_elem, self._ns_tag(XMLTag.DATI_GENERALI_DOCUMENTO))

        doc = dati.DatiGeneraliDocumento

        # 2.1.1.1 TipoDocumento
        self._add_element(dgd_elem, XMLTag.TIPO_DOCUMENTO, doc.TipoDocumento.value)

        # 2.1.1.2 Divisa
        self._add_element(dgd_elem, XMLTag.DIVISA, doc.Divisa)

        # 2.1.1.3 Data
        self._add_element(dgd_elem, XMLTag.DATA, doc.Data)

        # 2.1.1.4 Numero
        self._add_element(dgd_elem, XMLTag.NUMERO, doc.Numero)

        # 2.1.1.5 DatiRitenuta (opzionale, multiplo)
        for ritenuta in doc.DatiRitenuta:
            dr_elem = SubElement(dgd_elem, self._ns_tag(XMLTag.DATI_RITENUTA))
            self._add_element(dr_elem, XMLTag.TIPO_RITENUTA, ritenuta.TipoRitenuta.value)
            self._add_decimal(dr_elem, XMLTag.IMPORTO_RITENUTA, ritenuta.ImportoRitenuta, DecimalPrecision.STANDARD)
            self._add_decimal(dr_elem, XMLTag.ALIQUOTA_RITENUTA, ritenuta.AliquotaRitenuta, DecimalPrecision.STANDARD)
            self._add_element(dr_elem, XMLTag.CAUSALE_PAGAMENTO, ritenuta.CausalePagamento)

        # 2.1.1.6 DatiBollo (opzionale)
        if doc.DatiBollo:
            db_elem = SubElement(dgd_elem, self._ns_tag(XMLTag.DATI_BOLLO))
            self._add_element(db_elem, XMLTag.BOLLO_VIRTUALE, doc.DatiBollo.BolloVirtuale)
            self._add_decimal(db_elem, XMLTag.IMPORTO_BOLLO, doc.DatiBollo.ImportoBollo, DecimalPrecision.STANDARD)

        # 2.1.1.7 DatiCassaPrevidenziale (opzionale, multiplo)
        for cassa in doc.DatiCassaPrevidenziale:
            dcp_elem = SubElement(dgd_elem, self._ns_tag(XMLTag.DATI_CASSA_PREVIDENZIALE))
            self._add_element(dcp_elem, XMLTag.TIPO_CASSA, cassa.TipoCassa.value)
            self._add_decimal(dcp_elem, XMLTag.AL_CASSA, cassa.AlCassa, DecimalPrecision.STANDARD)
            self._add_decimal(dcp_elem, XMLTag.IMPORTO_CONTRIBUTO_CASSA, cassa.ImportoContributoCassa, DecimalPrecision.STANDARD)
            if cassa.ImponibileCassa is not None:
                self._add_decimal(dcp_elem, XMLTag.IMPONIBILE_CASSA, cassa.ImponibileCassa, DecimalPrecision.STANDARD)
            self._add_decimal(dcp_elem, XMLTag.ALIQUOTA_IVA, cassa.AliquotaIVA, DecimalPrecision.STANDARD)
            if cassa.Ritenuta:
                self._add_element(dcp_elem, XMLTag.RITENUTA, cassa.Ritenuta)
            if cassa.Natura:
                self._add_element(dcp_elem, XMLTag.NATURA, cassa.Natura.value)
            if cassa.RiferimentoAmministrazione:
                self._add_element(dcp_elem, XMLTag.RIFERIMENTO_AMMINISTRAZIONE, cassa.RiferimentoAmministrazione)

        # 2.1.1.8 ScontoMaggiorazione (opzionale, multiplo)
        for sconto in doc.ScontoMaggiorazione:
            self._add_sconto_maggiorazione(dgd_elem, sconto)

        # 2.1.1.9 ImportoTotaleDocumento (opzionale)
        if doc.ImportoTotaleDocumento is not None:
            self._add_decimal(dgd_elem, XMLTag.IMPORTO_TOTALE_DOCUMENTO, doc.ImportoTotaleDocumento, DecimalPrecision.STANDARD)

        # 2.1.1.10 Arrotondamento (opzionale)
        if doc.Arrotondamento is not None:
            self._add_decimal(dgd_elem, XMLTag.ARROTONDAMENTO, doc.Arrotondamento, DecimalPrecision.STANDARD)

        # 2.1.1.11 Causale (opzionale, multiplo)
        for causale in doc.Causale:
            self._add_element(dgd_elem, XMLTag.CAUSALE, causale)

        # 2.1.1.12 Art73 (opzionale)
        if doc.Art73:
            self._add_element(dgd_elem, XMLTag.ART73, doc.Art73)

    def _add_dati_beni_servizi(self, parent: Element, dati: DatiBeniServizi) -> None:
        """Aggiunge DatiBeniServizi (2.2)"""
        dbs_elem = SubElement(parent, self._ns_tag(XMLTag.DATI_BENI_SERVIZI))

        # 2.2.1 DettaglioLinee (multiplo)
        for linea in dati.DettaglioLinee:
            self._add_dettaglio_linee(dbs_elem, linea)

        # 2.2.2 DatiRiepilogo (multiplo)
        for riepilogo in dati.DatiRiepilogo:
            self._add_dati_riepilogo(dbs_elem, riepilogo)

    def _add_dettaglio_linee(self, parent: Element, linea: DettaglioLinee) -> None:
        """Aggiunge DettaglioLinee (2.2.1)"""
        dl_elem = SubElement(parent, self._ns_tag(XMLTag.DETTAGLIO_LINEE))

        # 2.2.1.1 NumeroLinea
        self._add_element(dl_elem, XMLTag.NUMERO_LINEA, str(linea.NumeroLinea))

        # 2.2.1.2 TipoCessionePrestazione (opzionale)
        if linea.TipoCessionePrestazione:
            self._add_element(dl_elem, XMLTag.TIPO_CESSIONE_PRESTAZIONE, linea.TipoCessionePrestazione)

        # 2.2.1.3 CodiceArticolo (opzionale, multiplo)
        for codice in linea.CodiceArticolo:
            ca_elem = SubElement(dl_elem, self._ns_tag(XMLTag.CODICE_ARTICOLO))
            self._add_element(ca_elem, XMLTag.CODICE_TIPO, codice.CodiceTipo)
            self._add_element(ca_elem, XMLTag.CODICE_VALORE, codice.CodiceValore)

        # 2.2.1.4 Descrizione
        self._add_element(dl_elem, XMLTag.DESCRIZIONE, linea.Descrizione)

        # 2.2.1.5 Quantita (opzionale)
        if linea.Quantita is not None:
            self._add_decimal(dl_elem, XMLTag.QUANTITA, linea.Quantita, DecimalPrecision.EXTENDED)

        # 2.2.1.6 UnitaMisura (opzionale)
        if linea.UnitaMisura:
            self._add_element(dl_elem, XMLTag.UNITA_MISURA, linea.UnitaMisura)

        # 2.2.1.7-8 DataInizioPeriodo/DataFinePeriodo (opzionale)
        if linea.DataInizioPeriodo:
            self._add_element(dl_elem, XMLTag.DATA_INIZIO_PERIODO, linea.DataInizioPeriodo)
        if linea.DataFinePeriodo:
            self._add_element(dl_elem, XMLTag.DATA_FINE_PERIODO, linea.DataFinePeriodo)

        # 2.2.1.9 PrezzoUnitario
        self._add_decimal(dl_elem, XMLTag.PREZZO_UNITARIO, linea.PrezzoUnitario, DecimalPrecision.EXTENDED)

        # 2.2.1.10 ScontoMaggiorazione (opzionale, multiplo)
        for sconto in linea.ScontoMaggiorazione:
            self._add_sconto_maggiorazione(dl_elem, sconto)

        # 2.2.1.11 PrezzoTotale
        self._add_decimal(dl_elem, XMLTag.PREZZO_TOTALE, linea.PrezzoTotale, DecimalPrecision.EXTENDED)

        # 2.2.1.12 AliquotaIVA
        self._add_decimal(dl_elem, XMLTag.ALIQUOTA_IVA, linea.AliquotaIVA, DecimalPrecision.STANDARD)

        # 2.2.1.13 Ritenuta (opzionale)
        if linea.Ritenuta:
            self._add_element(dl_elem, XMLTag.RITENUTA, linea.Ritenuta)

        # 2.2.1.14 Natura (opzionale)
        if linea.Natura:
            self._add_element(dl_elem, XMLTag.NATURA, linea.Natura.value)

        # 2.2.1.15 RiferimentoAmministrazione (opzionale)
        if linea.RiferimentoAmministrazione:
            self._add_element(dl_elem, XMLTag.RIFERIMENTO_AMMINISTRAZIONE, linea.RiferimentoAmministrazione)

        # 2.2.1.16 AltriDatiGestionali (opzionale, multiplo)
        for altri_dati in linea.AltriDatiGestionali:
            adg_elem = SubElement(dl_elem, self._ns_tag(XMLTag.ALTRI_DATI_GESTIONALI))
            self._add_element(adg_elem, XMLTag.TIPO_DATO, altri_dati.TipoDato)
            if altri_dati.RiferimentoTesto:
                self._add_element(adg_elem, XMLTag.RIFERIMENTO_TESTO, altri_dati.RiferimentoTesto)
            if altri_dati.RiferimentoNumero is not None:
                self._add_decimal(adg_elem, XMLTag.RIFERIMENTO_NUMERO, altri_dati.RiferimentoNumero, DecimalPrecision.EXTENDED)
            if altri_dati.RiferimentoData:
                self._add_element(adg_elem, XMLTag.RIFERIMENTO_DATA, altri_dati.RiferimentoData)

    def _add_dati_riepilogo(self, parent: Element, riepilogo: DatiRiepilogo) -> None:
        """Aggiunge DatiRiepilogo (2.2.2)"""
        dr_elem = SubElement(parent, self._ns_tag(XMLTag.DATI_RIEPILOGO))

        # 2.2.2.1 AliquotaIVA
        self._add_decimal(dr_elem, XMLTag.ALIQUOTA_IVA, riepilogo.AliquotaIVA, DecimalPrecision.STANDARD)

        # 2.2.2.2 Natura (opzionale)
        if riepilogo.Natura:
            self._add_element(dr_elem, XMLTag.NATURA, riepilogo.Natura.value)

        # 2.2.2.3 SpeseAccessorie (opzionale)
        if riepilogo.SpeseAccessorie is not None:
            self._add_decimal(dr_elem, XMLTag.SPESE_ACCESSORIE, riepilogo.SpeseAccessorie, DecimalPrecision.STANDARD)

        # 2.2.2.4 Arrotondamento (opzionale)
        if riepilogo.Arrotondamento is not None:
            self._add_decimal(dr_elem, XMLTag.ARROTONDAMENTO, riepilogo.Arrotondamento, DecimalPrecision.EXTENDED)

        # 2.2.2.5 ImponibileImporto
        self._add_decimal(dr_elem, XMLTag.IMPONIBILE_IMPORTO, riepilogo.ImponibileImporto, DecimalPrecision.STANDARD)

        # 2.2.2.6 Imposta
        self._add_decimal(dr_elem, XMLTag.IMPOSTA, riepilogo.Imposta, DecimalPrecision.STANDARD)

        # 2.2.2.7 EsigibilitaIVA (opzionale)
        if riepilogo.EsigibilitaIVA:
            self._add_element(dr_elem, XMLTag.ESIGIBILITA_IVA, riepilogo.EsigibilitaIVA.value)

        # 2.2.2.8 RiferimentoNormativo (opzionale)
        if riepilogo.RiferimentoNormativo:
            self._add_element(dr_elem, XMLTag.RIFERIMENTO_NORMATIVO, riepilogo.RiferimentoNormativo)

    def _add_dati_pagamento(self, parent: Element, dati: DatiPagamento) -> None:
        """Aggiunge DatiPagamento (2.4)"""
        dp_elem = SubElement(parent, self._ns_tag(XMLTag.DATI_PAGAMENTO))

        # 2.4.1 CondizioniPagamento
        self._add_element(dp_elem, XMLTag.CONDIZIONI_PAGAMENTO, dati.CondizioniPagamento.value)

        # 2.4.2 DettaglioPagamento (multiplo)
        for dettaglio in dati.DettaglioPagamento:
            self._add_dettaglio_pagamento(dp_elem, dettaglio)

    def _add_dettaglio_pagamento(self, parent: Element, dettaglio: DettaglioPagamento) -> None:
        """Aggiunge DettaglioPagamento (2.4.2)"""
        dp_elem = SubElement(parent, self._ns_tag(XMLTag.DETTAGLIO_PAGAMENTO))

        # 2.4.2.1 Beneficiario (opzionale)
        if dettaglio.Beneficiario:
            self._add_element(dp_elem, XMLTag.BENEFICIARIO, dettaglio.Beneficiario)

        # 2.4.2.2 ModalitaPagamento
        self._add_element(dp_elem, XMLTag.MODALITA_PAGAMENTO, dettaglio.ModalitaPagamento.value)

        # 2.4.2.3 DataRiferimentoTerminiPagamento (opzionale)
        if dettaglio.DataRiferimentoTerminiPagamento:
            self._add_element(dp_elem, XMLTag.DATA_RIFERIMENTO_TERMINI_PAGAMENTO, dettaglio.DataRiferimentoTerminiPagamento)

        # 2.4.2.4 GiorniTerminiPagamento (opzionale)
        if dettaglio.GiorniTerminiPagamento is not None:
            self._add_element(dp_elem, XMLTag.GIORNI_TERMINI_PAGAMENTO, str(dettaglio.GiorniTerminiPagamento))

        # 2.4.2.5 DataScadenzaPagamento (opzionale)
        if dettaglio.DataScadenzaPagamento:
            self._add_element(dp_elem, XMLTag.DATA_SCADENZA_PAGAMENTO, dettaglio.DataScadenzaPagamento)

        # 2.4.2.6 ImportoPagamento
        self._add_decimal(dp_elem, XMLTag.IMPORTO_PAGAMENTO, dettaglio.ImportoPagamento, DecimalPrecision.STANDARD)

        # 2.4.2.7-21 Altri campi opzionali
        if dettaglio.CodUfficioPostale:
            self._add_element(dp_elem, XMLTag.COD_UFFICIO_POSTALE, dettaglio.CodUfficioPostale)
        if dettaglio.CognomeQuietanzante:
            self._add_element(dp_elem, XMLTag.COGNOME_QUIETANZANTE, dettaglio.CognomeQuietanzante)
        if dettaglio.NomeQuietanzante:
            self._add_element(dp_elem, XMLTag.NOME_QUIETANZANTE, dettaglio.NomeQuietanzante)
        if dettaglio.CFQuietanzante:
            self._add_element(dp_elem, XMLTag.CF_QUIETANZANTE, dettaglio.CFQuietanzante)
        if dettaglio.TitoloQuietanzante:
            self._add_element(dp_elem, XMLTag.TITOLO_QUIETANZANTE, dettaglio.TitoloQuietanzante)
        if dettaglio.IstitutoFinanziario:
            self._add_element(dp_elem, XMLTag.ISTITUTO_FINANZIARIO, dettaglio.IstitutoFinanziario)
        if dettaglio.IBAN:
            self._add_element(dp_elem, XMLTag.IBAN, dettaglio.IBAN)
        if dettaglio.ABI:
            self._add_element(dp_elem, XMLTag.ABI, dettaglio.ABI)
        if dettaglio.CAB:
            self._add_element(dp_elem, XMLTag.CAB, dettaglio.CAB)
        if dettaglio.BIC:
            self._add_element(dp_elem, XMLTag.BIC, dettaglio.BIC)
        if dettaglio.ScontoPagamentoAnticipato is not None:
            self._add_decimal(dp_elem, XMLTag.SCONTO_PAGAMENTO_ANTICIPATO, dettaglio.ScontoPagamentoAnticipato, DecimalPrecision.STANDARD)
        if dettaglio.DataLimitePagamentoAnticipato:
            self._add_element(dp_elem, XMLTag.DATA_LIMITE_PAGAMENTO_ANTICIPATO, dettaglio.DataLimitePagamentoAnticipato)
        if dettaglio.PenalitaPagamentiRitardati is not None:
            self._add_decimal(dp_elem, XMLTag.PENALITA_PAGAMENTI_RITARDATI, dettaglio.PenalitaPagamentiRitardati, DecimalPrecision.STANDARD)
        if dettaglio.DataDecorrenzaPenale:
            self._add_element(dp_elem, XMLTag.DATA_DECORRENZA_PENALE, dettaglio.DataDecorrenzaPenale)
        if dettaglio.CodicePagamento:
            self._add_element(dp_elem, XMLTag.CODICE_PAGAMENTO, dettaglio.CodicePagamento)

    # Metodi helper per elementi comuni

    def _add_id_fiscale_iva(self, parent: Element, id_fiscale: IdFiscaleIVA) -> None:
        """Aggiunge IdFiscaleIVA"""
        if_elem = SubElement(parent, self._ns_tag(XMLTag.ID_FISCALE_IVA))
        self._add_element(if_elem, XMLTag.ID_PAESE, id_fiscale.IdPaese)
        self._add_element(if_elem, XMLTag.ID_CODICE, id_fiscale.IdCodice)

    def _add_anagrafica(self, parent: Element, anagrafica: Anagrafica) -> None:
        """Aggiunge Anagrafica"""
        ana_elem = SubElement(parent, self._ns_tag(XMLTag.ANAGRAFICA))

        if anagrafica.Denominazione:
            self._add_element(ana_elem, XMLTag.DENOMINAZIONE, anagrafica.Denominazione)
        if anagrafica.Nome:
            self._add_element(ana_elem, XMLTag.NOME, anagrafica.Nome)
        if anagrafica.Cognome:
            self._add_element(ana_elem, XMLTag.COGNOME, anagrafica.Cognome)
        if anagrafica.Titolo:
            self._add_element(ana_elem, XMLTag.TITOLO, anagrafica.Titolo)
        if anagrafica.CodEORI:
            self._add_element(ana_elem, XMLTag.COD_EORI, anagrafica.CodEORI)

    def _add_sede(self, parent: Element, sede: Sede | StabileOrganizzazione, tag: XMLTag) -> None:
        """Aggiunge Sede o StabileOrganizzazione"""
        sede_elem = SubElement(parent, self._ns_tag(tag))

        self._add_element(sede_elem, XMLTag.INDIRIZZO, sede.Indirizzo)
        if sede.NumeroCivico:
            self._add_element(sede_elem, XMLTag.NUMERO_CIVICO, sede.NumeroCivico)
        self._add_element(sede_elem, XMLTag.CAP, sede.CAP)
        self._add_element(sede_elem, XMLTag.COMUNE, sede.Comune)
        if sede.Provincia:
            self._add_element(sede_elem, XMLTag.PROVINCIA, sede.Provincia)
        self._add_element(sede_elem, XMLTag.NAZIONE, sede.Nazione)

    def _add_contatti(self, parent: Element, contatti: Contatti) -> None:
        """Aggiunge Contatti"""
        cont_elem = SubElement(parent, self._ns_tag(XMLTag.CONTATTI))

        if contatti.Telefono:
            self._add_element(cont_elem, XMLTag.TELEFONO, contatti.Telefono)
        if contatti.Fax:
            self._add_element(cont_elem, XMLTag.FAX, contatti.Fax)
        if contatti.Email:
            self._add_element(cont_elem, XMLTag.EMAIL, contatti.Email)

    def _add_rappresentante_fiscale(self, parent: Element, rappresentante) -> None:
        """Aggiunge RappresentanteFiscale (1.3)"""
        rf_elem = SubElement(parent, self._ns_tag(XMLTag.RAPPRESENTANTE_FISCALE))

        # DatiAnagrafici
        da_elem = SubElement(rf_elem, self._ns_tag(XMLTag.DATI_ANAGRAFICI))
        self._add_id_fiscale_iva(da_elem, rappresentante.IdFiscaleIVA)
        self._add_anagrafica(da_elem, rappresentante.Anagrafica)

    def _add_sconto_maggiorazione(self, parent: Element, sconto: ScontoMaggiorazioneDettaglio) -> None:
        """Aggiunge ScontoMaggiorazione"""
        sm_elem = SubElement(parent, self._ns_tag(XMLTag.SCONTO_MAGGIORAZIONE))

        self._add_element(sm_elem, XMLTag.TIPO, sconto.Tipo.value)

        if sconto.Percentuale is not None:
            self._add_decimal(sm_elem, XMLTag.PERCENTUALE, sconto.Percentuale, DecimalPrecision.STANDARD)

        if sconto.Importo is not None:
            self._add_decimal(sm_elem, XMLTag.IMPORTO, sconto.Importo, DecimalPrecision.STANDARD)

    # Metodi utility

    def _ns_tag(self, tag: XMLTag) -> str:
        """Aggiunge namespace al tag"""
        return f"{{{self.namespace}}}{tag.value}"

    def _add_element(self, parent: Element, tag: XMLTag, text: str | None) -> Element | None:
        """Aggiunge un elemento XML semplice"""
        if text is None:
            return None

        elem = SubElement(parent, self._ns_tag(tag))
        elem.text = str(text)
        return elem

    def _add_decimal(self, parent: Element, tag: XMLTag, value: Decimal, decimal_places: int) -> Element | None:
        """Aggiunge un elemento Decimal formattato"""
        format_str = f"{{:.{decimal_places}f}}"
        text = format_str.format(value)
        return self._add_element(parent, tag, text)

    def _get_filename(self, fattura: FatturaElettronica) -> str:
        """
        Genera il nome del file secondo il pattern SDI: <IdPaese><IdCodice>_<ProgressivoInvio>.xml

        Args:
            fattura: Struttura dati della fattura

        Returns:
            Nome del file (es: IT12345678901_00001.xml)
        """
        id_paese = fattura.FatturaElettronicaHeader.DatiTrasmissione.IdTrasmittente.IdPaese
        id_codice = fattura.FatturaElettronicaHeader.DatiTrasmissione.IdTrasmittente.IdCodice
        progressivo = fattura.FatturaElettronicaHeader.DatiTrasmissione.ProgressivoInvio

        return f"{id_paese}{id_codice}_{progressivo}.xml"

    def save_to_file(self, fattura: FatturaElettronica, directory: str | Path, pretty_print: bool = True) -> Path:
        """
        Salva l'XML della fattura in un file locale

        Args:
            fattura: Struttura dati della fattura
            directory: Directory dove salvare il file
            pretty_print: Se True, formatta l'XML con indentazione

        Returns:
            Path del file salvato

        Example:
            >>> generator = FatturaPAXMLGenerator()
            >>> file_path = generator.save_to_file(fattura, "/path/to/invoices")
            >>> print(file_path)  # /path/to/invoices/IT12345678901_00001.xml
        """
        directory_path = Path(directory)
        directory_path.mkdir(parents=True, exist_ok=True)

        filename = self._get_filename(fattura)
        file_path = directory_path / filename

        logger.info(f"Saving invoice to file: {file_path}")

        xml_content = self.generate_xml(fattura, pretty_print=pretty_print)

        file_path.write_text(xml_content, encoding="utf-8")

        logger.info(f"Invoice saved successfully to {file_path}")
        return file_path

    def save_to_s3(
        self,
        fattura: FatturaElettronica,
        bucket: str,
        s3_prefix: str = "",
        s3_client: S3Client | None = None,
        pretty_print: bool = True,
    ) -> str:
        """
        Salva l'XML della fattura su AWS S3

        Args:
            fattura: Struttura dati della fattura
            bucket: Nome del bucket S3
            s3_prefix: Prefisso/path S3 (es: "invoices/2024/")
            s3_client: Client boto3 S3 (opzionale, viene creato se non fornito)
            pretty_print: Se True, formatta l'XML con indentazione

        Returns:
            Chiave S3 completa del file salvato (es: "invoices/2024/IT12345678901_00001.xml")

        Raises:
            Exception: Se boto3 non è installato o errore durante upload

        Example:
            >>> generator = FatturaPAXMLGenerator()
            >>> s3_key = generator.save_to_s3(fattura, "my-invoices-bucket", "2024/")
            >>> print(s3_key)  # 2024/IT12345678901_00001.xml
        """
        try:
            import boto3
        except ImportError:
            logger.error("boto3 not installed for S3 operations")
            raise Exception(
                "boto3 is required for S3 operations. "
                "Install it with: pip install boto3"
            )

        if s3_client is None:
            logger.debug("Creating default S3 client")
            s3_client = boto3.client("s3")  # type: ignore[assignment]

        filename = self._get_filename(fattura)

        # Rimuovi eventuali slash iniziali/finali dal prefix e costruisci la key
        s3_prefix_clean = s3_prefix.strip("/")
        s3_key = f"{s3_prefix_clean}/{filename}" if s3_prefix_clean else filename

        logger.info(f"Saving invoice to S3: s3://{bucket}/{s3_key}")

        xml_content = self.generate_xml(fattura, pretty_print=pretty_print)

        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=xml_content.encode("utf-8"),
                ContentType="application/xml",
            )
            logger.info(f"Invoice uploaded successfully to s3://{bucket}/{s3_key}")
        except Exception as e:
            logger.error(f"Failed to upload invoice to S3: {bucket}/{s3_key}", exc_info=True)
            raise Exception(f"Errore nel caricamento su S3 ({bucket}/{s3_key}): {e}")

        return s3_key
