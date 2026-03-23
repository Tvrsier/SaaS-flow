"""
Costanti e configurazioni per la generazione XML FatturaPA
"""
from enum import Enum


class XMLNamespace(str, Enum):
    """Namespace XML per FatturaPA"""

    FATTURA_PA = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
    XSI = "http://www.w3.org/2001/XMLSchema-instance"


class XMLSchemaLocation:
    """Schema location per validazione XSD"""

    FATTURA_PA = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2 http://www.fatturapa.gov.it/export/fatturazione/sdi/fatturapa/v1.2/Schema_del_file_xml_FatturaPA_versione_1.2.xsd"


class XMLTag(str, Enum):
    """Tag XML principali FatturaPA"""

    # Root
    FATTURA_ELETTRONICA = "FatturaElettronica"

    # Header - Livello 1
    FATTURA_ELETTRONICA_HEADER = "FatturaElettronicaHeader"
    DATI_TRASMISSIONE = "DatiTrasmissione"
    CEDENTE_PRESTATORE = "CedentePrestatore"
    RAPPRESENTANTE_FISCALE = "RappresentanteFiscale"
    CESSIONARIO_COMMITTENTE = "CessionarioCommittente"
    TERZO_INTERMEDIARIO_O_SOGGETTO_EMITTENTE = "TerzoIntermediarioOSoggettoEmittente"
    SOGGETTO_EMITTENTE = "SoggettoEmittente"

    # Dati Trasmissione
    ID_TRASMITTENTE = "IdTrasmittente"
    ID_PAESE = "IdPaese"
    ID_CODICE = "IdCodice"
    PROGRESSIVO_INVIO = "ProgressivoInvio"
    FORMATO_TRASMISSIONE = "FormatoTrasmissione"
    CODICE_DESTINATARIO = "CodiceDestinatario"
    CONTATTI_TRASMITTENTE = "ContattiTrasmittente"
    PEC_DESTINATARIO = "PECDestinatario"

    # Anagrafica
    DATI_ANAGRAFICI = "DatiAnagrafici"
    ID_FISCALE_IVA = "IdFiscaleIVA"
    CODICE_FISCALE = "CodiceFiscale"
    ANAGRAFICA = "Anagrafica"
    DENOMINAZIONE = "Denominazione"
    NOME = "Nome"
    COGNOME = "Cognome"
    TITOLO = "Titolo"
    COD_EORI = "CodEORI"
    REGIME_FISCALE = "RegimeFiscale"

    # Albo Professionale
    ALBO_PROFESSIONALE = "AlboProfessionale"
    PROVINCIA_ALBO = "ProvinciaAlbo"
    NUMERO_ISCRIZIONE_ALBO = "NumeroIscrizioneAlbo"
    DATA_ISCRIZIONE_ALBO = "DataIscrizioneAlbo"

    # Sede
    SEDE = "Sede"
    STABILE_ORGANIZZAZIONE = "StabileOrganizzazione"
    INDIRIZZO = "Indirizzo"
    NUMERO_CIVICO = "NumeroCivico"
    CAP = "CAP"
    COMUNE = "Comune"
    PROVINCIA = "Provincia"
    NAZIONE = "Nazione"

    # Contatti
    CONTATTI = "Contatti"
    TELEFONO = "Telefono"
    FAX = "Fax"
    EMAIL = "Email"

    # REA
    ISCRIZIONE_REA = "IscrizioneREA"
    UFFICIO = "Ufficio"
    NUMERO_REA = "NumeroREA"
    CAPITALE_SOCIALE = "CapitaleSociale"
    SOCIO_UNICO = "SocioUnico"
    STATO_LIQUIDAZIONE = "StatoLiquidazione"

    # Riferimenti
    RIFERIMENTO_AMMINISTRAZIONE = "RiferimentoAmministrazione"

    # Body
    FATTURA_ELETTRONICA_BODY = "FatturaElettronicaBody"

    # Dati Generali
    DATI_GENERALI = "DatiGenerali"
    DATI_GENERALI_DOCUMENTO = "DatiGeneraliDocumento"
    TIPO_DOCUMENTO = "TipoDocumento"
    DIVISA = "Divisa"
    DATA = "Data"
    NUMERO = "Numero"

    # Ritenuta
    DATI_RITENUTA = "DatiRitenuta"
    TIPO_RITENUTA = "TipoRitenuta"
    IMPORTO_RITENUTA = "ImportoRitenuta"
    ALIQUOTA_RITENUTA = "AliquotaRitenuta"
    CAUSALE_PAGAMENTO = "CausalePagamento"

    # Bollo
    DATI_BOLLO = "DatiBollo"
    BOLLO_VIRTUALE = "BolloVirtuale"
    IMPORTO_BOLLO = "ImportoBollo"

    # Cassa Previdenziale
    DATI_CASSA_PREVIDENZIALE = "DatiCassaPrevidenziale"
    TIPO_CASSA = "TipoCassa"
    AL_CASSA = "AlCassa"
    IMPORTO_CONTRIBUTO_CASSA = "ImportoContributoCassa"
    IMPONIBILE_CASSA = "ImponibileCassa"
    ALIQUOTA_IVA = "AliquotaIVA"
    RITENUTA = "Ritenuta"
    NATURA = "Natura"

    # Sconto/Maggiorazione
    SCONTO_MAGGIORAZIONE = "ScontoMaggiorazione"
    TIPO = "Tipo"
    PERCENTUALE = "Percentuale"
    IMPORTO = "Importo"

    # Totali
    IMPORTO_TOTALE_DOCUMENTO = "ImportoTotaleDocumento"
    ARROTONDAMENTO = "Arrotondamento"
    CAUSALE = "Causale"
    ART73 = "Art73"

    # Dati Beni Servizi
    DATI_BENI_SERVIZI = "DatiBeniServizi"
    DETTAGLIO_LINEE = "DettaglioLinee"
    NUMERO_LINEA = "NumeroLinea"
    TIPO_CESSIONE_PRESTAZIONE = "TipoCessionePrestazione"

    # Codice Articolo
    CODICE_ARTICOLO = "CodiceArticolo"
    CODICE_TIPO = "CodiceTipo"
    CODICE_VALORE = "CodiceValore"

    # Dettagli Linea
    DESCRIZIONE = "Descrizione"
    QUANTITA = "Quantita"
    UNITA_MISURA = "UnitaMisura"
    DATA_INIZIO_PERIODO = "DataInizioPeriodo"
    DATA_FINE_PERIODO = "DataFinePeriodo"
    PREZZO_UNITARIO = "PrezzoUnitario"
    PREZZO_TOTALE = "PrezzoTotale"

    # Altri Dati Gestionali
    ALTRI_DATI_GESTIONALI = "AltriDatiGestionali"
    TIPO_DATO = "TipoDato"
    RIFERIMENTO_TESTO = "RiferimentoTesto"
    RIFERIMENTO_NUMERO = "RiferimentoNumero"
    RIFERIMENTO_DATA = "RiferimentoData"

    # Riepilogo IVA
    DATI_RIEPILOGO = "DatiRiepilogo"
    SPESE_ACCESSORIE = "SpeseAccessorie"
    IMPONIBILE_IMPORTO = "ImponibileImporto"
    IMPOSTA = "Imposta"
    ESIGIBILITA_IVA = "EsigibilitaIVA"
    RIFERIMENTO_NORMATIVO = "RiferimentoNormativo"

    # Dati Veicoli
    DATI_VEICOLI = "DatiVeicoli"
    TOTALE_PERCORSO = "TotalePercorso"

    # Dati Pagamento
    DATI_PAGAMENTO = "DatiPagamento"
    CONDIZIONI_PAGAMENTO = "CondizioniPagamento"
    DETTAGLIO_PAGAMENTO = "DettaglioPagamento"
    BENEFICIARIO = "Beneficiario"
    MODALITA_PAGAMENTO = "ModalitaPagamento"
    DATA_RIFERIMENTO_TERMINI_PAGAMENTO = "DataRiferimentoTerminiPagamento"
    GIORNI_TERMINI_PAGAMENTO = "GiorniTerminiPagamento"
    DATA_SCADENZA_PAGAMENTO = "DataScadenzaPagamento"
    IMPORTO_PAGAMENTO = "ImportoPagamento"

    # Dati Bancari
    COD_UFFICIO_POSTALE = "CodUfficioPostale"
    COGNOME_QUIETANZANTE = "CognomeQuietanzante"
    NOME_QUIETANZANTE = "NomeQuietanzante"
    CF_QUIETANZANTE = "CFQuietanzante"
    TITOLO_QUIETANZANTE = "TitoloQuietanzante"
    ISTITUTO_FINANZIARIO = "IstitutoFinanziario"
    IBAN = "IBAN"
    ABI = "ABI"
    CAB = "CAB"
    BIC = "BIC"
    SCONTO_PAGAMENTO_ANTICIPATO = "ScontoPagamentoAnticipato"
    DATA_LIMITE_PAGAMENTO_ANTICIPATO = "DataLimitePagamentoAnticipato"
    PENALITA_PAGAMENTI_RITARDATI = "PenalitaPagamentiRitardati"
    DATA_DECORRENZA_PENALE = "DataDecorrenzaPenale"
    CODICE_PAGAMENTO = "CodicePagamento"

    # Allegati
    ALLEGATI = "Allegati"
    NOME_ATTACHMENT = "NomeAttachment"
    ALGORITMO_COMPRESSIONE = "AlgoritmoCompressione"
    FORMATO_ATTACHMENT = "FormatoAttachment"
    DESCRIZIONE_ATTACHMENT = "DescrizioneAttachment"
    ATTACHMENT = "Attachment"


class XMLAttribute(str, Enum):
    """Attributi XML"""

    VERSIONE = "versione"
    SCHEMA_LOCATION = "schemaLocation"


class XMLVersion:
    """Versioni supportate"""

    FPA12 = "FPA12"  # Fattura verso PA
    FPR12 = "FPR12"  # Fattura verso privati


class XMLEncoding:
    """Encoding supportati"""

    UTF8 = "UTF-8"


class XMLDeclaration:
    """Dichiarazione XML standard"""

    VERSION = "1.0"
    ENCODING = XMLEncoding.UTF8


class DecimalPrecision:
    """Precisione decimali per diversi campi"""

    STANDARD = 2  # Importi, percentuali IVA (es. 1234.56)
    EXTENDED = 8  # Prezzi unitari, quantità (es. 1234.56789012)
