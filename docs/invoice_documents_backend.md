# Backend — Generazione e download PDF/XML delle fatture

## Obiettivo

Implementare nel backend FastAPI:

1. un entrypoint riutilizzabile per generare PDF e XML;
2. un worker avviato dopo la creazione della fattura;
3. la rigenerazione sincrona dei file mancanti durante il download;
4. due endpoint GET che ricevono `invoice_number`;
5. la risposta binaria tramite `FileResponse`.

La risposta della creazione fattura deve rimanere invariata: salvataggio, commit e restituzione della fattura creata. La generazione documentale non deve rallentare tale risposta.

## Contratto di interfaccia condiviso FE/BE

### Identificazione della fattura

Il frontend invia `invoice_number`.

Il backend identifica la fattura usando contemporaneamente:

- `invoice_number`;
- il cliente, tenant o azienda ricavato dal contesto autenticato.

La ricerca non deve essere globale sul solo numero fattura, perché clienti differenti possono avere lo stesso numero.

### Download PDF

```http
GET /api/v1/invoices/{invoice_number}/pdf
Authorization: Bearer <access_token>
Accept: application/pdf
```

Risposta positiva:

```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="<invoice_number>.pdf"
```

Il body contiene il PDF binario.

### Download XML

```http
GET /api/v1/invoices/{invoice_number}/xml
Authorization: Bearer <access_token>
Accept: application/xml
```

Risposta positiva:

```http
HTTP/1.1 200 OK
Content-Type: application/xml
Content-Disposition: attachment; filename="<invoice_number>.xml"
```

Il body contiene l'XML binario.

### Codifica del numero fattura

Il frontend deve codificare il numero fattura con `encodeURIComponent`.

Esempio:

```text
2026/026 -> 2026%2F026
```

Se il routing o il reverse proxy non gestiscono correttamente slash codificati nei path parameter, FE e BE devono adottare insieme questa variante:

```http
GET /api/v1/invoices/download/pdf?invoice_number=2026%2F026
GET /api/v1/invoices/download/xml?invoice_number=2026%2F026
```

Non devono esistere due contratti differenti tra frontend e backend.

### Errori

Formato:

```json
{
  "detail": {
    "code": "INVOICE_NOT_FOUND",
    "message": "Invoice not found"
  }
}
```

| HTTP | Code | Significato |
|---:|---|---|
| 401 | `UNAUTHORIZED` | Sessione assente o non valida |
| 403 | `FORBIDDEN` | Accesso non consentito |
| 404 | `INVOICE_NOT_FOUND` | Fattura non trovata per il cliente autenticato |
| 409 | `INVOICE_NOT_READY` | Documento temporaneamente non disponibile |
| 422 | `INVALID_INVOICE_NUMBER` | Numero fattura non valido |
| 500 | `DOCUMENT_GENERATION_FAILED` | Generazione o lettura fallita |

### Regole funzionali

1. Il frontend invia `invoice_number`, non `invoice_id`.
2. Il backend verifica sempre proprietà e autorizzazione.
3. Se il file esiste, lo restituisce senza rigenerarlo.
4. Se il file manca, lo rigenera usando i dati persistiti nel database.
5. PDF e XML vengono salvati nella root della cartella fattura:
   - `/data/public/invoices/{invoice_id}/{nome_file}.pdf`
   - `/data/public/invoices/{invoice_id}/{nome_file}.xml`
6. Le sottocartelle `documents/` e `attachment/` restano riservate ai documenti correlati e agli allegati.
7. I nomi fisici devono essere sanitizzati contro path traversal e caratteri non validi.


## Separazione delle responsabilità

Struttura consigliata:

```text
app/
├── api/routes/invoices.py
├── services/invoice_documents/
│   ├── service.py
│   ├── pdf_generator.py
│   ├── xml_generator.py
│   ├── paths.py
│   └── exceptions.py
├── workers/invoice_documents.py
└── repositories/invoices.py
```

Il router deve occuparsi solo di validazione HTTP, dipendenze, autorizzazione e risposta. La logica di generazione deve vivere nel service.

