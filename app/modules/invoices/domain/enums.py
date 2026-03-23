from enum import Enum


class SubjectType(str, Enum):
    """Tipo di soggetto (interno, non usato in XML)"""
    COMPANY = "company"
    INDIVIDUAL = "individual"


class LineType(str, Enum):
    """Tipo di riga (interno, non usato in XML)"""
    PRODUCT = "product"
    SERVICE = "service"


class FormatoTrasmissione(str, Enum):
    """Formato della trasmissione FatturaPA"""
    FPA12 = "FPA12"  # Fattura verso PA
    FPR12 = "FPR12"  # Fattura verso privati


class TipoDocumento(str, Enum):
    """Codice tipo documento secondo specifiche FatturaPA"""
    TD01 = "TD01"  # Fattura
    TD02 = "TD02"  # Acconto/Anticipo su fattura
    TD03 = "TD03"  # Acconto/Anticipo su parcella
    TD04 = "TD04"  # Nota di credito
    TD05 = "TD05"  # Nota di debito
    TD06 = "TD06"  # Parcella
    TD07 = "TD07"  # Fattura semplificata
    TD08 = "TD08"  # Nota di credito semplificata
    TD09 = "TD09"  # Nota di debito semplificata
    TD16 = "TD16"  # Integrazione fattura reverse charge interno
    TD17 = "TD17"  # Integrazione/autofattura per acquisto servizi dall'estero
    TD18 = "TD18"  # Integrazione per acquisto di beni intracomunitari
    TD19 = "TD19"  # Integrazione/autofattura per acquisto di beni ex art.17 c.2 DPR 633/72
    TD20 = "TD20"  # Autofattura per regolarizzazione e integrazione delle fatture
    TD21 = "TD21"  # Autofattura per splafonamento
    TD22 = "TD22"  # Estrazione beni da Deposito IVA
    TD23 = "TD23"  # Estrazione beni da Deposito IVA con versamento dell'IVA
    TD24 = "TD24"  # Fattura differita di cui all'art.21, comma 4, lett. a)
    TD25 = "TD25"  # Fattura differita di cui all'art.21, comma 4, lett. b)
    TD26 = "TD26"  # Cessione di beni ammortizzabili e per passaggi interni
    TD27 = "TD27"  # Fattura per autoconsumo o per cessioni gratuite senza rivalsa
    TD28 = "TD28"  # Acquisti da San Marino con IVA


# Alias per retrocompatibilità
DocumentType = TipoDocumento


class Natura(str, Enum):
    """Natura dell'operazione quando IVA non è applicata"""
    N1 = "N1"  # Escluse ex art.15
    N2_1 = "N2.1"  # Non soggette ad IVA ai sensi degli artt. da 7 a 7-septies
    N2_2 = "N2.2"  # Non soggette - altri casi
    N3_1 = "N3.1"  # Non imponibili - esportazioni
    N3_2 = "N3.2"  # Non imponibili - cessioni intracomunitarie
    N3_3 = "N3.3"  # Non imponibili - cessioni verso San Marino
    N3_4 = "N3.4"  # Non imponibili - operazioni assimilate alle cessioni all'esportazione
    N3_5 = "N3.5"  # Non imponibili - a seguito di dichiarazioni d'intento
    N3_6 = "N3.6"  # Non imponibili - altre operazioni che non concorrono alla formazione del plafond
    N4 = "N4"  # Esenti
    N5 = "N5"  # Regime del margine / IVA non esposta in fattura
    N6_1 = "N6.1"  # Inversione contabile - cessione di rottami
    N6_2 = "N6.2"  # Inversione contabile - cessione di oro e argento
    N6_3 = "N6.3"  # Inversione contabile - subappalto nel settore edile
    N6_4 = "N6.4"  # Inversione contabile - cessione di fabbricati
    N6_5 = "N6.5"  # Inversione contabile - cessione di telefoni cellulari
    N6_6 = "N6.6"  # Inversione contabile - cessione di prodotti elettronici
    N6_7 = "N6.7"  # Inversione contabile - prestazioni comparto edile
    N6_8 = "N6.8"  # Inversione contabile - operazioni settore energetico
    N6_9 = "N6.9"  # Inversione contabile - altri casi
    N7 = "N7"  # IVA assolta in altro stato UE


# Alias per retrocompatibilità
NatureCode = Natura


class RegimeFiscale(str, Enum):
    """Regime fiscale del cedente/prestatore"""
    RF01 = "RF01"  # Ordinario
    RF02 = "RF02"  # Contribuenti minimi (art.1, c.96-117, L.244/07)
    RF04 = "RF04"  # Agricoltura e attività connesse e pesca (artt.34 e 34-bis, DPR 633/72)
    RF05 = "RF05"  # Vendita sali e tabacchi (art.74, c.1, DPR 633/72)
    RF06 = "RF06"  # Commercio fiammiferi (art.74, c.1, DPR 633/72)
    RF07 = "RF07"  # Editoria (art.74, c.1, DPR 633/72)
    RF08 = "RF08"  # Gestione servizi telefonia pubblica (art.74, c.1, DPR 633/72)
    RF09 = "RF09"  # Rivendita documenti di trasporto pubblico e di sosta (art.74, c.1, DPR 633/72)
    RF10 = "RF10"  # Intrattenimenti, giochi e altre attività (art.74, c.6, DPR 633/72)
    RF11 = "RF11"  # Agenzie viaggi e turismo (art.74-ter, DPR 633/72)
    RF12 = "RF12"  # Agriturismo (art.5, c.2, L.413/91)
    RF13 = "RF13"  # Vendite a domicilio (art.25-bis, c.6, DPR 600/73)
    RF14 = "RF14"  # Rivendita beni usati, oggetti d'arte, d'antiquariato o da collezione (art.36, DL 41/95)
    RF15 = "RF15"  # Agenzie di vendite all'asta di oggetti d'arte, antiquariato o da collezione (art.40-bis, DL 41/95)
    RF16 = "RF16"  # IVA per cassa P.A. (art.6, c.5, DPR 633/72)
    RF17 = "RF17"  # IVA per cassa (art.32-bis, DL 83/2012)
    RF19 = "RF19"  # Regime forfettario (art.1, c.54-89, L.190/2014)
    RF18 = "RF18"  # Altro


