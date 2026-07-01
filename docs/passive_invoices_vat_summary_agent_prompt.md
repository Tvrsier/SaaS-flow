# Backend feature prompt — Fatture passive + VAT Summary periodico

## Contesto

Il progetto SaaS gestisce già fatture attive, righe fattura, riepiloghi IVA fattura e generazione/parsing XML FatturaPA.
L'agent ha accesso completo al codice e alle migration Alembic esistenti, quindi **non deve basarsi su questo documento per ricostruire lo schema attuale**: deve prima ispezionare modelli, repository/service/router, migration e parser XML già presenti, poi implementare la feature seguendo lo stile del progetto.

Il parser XML FatturaPA **esiste già**. Non crearne uno nuovo se è già disponibile. L'obiettivo è collegare il parser esistente a una nuova implementazione di **fatture passive** e poi costruire il **VAT Summary periodico**.

Per ora:

* non creare endpoint API REST se non già richiesti dallo stile del progetto;
* non implementare integrazioni F24, banca, open banking o quietanze.

L'obiettivo immediato è avere una base backend testabile con test automatici e output leggibile in console.

\---

## Obiettivo funzionale

Implementare due blocchi:

1. **Fatture passive**

   * Importazione di una fattura passiva partendo da XML FatturaPA già parsabile dal parser esistente.
   * Persistenza della fattura passiva, delle righe e del riepilogo IVA.
   * Generazione dei movimenti IVA a credito.
2. **VAT Summary periodico**

   * Gestione periodi IVA mensili o trimestrali.
   * Calcolo IVA a debito, IVA a credito, credito riportato, saldo, importo da versare e credito da riportare.
   * Chiusura/liquidazione logica del periodo.
   * Registrazione manuale del pagamento del debito IVA, senza azzerare il saldo storico del periodo.

\---

## Regole contabili da rispettare

### IVA a debito e IVA a credito

* Fattura attiva emessa dal SaaS → genera IVA a debito.
* Fattura passiva ricevuta/importata → genera IVA a credito.
* Il credito non deve scalare automaticamente il debito a ogni singola fattura.
* Debito e credito devono rimanere movimenti separati e storicizzati.
* La compensazione avviene solo nel calcolo della liquidazione del periodo IVA.

Formula:

```text
saldo\_periodo = total\_debit - total\_credit - previous\_credit
```

Interpretazione:

```text
saldo\_periodo > 0  => IVA da versare
saldo\_periodo == 0 => nulla da versare / nulla da riportare
saldo\_periodo < 0  => credito IVA da riportare al periodo successivo
```

Esempio:

```text
Debito periodo:          1.000,00
Credito periodo:           700,00
Credito precedente:          0,00
Saldo:                    +300,00
Amount to pay:             300,00
Credit to carry:             0,00
```

Esempio con credito:

```text
Debito periodo:            500,00
Credito periodo:           800,00
Credito precedente:          0,00
Saldo:                    -300,00
Amount to pay:               0,00
Credit to carry:           300,00
```

### Pagamento del debito IVA

Quando l'utente paga l'IVA, **non bisogna aggiornare il saldo del periodo portandolo a zero**.

Il saldo è il risultato fiscale storico del periodo e deve rimanere invariato.

Bisogna invece registrare un pagamento collegato alla liquidazione/settlement:

```text
balance = +300,00
amount\_to\_pay = 300,00
amount\_paid = 300,00
payment\_status = PAID
payment\_date = ...
```

Quindi:

* `balance` resta `+300,00`;
* `amount\_to\_pay` resta `300,00`;
* viene aggiornato `amount\_paid`;
* viene aggiornato `payment\_status`;
* viene salvata la data pagamento.

\---

## Periodi IVA

Supportare almeno:

```text
MONTHLY
QUARTERLY
```

Trimestri standard anno solare:

```text
Q1: 01/01 - 31/03
Q2: 01/04 - 30/06
Q3: 01/07 - 30/09
Q4: 01/10 - 31/12
```

Mensile:

```text
M01: 01/01 - 31/01
M02: 01/02 - 28/29/02
...
M12: 01/12 - 31/12
```

Il cambio periodo non deve cancellare o modificare i dati del periodo precedente.

La logica corretta è:

```text
chiudo Q1
apro Q2
associo i nuovi movimenti a Q2
riporto solo eventuale credito residuo come previous\_credit
```

Non implementare un concetto di “reset” distruttivo.

\---

## Modelli / Tabelle da introdurre o adattare

L'agent deve scegliere nomi e relazioni coerenti con il codice esistente, ma la struttura funzionale desiderata è questa.

### PassiveInvoice

Rappresenta una fattura passiva importata da XML ricevuto.

Campi funzionali suggeriti:

```text
id
company\_id
supplier\_id nullable, se esiste/si crea anagrafica fornitore
supplier\_name
supplier\_vat\_number
supplier\_tax\_code nullable
supplier\_address fields se coerente con modello esistente
invoice\_number
invoice\_year
invoice\_date
registration\_date
vat\_competence\_date
currency
document\_type
status
taxable\_amount
vat\_amount
total\_amount
xml\_hash nullable
xml\_s3\_key nullable, oppure riferimento storage già presente
source\_channel nullable/mock
created\_at
updated\_at
deleted\_at nullable se coerente con stile esistente
```

Note:

* `invoice\_date` deriva dall'XML.
* `registration\_date` può essere valorizzata alla data import.
* `vat\_competence\_date` deve esistere separatamente, anche se per ora default = `invoice\_date`.
* `company\_id` è la P.IVA/azienda destinataria della fattura passiva.
* Il fornitore è il `CedentePrestatore` dell'XML.
* L'azienda cliente del SaaS è il `CessionarioCommittente` dell'XML.

### PassiveInvoiceLine

Se il progetto gestisce già righe fattura per le attive, creare equivalente coerente per passive.

Campi suggeriti:

```text
id
passive\_invoice\_id
line\_number
description
quantity
unit\_price
discount\_amount nullable
discount\_percentage nullable
taxable\_amount
vat\_rate
vat\_nature nullable
vat\_amount
total\_amount
unit\_of\_measure nullable
created\_at
updated\_at
```

### PassiveInvoiceVatSummary

Riepilogo IVA della fattura passiva.

Campi suggeriti:

```text
id
passive\_invoice\_id
vat\_rate
vat\_nature nullable
taxable\_amount
vat\_amount
created\_at
updated\_at
```

Vincolo consigliato:

```text
unique(passive\_invoice\_id, vat\_rate, vat\_nature)
```

### VatPeriod

Contenitore temporale fiscale.

Campi suggeriti:

```text
id
company\_id
year
period\_index
frequency: MONTHLY | QUARTERLY
start\_date
end\_date
status: OPEN | CLOSED | SETTLED
previous\_credit
created\_at
updated\_at
closed\_at nullable
settled\_at nullable
```

Note:

* `period\_index` vale 1-12 per mensile, 1-4 per trimestrale.
* `previous\_credit` rappresenta il credito riportato dal periodo precedente.
* Non usare float. Usare Decimal/Numeric.

Vincoli consigliati:

```text
unique(company\_id, year, period\_index, frequency)
check(period\_index valid by frequency)
check(previous\_credit >= 0)
```

### VatMovement

Movimento IVA atomico e storicizzato.

Campi suggeriti:

```text
id
company\_id
period\_id
source\_type: ACTIVE\_INVOICE | PASSIVE\_INVOICE | MANUAL\_ADJUSTMENT
source\_invoice\_id nullable
source\_passive\_invoice\_id nullable
movement\_type: DEBIT | CREDIT
document\_date
registration\_date
vat\_competence\_date
vat\_rate
vat\_nature nullable
taxable\_amount
vat\_amount
created\_at
updated\_at
```

Regole:

* Fatture attive → `movement\_type = DEBIT`.
* Fatture passive → `movement\_type = CREDIT`.
* Il movimento deve puntare al periodo determinato da `vat\_competence\_date`.
* Se il periodo è `CLOSED` o `SETTLED`, non modificare automaticamente i movimenti esistenti.
* Per ora, in caso di periodo chiuso, sollevare errore esplicito. Le rettifiche manuali saranno implementate dopo.

### VatSettlement

Snapshot/calcolo congelato della liquidazione IVA del periodo.

Campi suggeriti:

```text
id
company\_id
period\_id
total\_debit
total\_credit
previous\_credit
balance
amount\_to\_pay
credit\_to\_carry
amount\_paid
payment\_status: UNPAID | PARTIALLY\_PAID | PAID | OVERPAID
payment\_date nullable
payment\_reference nullable
created\_at
updated\_at
```

Regole:

* Deve essere creato alla chiusura del periodo o alla richiesta esplicita di settlement.
* Deve congelare i totali del periodo.
* Non deve cancellare i movimenti.
* Non deve portare `balance` a zero quando viene registrato il pagamento.

\---

## Servizi da implementare

Adattare nomi e posizione ai pattern del progetto.

### PassiveInvoiceImportService

Responsabilità:

```text
import\_from\_xml(company\_id, xml\_content, source\_channel="MOCK")
```

Flusso:

1. Usa il parser XML FatturaPA già presente.
2. Estrae dati fattura.
3. Determina se la fattura è passiva per la company indicata.
4. Calcola hash XML per idempotenza.
5. Se esiste già una passiva con stesso hash/company, evitare duplicati.
6. Crea `PassiveInvoice`.
7. Crea `PassiveInvoiceLine` se i dati sono disponibili.
8. Crea `PassiveInvoiceVatSummary`.
9. Crea i `VatMovement` CREDIT tramite `VatMovementService`.
10. Restituisce oggetto/DTO con fattura importata e riepilogo import.

Per ora, se l'XML non contiene dati sufficienti o non è compatibile con il parser, sollevare errore chiaro e testabile.

### VatPeriodService

Funzioni minime:

```text
get\_or\_create\_period(company\_id, competence\_date, frequency)
get\_current\_period(company\_id, date, frequency)
create\_next\_period(previous\_period)
close\_period(company\_id, period\_id)
settle\_period(company\_id, period\_id)
```

Regole:

* `get\_or\_create\_period` calcola start/end in base a frequency.
* Se il periodo precedente aveva `credit\_to\_carry`, il nuovo periodo deve avere `previous\_credit` valorizzato.
* Non cancellare periodi vecchi.

### VatMovementService

Funzioni minime:

```text
create\_from\_active\_invoice(invoice\_id)
create\_from\_passive\_invoice(passive\_invoice\_id)
replace\_for\_active\_invoice(invoice\_id)
replace\_for\_passive\_invoice(passive\_invoice\_id)
```

Regole:

* Prima di sostituire movimenti, verificare che il periodo collegato non sia CLOSED/SETTLED.
* Per fatture attive usare i riepiloghi IVA già esistenti.
* Per fatture passive usare `PassiveInvoiceVatSummary`.
* Generare un movimento per ogni aliquota/natura IVA presente nel riepilogo.

### VatSummaryService

Funzioni minime:

```text
calculate\_period\_summary(company\_id, period\_id)
close\_period\_and\_create\_settlement(company\_id, period\_id)
record\_settlement\_payment(settlement\_id, amount\_paid, payment\_date, reference=None)
```

Output calcolo:

```text
total\_debit
total\_credit
previous\_credit
balance
amount\_to\_pay
credit\_to\_carry
```

Regole pagamento:

```text
if amount\_paid == 0 => UNPAID
if 0 < amount\_paid < amount\_to\_pay => PARTIALLY\_PAID
if amount\_paid == amount\_to\_pay => PAID
if amount\_paid > amount\_to\_pay => OVERPAID
```

\---

## Console output richiesto

Per ora voglio visualizzare l'output in console.

Implementare uno script, comando CLI, test verbose o fixture eseguibile che stampi un riepilogo leggibile.

Esempio output desiderato:

```text
=== VAT SUMMARY Q1 2026 ===
Company: <company\_id>
Period: 2026-Q1 (2026-01-01 -> 2026-03-31)
Status: OPEN

Movements:
- DEBIT  | TD01 active invoice 1/2026 | taxable 1000.00 | VAT 220.00
- CREDIT | passive invoice A-15       | taxable 300.00  | VAT 66.00

Totals:
Total debit:       220.00
Total credit:       66.00
Previous credit:     0.00
Balance:           154.00
Amount to pay:     154.00
Credit to carry:     0.00
```

Dopo pagamento:

```text
=== VAT SETTLEMENT PAYMENT ===
Period: 2026-Q1
Balance:        154.00
Amount to pay:  154.00
Amount paid:    154.00
Payment status: PAID
Payment date:   2026-05-16
```

Nota: `balance` resta `154.00`, non diventa zero.

\---

## Test richiesti

Scrivere test automatici coerenti con framework già presente nel progetto.

### Fatture passive

Test minimi:

1. Import XML passivo valido.
2. Creazione `PassiveInvoice`.
3. Creazione righe passive se presenti.
4. Creazione `PassiveInvoiceVatSummary`.
5. Creazione `VatMovement` CREDIT.
6. Idempotenza: stesso XML/company non deve creare duplicati.
7. Errore chiaro per XML non valido/non parsabile.

### Periodi IVA

Test minimi:

1. `get\_or\_create\_period` mensile.
2. `get\_or\_create\_period` trimestrale.
3. Date Q1/Q2/Q3/Q4 corrette.
4. Period index corretto.
5. Periodo precedente con credito riportato → nuovo periodo con `previous\_credit`.

### VAT Summary

Test minimi:

1. Solo fatture attive → saldo positivo.
2. Fatture attive + passive nello stesso periodo → debito e credito separati.
3. Credito maggiore del debito → saldo negativo e `credit\_to\_carry` positivo.
4. Credito riportato dal periodo precedente riduce il saldo del periodo successivo.
5. Chiusura periodo crea `VatSettlement` con snapshot corretto.
6. Pagamento settlement aggiorna `amount\_paid` e `payment\_status` senza modificare `balance`.
7. Periodo CLOSED/SETTLED blocca modifiche automatiche ai movimenti.

### Console output

Aggiungere almeno un test o comando che produca output console leggibile.

Esempio:

```bash
pytest -s tests/.../test\_vat\_summary\_console.py
```

oppure comando equivalente già usato nel progetto.

\---

## Vincoli tecnici

* Usare `Decimal` lato Python e `Numeric` lato DB.
* Non usare `float` per importi.
* Seguire pattern esistenti per SQLAlchemy, Alembic, Pydantic/DTO, service/repository.
* Creare migration Alembic coerenti con quelle esistenti.
* Non creare parser XML duplicato.
* Non creare API REST pubbliche se non necessarie in questa fase.
* Non introdurre dipendenze pesanti senza motivo.
* Mantenere import idempotente.
* Scrivere errori espliciti e testabili.

\---

## Ordine di implementazione consigliato

1. Ispezionare modelli/migration esistenti.
2. Individuare parser XML FatturaPA già presente e relativo output.
3. Creare modelli/migration per fatture passive.
4. Implementare import service fatture passive.
5. Creare modelli/migration per `VatPeriod`, `VatMovement`, `VatSettlement`.
6. Implementare `VatPeriodService`.
7. Implementare `VatMovementService` per attive e passive.
8. Implementare `VatSummaryService`.
9. Scrivere test fatture passive.
10. Scrivere test periodi IVA.
11. Scrivere test summary/settlement/payment.
12. Aggiungere output console leggibile.
13. Eseguire test e correggere eventuali regressioni.

\---

## Nota finale

La feature deve riflettere questa logica di business:

```text
I movimenti IVA sono lo storico atomico.
Il periodo IVA è il contenitore temporale.
Il VAT Summary è un calcolo sul periodo.
Il VAT Settlement è lo snapshot congelato della liquidazione.
Il pagamento aggiorna lo stato del settlement, non il saldo storico.
Ragiona sulle feature che devono avvenire automaticamente a periodi fissi. Per esempio: Utente con vat period trimestrale -> al suo prossimo login alla scadenza del periodo precedente equivale la apertura del nuovo periodo
Tieni a mente creando questo codice che dovrai predisporre il tutto per supportare la feature di ricezione fatture passive quando create sul portale. Esempio utente A crea fattura per utente B e B è un utente registrato sul nostro sito -> la fattura sarà visualizzabile come fattura passiva per utente B in automatico, ma aggiornerà il saldo quando lo SDI avrà approvato la fattura. La parte SDI al momento non è ancora implementata quindi ragioneremo attraverso simulazioni ovviamente
```