## Entry point applicativo

Creare un unico metodo richiamabile sia dal worker sia dal flusso di download.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DocumentType = Literal["pdf", "xml"]


@dataclass(frozen=True)
class GeneratedInvoiceDocuments:
    pdf_path: Path | None
    xml_path: Path | None


class InvoiceDocumentService:
    async def generate_documents(
        self,
        *,
        invoice_id: int,
        document_types: set[DocumentType] | None = None,
        force: bool = False,
    ) -> GeneratedInvoiceDocuments:
        ...
```

Comportamento:

- recupera la fattura completa dal DB tramite `invoice_id`;
- carica tutte le relazioni necessarie;
- costruisce un DTO unico per PDF e XML;
- crea `/data/public/invoices/{invoice_id}`;
- genera entrambi i file oppure soltanto i tipi richiesti;
- con `force=False` riutilizza un file già presente e non vuoto;
- scrive prima su file temporaneo;
- sostituisce atomicamente il file definitivo;
- restituisce i path finali.

```python
requested_types = document_types or {"pdf", "xml"}
```

## DTO documentale comune

PDF e XML devono usare la stessa fotografia dei dati.

```python
@dataclass(frozen=True)
class InvoiceDocumentDTO:
    invoice_id: int
    invoice_number: str
    issue_date: date
    seller: SellerDTO
    customer: CustomerDTO
    lines: tuple[InvoiceLineDTO, ...]
    payment_details: PaymentDetailsDTO | None
    taxable_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    vat_collectability: str
```

Il DTO deve essere costruito mentre la sessione SQLAlchemy è aperta. Non passare al worker entità lazy-loaded appartenenti alla request terminata.

Nel DTO devono essere inclusi tutti i dati necessari, compresi:

- cedente/prestatore;
- cessionario/committente;
- righe fattura;
- riepiloghi IVA;
- Split Payment ed `esigibilita_iva`;
- metodo e dettagli di pagamento;
- eventuali riferimenti DDT;
- dati necessari alla conformità SDI.

## Configurazione filesystem

Centralizzare il path nelle settings.

```python
class Settings(BaseSettings):
    invoice_files_root: Path = Path("/data/public/invoices")
```

Costruzione sicura dei path:

```python
import re
from pathlib import Path


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = value.strip("._")
    return value or "invoice"


def get_invoice_directory(root: Path, invoice_id: int) -> Path:
    return root / str(invoice_id)


def get_invoice_pdf_path(
    root: Path,
    invoice_id: int,
    invoice_number: str,
) -> Path:
    name = sanitize_filename(invoice_number)
    return get_invoice_directory(root, invoice_id) / f"{name}.pdf"


def get_invoice_xml_path(
    root: Path,
    invoice_id: int,
    invoice_number: str,
) -> Path:
    name = sanitize_filename(invoice_number)
    return get_invoice_directory(root, invoice_id) / f"{name}.xml"
```

PDF e XML vanno nella root della fattura:

```text
/data/public/invoices/{invoice_id}/
├── {invoice_number_sanitized}.pdf
├── {invoice_number_sanitized}.xml
├── documents/
└── attachment/
```

## Generazione XML

Interfaccia indicativa:

```python
def build_invoice_xml(invoice: InvoiceDocumentDTO) -> bytes:
    ...
```

Requisiti:

- encoding UTF-8;
- dichiarazione XML;
- output deterministico;
- struttura compatibile con le regole SDI già adottate;
- campi Split Payment corretti;
- nessuna modifica al database;
- eccezione applicativa specifica in caso di fallimento.

Se esiste già un generatore SDI, estrarne la logica in questo servizio anziché duplicarla.

## Generazione PDF

Interfaccia indicativa:

```python
def build_invoice_pdf(invoice: InvoiceDocumentDTO) -> bytes:
    ...
```

Oppure:

```python
def render_invoice_pdf(
    invoice: InvoiceDocumentDTO,
    output_path: Path,
) -> None:
    ...