# Alias per retrocompatibilità
FiscalRegime = RegimeFiscale


class TipoRitenuta(str, Enum):
    """Tipo di ritenuta"""
    RT01 = "RT01"  # Ritenuta persone fisiche
    RT02 = "RT02"  # Ritenuta persone giuridiche
    RT03 = "RT03"  # Contributo INPS
    RT04 = "RT04"  # Contributo ENASARCO
    RT05 = "RT05"  # Contributo ENPAM
    RT06 = "RT06"  # Altro contributo previdenziale


# Alias per retrocompatibilità
Withholding = TipoRitenuta


class CondizioniPagamento(str, Enum):
    """Condizioni di pagamento"""
    TP01 = "TP01"  # Pagamento a rate
    TP02 = "TP02"  # Pagamento completo
    TP03 = "TP03"  # Anticipo


# Alias per retrocompatibilità
PaymentTerms = CondizioniPagamento


class ModalitaPagamento(str, Enum):
    """Modalità di pagamento"""
    MP01 = "MP01"  # Contanti
    MP02 = "MP02"  # Assegno
    MP03 = "MP03"  # Assegno circolare
    MP04 = "MP04"  # Contanti presso Tesoreria
    MP05 = "MP05"  # Bonifico
    MP06 = "MP06"  # Vaglia cambiario
    MP07 = "MP07"  # Bollettino bancario
    MP08 = "MP08"  # Carta di pagamento
    MP09 = "MP09"  # RID
    MP10 = "MP10"  # RID utenze
    MP11 = "MP11"  # RID veloce
    MP12 = "MP12"  # Riba
    MP13 = "MP13"  # MAV
    MP14 = "MP14"  # Quietanza erario
    MP15 = "MP15"  # Giroconto su conti di contabilità speciale
    MP16 = "MP16"  # Domiciliazione bancaria
    MP17 = "MP17"  # Domiciliazione postale
    MP18 = "MP18"  # Bollettino di c/c postale
    MP19 = "MP19"  # SEPA Direct Debit
    MP20 = "MP20"  # SEPA Direct Debit CORE
    MP21 = "MP21"  # SEPA Direct Debit B2B
    MP22 = "MP22"  # Trattenuta su somme già riscosse
    MP23 = "MP23"  # PagoPa


# Alias per retrocompatibilità
PaymentMethod = ModalitaPagamento


class EsigibilitaIVA(str, Enum):
    """Esigibilità IVA"""
    IMMEDIATE = "I"  # IVA ad esigibilità immediata
    DEFERRED = "D"  # IVA ad esigibilità differita
    SPLIT = "S"  # Scissione dei pagamenti


class TipoCassa(str, Enum):
    """Tipo cassa previdenziale"""
    TC01 = "TC01"  # Cassa nazionale previdenza e assistenza avvocati
    TC02 = "TC02"  # Cassa previdenza dottori commercialisti
    TC03 = "TC03"  # Cassa previdenza e assistenza geometri
    TC04 = "TC04"  # Cassa nazionale previdenza e assistenza ingegneri e architetti
    TC05 = "TC05"  # Cassa nazionale del notariato
    TC06 = "TC06"  # Cassa nazionale previdenza e assistenza ragionieri e periti commerciali
    TC07 = "TC07"  # ENPACL
    TC08 = "TC08"  # ENPAM
    TC09 = "TC09"  # ENPAP
    TC10 = "TC10"  # ENPAF
    TC11 = "TC11"  # ENPAV
    TC12 = "TC12"  # ENPAIA
    TC13 = "TC13"  # FASC
    TC14 = "TC14"  # EPAP
    TC15 = "TC15"  # EPPI
    TC16 = "TC16"  # ENASARCO
    TC17 = "TC17"  # ENAP
    TC18 = "TC18"  # ENPAB
    TC19 = "TC19"  # ENPAPI
    TC20 = "TC20"  # ENPAP
    TC21 = "TC21"  # EPAP
    TC22 = "TC22"  # INPS


class ScontoMaggiorazione(str, Enum):
    """Tipo sconto/maggiorazione"""
    SC = "SC"  # Sconto
    MG = "MG"  # Maggiorazione


class TipoRitenutaPrevidenziale(str, Enum):
    """Tipo ritenuta previdenziale"""
    SI = "SI"  # Contributo previdenziale soggetto a ritenuta
    NO = "NO"  # Contributo previdenziale non soggetto a ritenuta
