"""
Modelli per la generazione di XML FatturaPA secondo schema VFPR12 v1.2.3
Struttura allineata allo schema XSD ufficiale dell'Agenzia delle Entrate
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.modules.invoices.domain.enums import (
    TipoDocumento,
    Natura,
    ModalitaPagamento,
    CondizioniPagamento,
    RegimeFiscale,
    FormatoTrasmissione,
    EsigibilitaIVA,
    TipoCassa,
    ScontoMaggiorazione,
    TipoRitenuta,
)


# ============================================================================
# DATI DI TRASMISSIONE (Header - DatiTrasmissione)
# ============================================================================

@dataclass(slots=True)
class IdTrasmittente:
    """1.1.1 Identificativo del trasmittente"""
    IdPaese: str  # 1.1.1.1 - ISO 3166-1 alpha-2 (2 caratteri)
    IdCodice: str  # 1.1.1.2 - Codice fiscale o Partita IVA (min 1, max 28)


@dataclass(slots=True)
class ContattiTrasmittente:
    """1.1.5 Contatti del trasmittente (opzionale)"""
    Telefono: Optional[str] = None  # 1.1.5.1 - max 12
    Email: Optional[str] = None  # 1.1.5.2 - max 256


@dataclass(slots=True)
class DatiTrasmissione:
    """1.1 Dati di trasmissione della fattura"""
    IdTrasmittente: IdTrasmittente  # 1.1.1
    ProgressivoInvio: str  # 1.1.2 - max 10 caratteri alfanumerici
    FormatoTrasmissione: FormatoTrasmissione  # 1.1.3 - FPA12 o FPR12
    CodiceDestinatario: str  # 1.1.4 - 7 caratteri (Codice IPA per PA, codice SdI o "0000000" per privati)
    ContattiTrasmittente: Optional[ContattiTrasmittente] = None  # 1.1.5
    PECDestinatario: Optional[str] = None  # 1.1.6 - max 256


# ============================================================================
# CEDENTE/PRESTATORE (Header - CedentePrestatore)
# ============================================================================

@dataclass(slots=True)
class IdFiscaleIVA:
    """Identificativo fiscale ai fini IVA"""
    IdPaese: str  # ISO 3166-1 alpha-2
    IdCodice: str  # Partita IVA (max 28)


@dataclass(slots=True)
class Anagrafica:
    """Dati anagrafici di una persona fisica o giuridica"""
    Denominazione: Optional[str] = None  # max 80 - per persone giuridiche
    Nome: Optional[str] = None  # max 60 - per persone fisiche
    Cognome: Optional[str] = None  # max 60 - per persone fisiche
    Titolo: Optional[str] = None  # max 10 - es. Dott., Ing., ecc.
    CodEORI: Optional[str] = None  # max 17 - Codice EORI


@dataclass(slots=True)
class Sede:
    """Indirizzo completo"""
    Indirizzo: str  # 1.2.2.1 - max 60
    CAP: str  # 1.2.2.3 - 5 caratteri
    Comune: str  # 1.2.2.4 - max 60
    NumeroCivico: Optional[str] = None  # 1.2.2.2 - max 8
    Provincia: Optional[str] = None  # 1.2.2.5 - 2 caratteri (sigla)
    Nazione: str = "IT"  # 1.2.2.6 - ISO 3166-1 alpha-2


@dataclass(slots=True)
class StabileOrganizzazione:
    """1.2.3 Stabile organizzazione (opzionale)"""
    Indirizzo: str  # max 60
    CAP: str  # 5 caratteri
    Comune: str  # max 60
    NumeroCivico: Optional[str] = None  # max 8
    Provincia: Optional[str] = None  # 2 caratteri
    Nazione: str = "IT"  # ISO 3166-1 alpha-2


@dataclass(slots=True)
class IscrizioneREA:
    """1.2.4 Dati di iscrizione al REA"""
    Ufficio: str  # 1.2.4.1 - 2 caratteri (sigla provincia)
    NumeroREA: str  # 1.2.4.2 - max 20
    CapitaleSociale: Optional[Decimal] = None  # 1.2.4.3 - max 15 cifre di cui 2 decimali
    SocioUnico: Optional[str] = None  # 1.2.4.4 - SU (socio unico) o SM (più soci)
    StatoLiquidazione: str = "LS"  # 1.2.4.5 - LS (in liquidazione) o LN (non in liquidazione)


@dataclass(slots=True)
class Contatti:
    """1.2.5 Contatti (opzionale)"""
    Telefono: Optional[str] = None  # 1.2.5.1 - max 12
    Fax: Optional[str] = None  # 1.2.5.2 - max 12
    Email: Optional[str] = None  # 1.2.5.3 - max 256


@dataclass(slots=True)
class DatiAnagraficiCedente:
    """1.2.1 Dati anagrafici cedente/prestatore"""
    IdFiscaleIVA: IdFiscaleIVA  # 1.2.1.1
    Anagrafica: Anagrafica  # 1.2.1.3
    RegimeFiscale: RegimeFiscale  # 1.2.1.8
    CodiceFiscale: Optional[str] = None  # 1.2.1.2 - max 28
    AlboProfessionale: Optional[str] = None  # 1.2.1.4 - max 60
    ProvinciaAlbo: Optional[str] = None  # 1.2.1.5 - 2 caratteri
    NumeroIscrizioneAlbo: Optional[str] = None  # 1.2.1.6 - max 60
    DataIscrizioneAlbo: Optional[str] = None  # 1.2.1.7 - formato YYYY-MM-DD


@dataclass(slots=True)
class RappresentanteFiscale:
    """1.3 Rappresentante fiscale (opzionale)"""
    IdFiscaleIVA: IdFiscaleIVA  # 1.3.1
    Anagrafica: Anagrafica  # 1.3.2


@dataclass(slots=True)
class CedentePrestatore:
    """1.2 Dati del cedente/prestatore"""
    DatiAnagrafici: DatiAnagraficiCedente  # 1.2.1
    Sede: Sede  # 1.2.2
    StabileOrganizzazione: Optional[StabileOrganizzazione] = None  # 1.2.3
    IscrizioneREA: Optional[IscrizioneREA] = None  # 1.2.4
    Contatti: Optional[Contatti] = None  # 1.2.5
    RiferimentoAmministrazione: Optional[str] = None  # 1.2.6 - max 20


# ============================================================================
# CESSIONARIO/COMMITTENTE (Header - CessionarioCommittente)
# ============================================================================

@dataclass(slots=True)
class DatiAnagraficiCommittente:
    """1.4.1 Dati anagrafici cessionario/committente"""
    IdFiscaleIVA: Optional[IdFiscaleIVA] = None  # 1.4.1.1
    CodiceFiscale: Optional[str] = None  # 1.4.1.2 - max 28
    Anagrafica: Optional[Anagrafica] = None  # 1.4.1.3


@dataclass(slots=True)
class CessionarioCommittente:
    """1.4 Dati del cessionario/committente"""
    DatiAnagrafici: DatiAnagraficiCommittente  # 1.4.1
    Sede: Sede  # 1.4.2
    StabileOrganizzazione: Optional[StabileOrganizzazione] = None  # 1.4.3
    RappresentanteFiscale: Optional[RappresentanteFiscale] = None  # 1.4.4


# ============================================================================
# TERZO INTERMEDIARIO O SOGGETTO EMITTENTE (opzionale)
# ============================================================================

@dataclass(slots=True)
class DatiAnagraficiTerzo:
    """1.5.1 Dati anagrafici terzo intermediario"""
    IdFiscaleIVA: Optional[IdFiscaleIVA] = None  # 1.5.1.1
    CodiceFiscale: Optional[str] = None  # 1.5.1.2
    Anagrafica: Optional[Anagrafica] = None  # 1.5.1.3


@dataclass(slots=True)
class TerzoIntermediarioOSoggettoEmittente:
    """1.5 Terzo intermediario o soggetto emittente (opzionale)"""
    DatiAnagrafici: DatiAnagraficiTerzo  # 1.5.1


# ============================================================================
# HEADER COMPLETO
# ============================================================================

@dataclass(slots=True)
class FatturaElettronicaHeader:
    """1 Intestazione della fattura elettronica"""
    DatiTrasmissione: DatiTrasmissione  # 1.1
    CedentePrestatore: CedentePrestatore  # 1.2
    RappresentanteFiscale: Optional[RappresentanteFiscale] = None  # 1.3
    CessionarioCommittente: Optional[CessionarioCommittente] = None  # 1.4
    TerzoIntermediarioOSoggettoEmittente: Optional[TerzoIntermediarioOSoggettoEmittente] = None  # 1.5
    SoggettoEmittente: Optional[str] = None  # 1.6 - CC (cessionario/committente) o TZ (terzo)


# ============================================================================
# BODY - DATI GENERALI
# ============================================================================

@dataclass(slots=True)
class DatiRitenuta:
    """2.1.1.5 Dati relativi alle ritenute"""
    TipoRitenuta: TipoRitenuta  # 2.1.1.5.1
    ImportoRitenuta: Decimal  # 2.1.1.5.2 - max 15 cifre di cui 2 decimali
    AliquotaRitenuta: Decimal  # 2.1.1.5.3 - max 6 cifre di cui 2 decimali
    CausalePagamento: str  # 2.1.1.5.4 - max 2 caratteri


@dataclass(slots=True)
class DatiBollo:
    """2.1.1.6 Dati relativi al bollo"""
    BolloVirtuale: str  # 2.1.1.6.1 - SI
    ImportoBollo: Decimal  # 2.1.1.6.2 - max 15 cifre di cui 2 decimali


@dataclass(slots=True)
class DatiCassaPrevidenziale:
    """2.1.1.7 Dati cassa previdenziale"""
    TipoCassa: TipoCassa  # 2.1.1.7.1
    AlCassa: Decimal  # 2.1.1.7.2 - max 6 cifre di cui 2 decimali
    ImportoContributoCassa: Decimal  # 2.1.1.7.3 - max 15 cifre di cui 2 decimali
    ImponibileCassa: Optional[Decimal] = None  # 2.1.1.7.4 - max 15 cifre di cui 2 decimali
    AliquotaIVA: Decimal = Decimal("0.00")  # 2.1.1.7.5 - max 6 cifre di cui 2 decimali
    Ritenuta: Optional[str] = None  # 2.1.1.7.6 - SI
    Natura: Optional[Natura] = None  # 2.1.1.7.7
    RiferimentoAmministrazione: Optional[str] = None  # 2.1.1.7.8 - max 20


@dataclass(slots=True)
class ScontoMaggiorazioneDettaglio:
    """2.1.1.8 Sconto o maggiorazione globale"""
    Tipo: ScontoMaggiorazione  # 2.1.1.8.1 - SC o MG
    Percentuale: Optional[Decimal] = None  # 2.1.1.8.2 - max 6 cifre di cui 2 decimali
    Importo: Optional[Decimal] = None  # 2.1.1.8.3 - max 15 cifre di cui 2 decimali


@dataclass(slots=True)
class DatiGeneraliDocumento:
    """2.1.1 Dati generali del documento"""
    TipoDocumento: TipoDocumento  # 2.1.1.1
    Divisa: str  # 2.1.1.2 - ISO 4217 alpha-3 (es. EUR)
    Data: str  # 2.1.1.3 - formato YYYY-MM-DD
    Numero: str  # 2.1.1.4 - max 20
    DatiRitenuta: list[DatiRitenuta] = field(default_factory=list)  # 2.1.1.5
    DatiBollo: Optional[DatiBollo] = None  # 2.1.1.6
    DatiCassaPrevidenziale: list[DatiCassaPrevidenziale] = field(default_factory=list)  # 2.1.1.7
    ScontoMaggiorazione: list[ScontoMaggiorazioneDettaglio] = field(default_factory=list)  # 2.1.1.8
    ImportoTotaleDocumento: Optional[Decimal] = None  # 2.1.1.9 - max 15 cifre di cui 2 decimali
    Arrotondamento: Optional[Decimal] = None  # 2.1.1.10 - max 15 cifre di cui 2 decimali
    Causale: list[str] = field(default_factory=list)  # 2.1.1.11 - max 200 caratteri per riga
    Art73: Optional[str] = None  # 2.1.1.12 - SI se fattura semplificata


@dataclass(slots=True)
class DatiDocumentoRiferimento:
    """
    Struttura base per riferimenti a documenti (ordine, contratto, convenzione, ricezione, fatture collegate)
    Usata in 2.1.2, 2.1.3, 2.1.4, 2.1.5, 2.1.6
    """
    RiferimentoNumeroLinea: list[int] = field(default_factory=list)
    IdDocumento: str = ""  # max 20
    Data: Optional[str] = None  # formato YYYY-MM-DD
    NumItem: Optional[str] = None  # max 20
    CodiceCommessaConvenzione: Optional[str] = None  # max 100
    CodiceCUP: Optional[str] = None  # max 15
    CodiceCIG: Optional[str] = None  # max 15


# Alias per chiarezza semantica nel codice
DatiOrdineAcquisto = DatiDocumentoRiferimento  # 2.1.2
DatiContratto = DatiDocumentoRiferimento  # 2.1.3
DatiConvenzione = DatiDocumentoRiferimento  # 2.1.4
DatiRicezione = DatiDocumentoRiferimento  # 2.1.5
DatiFattureCollegate = DatiDocumentoRiferimento  # 2.1.6


@dataclass(slots=True)
class DatiSAL:
    """2.1.7 Dati SAL - Stato Avanzamento Lavori (opzionale)"""
    RiferimentoFase: int  # 2.1.7.1 - numero progressivo SAL


@dataclass(slots=True)
class DatiDDT:
    """2.1.8 Dati DDT (opzionale)"""
    NumeroDDT: str  # 2.1.8.1 - max 20
    DataDDT: str  # 2.1.8.2 - formato YYYY-MM-DD
    RiferimentoNumeroLinea: list[int] = field(default_factory=list)  # 2.1.8.3


@dataclass(slots=True)
class DatiAnagraficiVettore:
    """2.1.9.1 Dati anagrafici vettore"""
    IdFiscaleIVA: Optional[IdFiscaleIVA] = None  # 2.1.9.1.1
    CodiceFiscale: Optional[str] = None  # 2.1.9.1.2
    Anagrafica: Optional[Anagrafica] = None  # 2.1.9.1.3
    NumeroLicenzaGuida: Optional[str] = None  # 2.1.9.1.4 - max 20


@dataclass(slots=True)
class DatiTrasporto:
    """2.1.9 Dati trasporto (opzionale)"""
    DatiAnagraficiVettore: Optional[DatiAnagraficiVettore] = None  # 2.1.9.1
    MezzoTrasporto: Optional[str] = None  # 2.1.9.2 - max 80
    CausaleTrasporto: Optional[str] = None  # 2.1.9.3 - max 100
    NumeroColli: Optional[int] = None  # 2.1.9.4
    Descrizione: Optional[str] = None  # 2.1.9.5 - max 100
    UnitaMisuraPeso: Optional[str] = None  # 2.1.9.6 - max 10
    PesoLordo: Optional[Decimal] = None  # 2.1.9.7 - max 7 cifre di cui 2 decimali
    PesoNetto: Optional[Decimal] = None  # 2.1.9.8 - max 7 cifre di cui 2 decimali
    DataOraRitiro: Optional[str] = None  # 2.1.9.9 - formato YYYY-MM-DDTHH:MM:SS
    DataInizioTrasporto: Optional[str] = None  # 2.1.9.10 - formato YYYY-MM-DD
    TipoResa: Optional[str] = None  # 2.1.9.11 - max 3 (codice Incoterms)
    IndirizzoResa: Optional[Sede] = None  # 2.1.9.12
    DataOraConsegna: Optional[str] = None  # 2.1.9.13 - formato YYYY-MM-DDTHH:MM:SS


@dataclass(slots=True)
class FatturaPrincipale:
    """2.1.10 Fattura principale (opzionale, per note di credito/debito)"""
    NumeroFatturaPrincipale: str  # 2.1.10.1 - max 20
    DataFatturaPrincipale: str  # 2.1.10.2 - formato YYYY-MM-DD


@dataclass(slots=True)
class DatiGenerali:
    """2.1 Dati generali del body"""
    DatiGeneraliDocumento: DatiGeneraliDocumento  # 2.1.1
    DatiOrdineAcquisto: list[DatiOrdineAcquisto] = field(default_factory=list)  # 2.1.2
    DatiContratto: list[DatiContratto] = field(default_factory=list)  # 2.1.3
    DatiConvenzione: list[DatiConvenzione] = field(default_factory=list)  # 2.1.4
    DatiRicezione: list[DatiRicezione] = field(default_factory=list)  # 2.1.5
    DatiFattureCollegate: list[DatiFattureCollegate] = field(default_factory=list)  # 2.1.6
    DatiSAL: list[DatiSAL] = field(default_factory=list)  # 2.1.7
    DatiDDT: list[DatiDDT] = field(default_factory=list)  # 2.1.8
    DatiTrasporto: Optional[DatiTrasporto] = None  # 2.1.9
    FatturaPrincipale: Optional[FatturaPrincipale] = None  # 2.1.10


# ============================================================================
# BODY - DATI BENI SERVIZI (RIGHE FATTURA)
# ============================================================================

@dataclass(slots=True)
class CodiceArticolo:
    """2.2.1.3 Codice articolo (opzionale)"""
    CodiceTipo: str  # 2.2.1.3.1 - max 35 (es. TARIC, CPV, EAN, ecc.)
    CodiceValore: str  # 2.2.1.3.2 - max 35


@dataclass(slots=True)
class AltriDatiGestionali:
    """2.2.1.16 Altri dati gestionali (opzionale)"""
    TipoDato: str  # 2.2.1.16.1 - max 10
    RiferimentoTesto: Optional[str] = None  # 2.2.1.16.2 - max 60
    RiferimentoNumero: Optional[Decimal] = None  # 2.2.1.16.3 - max 21 cifre di cui 8 decimali
    RiferimentoData: Optional[str] = None  # 2.2.1.16.4 - formato YYYY-MM-DD


@dataclass(slots=True)
class DettaglioLinee:
    """2.2.1 Dettaglio linea fattura"""
    NumeroLinea: int  # 2.2.1.1 - progressivo linea
    Descrizione: str  # 2.2.1.4 - max 1000
    PrezzoUnitario: Decimal  # 2.2.1.9 - max 21 cifre di cui 8 decimali
    PrezzoTotale: Decimal  # 2.2.1.11 - max 21 cifre di cui 8 decimali
    AliquotaIVA: Decimal  # 2.2.1.12 - max 6 cifre di cui 2 decimali
    TipoCessionePrestazione: Optional[str] = None  # 2.2.1.2 - SC (sconto) o PR (premio)
    CodiceArticolo: list[CodiceArticolo] = field(default_factory=list)  # 2.2.1.3
    Quantita: Optional[Decimal] = None  # 2.2.1.5 - max 21 cifre di cui 8 decimali
    UnitaMisura: Optional[str] = None  # 2.2.1.6 - max 10
    DataInizioPeriodo: Optional[str] = None  # 2.2.1.7 - formato YYYY-MM-DD
    DataFinePeriodo: Optional[str] = None  # 2.2.1.8 - formato YYYY-MM-DD
    ScontoMaggiorazione: list[ScontoMaggiorazioneDettaglio] = field(default_factory=list)  # 2.2.1.10
    Ritenuta: Optional[str] = None  # 2.2.1.13 - SI
    Natura: Optional[Natura] = None  # 2.2.1.14
    RiferimentoAmministrazione: Optional[str] = None  # 2.2.1.15 - max 20
    AltriDatiGestionali: list[AltriDatiGestionali] = field(default_factory=list)  # 2.2.1.16


@dataclass(slots=True)
class DatiRiepilogo:
    """2.2.2 Riepilogo IVA"""
    AliquotaIVA: Decimal  # 2.2.2.1 - max 6 cifre di cui 2 decimali
    ImponibileImporto: Decimal  # 2.2.2.5 - max 15 cifre di cui 2 decimali
    Imposta: Decimal  # 2.2.2.6 - max 15 cifre di cui 2 decimali
    Natura: Optional[Natura] = None  # 2.2.2.2
    SpeseAccessorie: Optional[Decimal] = None  # 2.2.2.3 - max 15 cifre di cui 2 decimali
    Arrotondamento: Optional[Decimal] = None  # 2.2.2.4 - max 21 cifre di cui 8 decimali
    EsigibilitaIVA: Optional[EsigibilitaIVA] = None  # 2.2.2.7
    RiferimentoNormativo: Optional[str] = None  # 2.2.2.8 - max 100


@dataclass(slots=True)
class DatiBeniServizi:
    """2.2 Dati beni e servizi"""
    DettaglioLinee: list[DettaglioLinee] = field(default_factory=list)  # 2.2.1
    DatiRiepilogo: list[DatiRiepilogo] = field(default_factory=list)  # 2.2.2


# ============================================================================
# BODY - DATI VEICOLI (opzionale)
# ============================================================================

@dataclass(slots=True)
class DatiVeicoli:
    """2.3 Dati veicoli (opzionale)"""
    Data: str  # 2.3.1 - formato YYYY-MM-DD (prima immatricolazione o iscrizione in PRA)
    TotalePercorso: str  # 2.3.2 - max 15 caratteri (km percorsi)


# ============================================================================
# BODY - DATI PAGAMENTO
# ============================================================================

@dataclass(slots=True)
class DettaglioPagamento:
    """2.4.2 Dettaglio pagamento"""
    ModalitaPagamento: ModalitaPagamento  # 2.4.2.2
    ImportoPagamento: Decimal  # 2.4.2.6 - max 15 cifre di cui 2 decimali
    Beneficiario: Optional[str] = None  # 2.4.2.1 - max 200
    DataRiferimentoTerminiPagamento: Optional[str] = None  # 2.4.2.3 - formato YYYY-MM-DD
    GiorniTerminiPagamento: Optional[int] = None  # 2.4.2.4
    DataScadenzaPagamento: Optional[str] = None  # 2.4.2.5 - formato YYYY-MM-DD
    CodUfficioPostale: Optional[str] = None  # 2.4.2.7 - max 20
    CognomeQuietanzante: Optional[str] = None  # 2.4.2.8 - max 60
    NomeQuietanzante: Optional[str] = None  # 2.4.2.9 - max 60
    CFQuietanzante: Optional[str] = None  # 2.4.2.10 - max 16
    TitoloQuietanzante: Optional[str] = None  # 2.4.2.11 - max 10
    IstitutoFinanziario: Optional[str] = None  # 2.4.2.12 - max 80
    IBAN: Optional[str] = None  # 2.4.2.13 - max 34
    ABI: Optional[str] = None  # 2.4.2.14 - 5 caratteri
    CAB: Optional[str] = None  # 2.4.2.15 - 5 caratteri
    BIC: Optional[str] = None  # 2.4.2.16 - max 11
    ScontoPagamentoAnticipato: Optional[Decimal] = None  # 2.4.2.17 - max 15 cifre di cui 2 decimali
    DataLimitePagamentoAnticipato: Optional[str] = None  # 2.4.2.18 - formato YYYY-MM-DD
    PenalitaPagamentiRitardati: Optional[Decimal] = None  # 2.4.2.19 - max 15 cifre di cui 2 decimali
    DataDecorrenzaPenale: Optional[str] = None  # 2.4.2.20 - formato YYYY-MM-DD
    CodicePagamento: Optional[str] = None  # 2.4.2.21 - max 60


@dataclass(slots=True)
class DatiPagamento:
    """2.4 Dati pagamento (opzionale)"""
    CondizioniPagamento: CondizioniPagamento  # 2.4.1
    DettaglioPagamento: list[DettaglioPagamento] = field(default_factory=list)  # 2.4.2


# ============================================================================
# BODY - ALLEGATI (opzionale)
# ============================================================================

@dataclass(slots=True)
class Allegati:
    """2.5 Allegati (opzionale)"""
    NomeAttachment: str  # 2.5.1 - max 60
    Attachment: str  # 2.5.5 - contenuto binario in Base64
    AlgoritmoCompressione: Optional[str] = None  # 2.5.2 - max 10
    FormatoAttachment: Optional[str] = None  # 2.5.3 - max 10
    DescrizioneAttachment: Optional[str] = None  # 2.5.4 - max 100


# ============================================================================
# BODY COMPLETO
# ============================================================================

@dataclass(slots=True)
class FatturaElettronicaBody:
    """2 Corpo della fattura elettronica"""
    DatiGenerali: DatiGenerali  # 2.1
    DatiBeniServizi: DatiBeniServizi  # 2.2
    DatiVeicoli: Optional[DatiVeicoli] = None  # 2.3
    DatiPagamento: list[DatiPagamento] = field(default_factory=list)  # 2.4
    Allegati: list[Allegati] = field(default_factory=list)  # 2.5


# ============================================================================
# FATTURA COMPLETA
# ============================================================================

@dataclass(slots=True)
class FatturaElettronica:
    """Fattura elettronica completa secondo schema FatturaPA v1.2.3"""
    versione: str  # Versione dello schema (es. "FPR12")
    FatturaElettronicaHeader: FatturaElettronicaHeader  # 1
    FatturaElettronicaBody: list[FatturaElettronicaBody] = field(default_factory=list)  # 2