```

Il PDF deve essere coerente con l'XML per:

- numero e data;
- anagrafiche;
- righe;
- imponibile;
- IVA;
- totale;
- Split Payment;
- dettagli pagamento.

## Scrittura atomica

Non scrivere direttamente sul file definitivo.

```python
temporary_path = final_path.with_suffix(final_path.suffix + ".tmp")
temporary_path.write_bytes(content)

if not temporary_path.exists() or temporary_path.stat().st_size == 0:
    raise InvoiceDocumentGenerationError()

temporary_path.replace(final_path)
```

Questo impedisce che una GET legga un file parziale.

Se possono esserci più processi Uvicorn o più istanze, aggiungere un lock condiviso per coppia `invoice_id + document_type`. Un lock Python in memoria copre soltanto il singolo processo.

## Worker dopo la creazione

Il flusso di creazione resta:

```python
invoice = await invoice_service.create_invoice(...)
await session.commit()
await session.refresh(invoice)

response = InvoiceResponse.model_validate(invoice)

await job_dispatcher.enqueue(invoice_id=invoice.id)

return response
```

Il job deve ricevere soltanto `invoice_id`, mai la sessione o l'entità SQLAlchemy della request.

Interfaccia:

```python
class InvoiceDocumentJobDispatcher:
    async def enqueue(self, *, invoice_id: int) -> None:
        ...
```

Worker:

```python
async def generate_invoice_documents_job(invoice_id: int) -> None:
    async with session_factory() as session:
        service = build_invoice_document_service(session)
        await service.generate_documents(invoice_id=invoice_id)
```

Il worker deve:

- aprire autonomamente una nuova sessione;
- generare PDF e XML;
- essere idempotente;
- registrare log e durata;
- prevedere retry limitati;
- non modificare l'esito della fattura già creata.

## Scelta della tecnologia asincrona

Soluzione preferita: coda esterna o sistema worker già presente, per esempio SQS, Celery, RQ, Dramatiq o Arq.

Fallback iniziale FastAPI:

```python
@router.post(...)
async def create_invoice(
    ...,
    background_tasks: BackgroundTasks,
):
    invoice = await service.create(...)
    await session.commit()
    await session.refresh(invoice)

    response = InvoiceResponse.model_validate(invoice)

    background_tasks.add_task(
        generate_invoice_documents_job,
        invoice.id,
    )

    return response
```

`BackgroundTasks` parte dopo l'invio della risposta, ma:

- non sopravvive necessariamente a un riavvio;
- non offre persistenza;
- non offre retry affidabili;
- resta nello stesso processo applicativo.

Usarlo soltanto dietro l'astrazione `InvoiceDocumentJobDispatcher`, così da poterlo sostituire senza cambiare il caso d'uso.

Non usare `asyncio.create_task()` direttamente nel router come implementazione definitiva.

## Repository fatture

Creare una query limitata al cliente o tenant autenticato.

```python
async def get_by_number_for_customer(
    self,
    *,
    customer_id: int,
    invoice_number: str,
) -> Invoice | None:
    stmt = (
        select(Invoice)
        .where(
            Invoice.customer_id == customer_id,
            Invoice.invoice_number == invoice_number,
        )
    )
    return await self.session.scalar(stmt)
```

Adattare `customer_id` al modello reale:

- se rappresenta il destinatario della fattura, non è sufficiente;
- usare il vero `tenant_id`, `owner_id`, `company_id` o identificativo dell'account SaaS.

Per sicurezza, una fattura appartenente a un altro tenant può essere trattata come non trovata.

## Caso d'uso download

```python
@dataclass(frozen=True)
class InvoiceDownload:
    path: Path
    media_type: str
    download_name: str


async def get_invoice_document_for_download(
    *,
    authenticated_customer_id: int,
    invoice_number: str,
    document_type: DocumentType,
) -> InvoiceDownload:
    ...
```

Flusso:

1. validare `invoice_number`;
2. recuperare la fattura nel perimetro autenticato;
3. restituire 404 se assente;
4. calcolare il path atteso;
5. se il file non esiste o è vuoto, chiamare `generate_documents`;
6. richiedere soltanto il tipo mancante;
7. verificare nuovamente il file;
8. restituire path, MIME type e nome download.

```python
await document_service.generate_documents(
    invoice_id=invoice.id,
    document_types={document_type},
    force=False,
)
```

La rigenerazione richiesta dalla GET deve essere completata nella stessa chiamata, così il frontend riceve direttamente il file.

## Endpoint

```python
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/api/v1/invoices",
    tags=["Invoices"],
)


@router.get("/{invoice_number}/pdf")
async def download_invoice_pdf(
    invoice_number: str,
    current_customer=Depends(get_current_customer),
    service=Depends(get_invoice_download_service),
) -> FileResponse:
    result = await service.get_for_download(
        authenticated_customer_id=current_customer.id,
        invoice_number=invoice_number,
        document_type="pdf",
    )

    return FileResponse(
        path=result.path,
        media_type="application/pdf",
        filename=result.download_name,
    )


@router.get("/{invoice_number}/xml")
async def download_invoice_xml(
    invoice_number: str,
    current_customer=Depends(get_current_customer),
    service=Depends(get_invoice_download_service),
) -> FileResponse:
    result = await service.get_for_download(
        authenticated_customer_id=current_customer.id,
        invoice_number=invoice_number,
        document_type="xml",
    )

    return FileResponse(
        path=result.path,
        media_type="application/xml",
        filename=result.download_name,
    )
```

Controllare l'ordine delle route per evitare conflitti con eventuali route dinamiche `/{invoice_id}`.

## Gestione errori

Eccezioni applicative:

```python
class InvoiceNotFoundError(Exception):
    pass


class InvoiceDocumentGenerationError(Exception):
    pass
```

Mapparle al formato condiviso. Non esporre:

- path locali;
- stack trace;
- query SQL;
- errori interni di WeasyPrint, Jinja o librerie XML;
- dettagli bancari.

## Concorrenza

Caso possibile:

1. il worker post-creazione sta generando il PDF;
2. contemporaneamente arriva la GET PDF.

La soluzione deve prevedere:

- scrittura atomica;
- controllo file non vuoto;
- lock per documento;
- generazione idempotente;
- eventuale attesa breve sul lock anziché doppia scrittura.

## Logging

Registrare:

- `invoice_id`;
- tipo documento;
- origine: `post_create_worker` o `download_regeneration`;
- file riutilizzato o generato;
- durata;
- errore;
- numero tentativo del worker.

Non loggare token, XML completi o dati di pagamento sensibili.

## Test backend

### Unit test

- sanitizzazione filename;
- path PDF e XML;
- DTO completo;
- generazione PDF;
- generazione XML;
- selezione del solo file richiesto;
- riuso con `force=False`;
- rigenerazione con `force=True`;
- file temporaneo e replace;
- errore di generazione.

### Integration test

- PDF esistente: 200 e `application/pdf`;
- XML esistente: 200 e `application/xml`;
- file mancante: rigenerazione e download;
- fattura inesistente: 404;
- fattura di altro tenant: non accessibile;
- numero fattura con slash;
- doppia richiesta concorrente;
- creazione fattura non attende il generatore;
- worker con nuova sessione DB;
- errore worker non annulla la fattura.

## Criteri di accettazione

- [ ] Un solo entrypoint genera PDF e XML.
- [ ] Lo stesso entrypoint è usato da worker e download.
- [ ] Il worker parte dopo commit e risposta applicativa.
- [ ] Il worker riceve soltanto `invoice_id`.
- [ ] La risposta di creazione resta invariata.
- [ ] Le GET ricevono `invoice_number`.
- [ ] La query è limitata al tenant autenticato.
- [ ] I file mancanti vengono rigenerati.
- [ ] PDF e XML sono nella root della cartella fattura.
- [ ] I file sono restituiti con `FileResponse`.
- [ ] La scrittura è atomica.
- [ ] I nomi file sono sanitizzati.
- [ ] Esistono test di autorizzazione, rigenerazione e concorrenza.
