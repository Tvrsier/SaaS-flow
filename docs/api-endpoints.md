# API Endpoints — Documentazione centralizzata

Questo documento descrive le API che il backend deve esporre e i contratti request/response che il frontend si aspetta. L’obiettivo è allineare payload, token, errori e dati minimi necessari per login, registrazione, refresh sessione e flussi principali.

Nota: il frontend costruisce gli URL usando `src/lib/api.ts` (`buildUrl`, `ENDPOINTS`, `apiGet`, `apiPost`). A seconda delle env Vite, le chiamate saranno fatte verso `/api/...` (quando `VITE_USE_PROXY=true` o modalità `local-ngrok`) oppure verso `<protocol>://<host>:<port>/...`.

---

## Convenzioni generali
- Variabili di ambiente usate dal frontend:
  - `VITE_ENV_TYPE` = `local-mocked` | `local` | `local-ngrok` | `test` | `prod`
  - `VITE_API_HOST`, `VITE_API_PORT`, `VITE_API_PROTOCOL`, `VITE_USE_PROXY`
- Quando si usa il proxy (Vite) le chiamate del frontend puntano a `/api/<path>` e Vite le inoltra al backend (configurato in `vite.config.ts`).
- I nomi degli endpoint sono definiti in `src/lib/api.ts` come `ENDPOINTS.<name>`.
- I metodi helper del frontend sono `apiGet<T>(path, query?, token?)` e `apiPost<T>(path, body?, token?)`.
- Modalità `local-mocked` (`VITE_ENV_TYPE=local-mocked`) attiva i mock locali; il backend non viene chiamato.

---

## Contratto di autenticazione
Il backend deve supportare un contratto uniforme per login, registrazione e refresh sessione:
- Token di autenticazione da restituire in uno dei campi supportati dal frontend:
  - `access_token` (preferito)
  - `token`
  - `accessToken`
  - `auth_token`
- Oggetto utente minimale nella response, utile per dashboard e refresh local storage.
- In caso di errore, il backend deve restituire JSON con almeno `message` e, se necessario, `errors` per campo.

---

## ENDPOINTS (mappa e scopo)
- `authLogin: "/auth/login"` — Login utente
- `authRegister: "/auth/register"` — Registrazione nuovo utente
- `authMe: "/auth/me"` — Profilo utente corrente / refresh sessione
- `invoices: "/invoices"` — Lista e creazione fatture
- `documentsUpload: "/documents/upload"` — Upload documenti (multipart/form-data)
- `delegations: "/delegations"` — Liste/creazione deleghe
- `invoicesSend: "/invoices/send"` — Invio fattura (email/PEC)

Per i path effettivi il client usa `buildUrl(ENDPOINTS.xxx, query?)`.

---

## 1) Login — POST `/auth/login`
- Scopo: autenticare l’utente e restituire token + dati minimi utente.

Request
- Metodo: POST
- Header: `Content-Type: application/json`
- Body (JSON):
  - `{ "email": string, "password": string }`

Response attesa
- Successo: `200 OK`
- Body JSON suggerito:
  ```json
  {
    "access_token": "jwt-or-token",
    "user": {
      "name": "Mario",
      "surname": "Rossi",
      "email": "mario@example.com",
      "companyName": "Atlas S.r.l.",
      "partitaIva": "12345678901",
      "codiceFiscale": "RSSMRA80A01H501U",
      "phone": "+390612345678"
    }
  }
  ```
- È accettato anche un payload con solo token:
  ```json
  { "access_token": "jwt-or-token" }
  ```
  In questo caso il frontend effettua `GET /auth/me` per caricare il profilo.

Errori da restituire
- `400 Bad Request` — payload mancante o non valido
  - esempio: `{ "message": "Invalid payload", "errors": { "email": ["required"] } }`
- `401 Unauthorized` — credenziali errate
  - esempio: `{ "message": "Invalid credentials" }`
- `403 Forbidden` — account bloccato/non verificato (se applicabile)
  - esempio: `{ "message": "Account not active" }`
- `500 Internal Server Error` — errore backend generico

---

## 2) Registrazione — POST `/auth/register`
- Scopo: creare un nuovo account e restituire token + dati minimi utente.

Request
- Metodo: POST
- Header: `Content-Type: application/json`
- Body (JSON) — campi comuni:
  ```json
  {
    "accountType": "privato",
    "email": "string",
    "password": "string",
    "codiceFiscale": "string",
    "partitaIva": "string | null",
    "phone": "string | null",
    "mobile": "string | null"
  }
  ```
- Campi aggiuntivi per persone fisiche (`privato`, `ditta_individuale`, `libero_professionista`):
  ```json
  {
    "firstName": "string",
    "lastName": "string",
    "nationality": "string",
    "birthDate": "YYYY-MM-DD",
    "birthProvince": "string",
    "birthComune": "string"
  }
  ```
- Campi aggiuntivi per aziende / PA:
  ```json
  {
    "companyName": "string",
    "residenceCountry": "string",
    "residenceProvince": "string",
    "residenceComune": "string",
    "residenceAddress": "string",
    "residencePostal": "string"
  }
  ```

Response attesa
- Successo: `201 Created` o `200 OK`
- Body JSON suggerito:
  ```json
  {
    "access_token": "jwt-or-token",
    "user": {
      "name": "Mario",
      "surname": "Rossi",
      "email": "mario@example.com",
      "companyName": "Atlas S.r.l.",
      "partitaIva": "12345678901",
      "codiceFiscale": "RSSMRA80A01H501U",
      "phone": "+390612345678"
    }
  }
  ```
- Deve essere accettato anche un payload con solo token:
  ```json
  { "access_token": "jwt-or-token" }
  ```

Errori da restituire
- `400 Bad Request` — payload mancante o campi obbligatori assenti
  - esempio: `{ "message": "Invalid payload", "errors": { "email": ["required"] } }`
- `409 Conflict` — email già registrata / account duplicato
  - esempio: `{ "message": "Email already in use" }`
- `422 Unprocessable Entity` — validazione business (CF/P.IVA/campi specifici)
  - esempio: `{ "message": "Validation failed", "errors": { "codiceFiscale": ["format invalid"] } }`
- `500 Internal Server Error` — errore backend generico

---

## 3) Profilo utente / refresh sessione — GET `/auth/me`
- Scopo: restituire il profilo minimale dell’utente autenticato.
- Questo endpoint viene usato dal frontend per ricaricare i dati quando esiste già un token.

Request
- Metodo: GET
- Header: `Authorization: Bearer <token>`

Response attesa
- Successo: `200 OK`
- Body JSON minimale suggerito:
  ```json
  {
    "name": "Mario",
    "surname": "Rossi",
    "email": "mario@example.com",
    "companyName": "Atlas S.r.l.",
    "partitaIva": "12345678901",
    "codiceFiscale": "RSSMRA80A01H501U",
    "phone": "+390612345678"
  }
  ```

Errori da restituire
- `401 Unauthorized` — token mancante/scaduto/non valido
  - esempio: `{ "message": "Unauthorized" }`
- `403 Forbidden` — token valido ma non autorizzato per la risorsa
  - esempio: `{ "message": "Forbidden" }`
- `500 Internal Server Error` — errore backend generico

---

## 4) Lista fatture — GET `/invoices`
- Scopo: ottenere elenco fatture con supporto a query (paginazione, filtri).

Request
- Metodo: GET
- Query params opzionali: `page`, `perPage`, `q`, `status`, `dateFrom`, `dateTo`, ecc.
- Header: `Authorization: Bearer <token>`

Response attesa
- `200 OK`
- Il backend può restituire un array semplice oppure un wrapper paginato.
- Contratto di riferimento: `docs/invoices.get.schema.json`
- Esempio wrapper:
  ```json
  {
    "data": [
      { "id": "INV-1", "client": "Demo", "date": "2025-01-01", "amount": 100, "status": "draft" }
    ],
    "page": 1,
    "perPage": 20,
    "total": 1,
    "last_invoice_number": "2026-001"
  }
  ```

Errori da restituire
- `401 Unauthorized`, `403 Forbidden`
- `422 Unprocessable Entity` — query non valida
- `500 Internal Server Error`

---

## 5) Creazione fattura — POST `/invoices`
- Scopo: creare una nuova fattura.

Request
- Metodo: POST
- Header: `Content-Type: application/json`, `Authorization: Bearer <token>`
- Body: oggetto fattura secondo il contratto `docs/invoices.post.schema.json`
- Campi chiave che il backend deve validare:
  - `mode`
  - `invoiceNumber`
  - `issueDate`
  - `currency`
  - `documentType`
  - `client`
  - `lines`
  - `subtotal`
  - `vatTotal`
  - `total`
  - `attachments` opzionale

Response attesa
- `201 Created` o `200 OK`
- Restituisce la fattura creata con `id` e dati normalizzati.
- Il payload di risposta può essere strutturato in modo esteso purché includa almeno l’identificativo e i valori principali appena creati.

Errori da restituire
- `400 Bad Request` / `422 Unprocessable Entity` — validazione fallita
- `401 Unauthorized` / `403 Forbidden`
- `500 Internal Server Error`

---

## 6) Invio fattura — POST `/invoices/send`
- Scopo: inviare una fattura via email/PEC/altro.

Request
- Metodo: POST
- Header: `Content-Type: application/json`, `Authorization: Bearer <token>`
- Body suggerito:
  ```json
  {
    "invoiceId": "string",
    "recipients": ["string"],
    "method": "email",
    "message": "string (opzionale)"
  }
  ```
- `recipients` può essere gestito dal backend anche come singola stringa, ma l’esempio mantiene la forma array per restare JSON valido.
- `method` accetta `email` o `pec`.

Response attesa
- `200 OK`
  - `{ "success": true, ... }`

Errori da restituire
- `400 Bad Request` — invoiceId/destinatari mancanti o invalidi
- `404 Not Found` — fattura non trovata
- `500 Internal Server Error` — errore invio (SMTP/PEC)

---

## 7) Upload documenti — POST `/documents/upload`
- Scopo: upload file/documenti.

Request
- Metodo: POST
- Header: `multipart/form-data`
- Body: `FormData` con chiavi come `file`, `name`, `category`, `tags`, `expires`

Response attesa
- `201 Created` o `200 OK`
- Esempio:
  ```json
  {
    "id": "DOC-1",
    "filename": "documento.pdf",
    "url": "https://...",
    "category": "other",
    "tags": ["..." ]
  }
  ```

Errori da restituire
- `400 Bad Request` — file mancante o campi mancanti
- `413 Payload Too Large` — file troppo grande
- `415 Unsupported Media Type` — tipo file non permesso
- `500 Internal Server Error`

---

## 8) Delegations — GET/POST `/delegations`
- Scopo: gestire deleghe (elenco e creazione).

Request
- GET: lista deleghe
- POST: creazione delega; body JSON con i campi richiesti dal dominio

Response attesa
- GET `200 OK`
- POST `201 Created`

Errori da restituire
- `400 Bad Request` / `422 Unprocessable Entity` — validazione
- `401 Unauthorized` / `403 Forbidden`
- `500 Internal Server Error`

---

## Error handling consigliato per il frontend
- `400/422`: mostrare messaggio di validazione e, se presente, mappare `errors` per campo.
- `401`: token mancante/scaduto/non valido, pulizia sessione e redirect login.
- `403`: utente autenticato ma non autorizzato.
- `404`: risorsa non trovata.
- `409`: conflitto business, es. email già registrata.
- `500`: errore generico backend.

---

## Note di contratto richieste al backend
- Restituire sempre JSON con almeno `message` sugli errori.
- Preferire `access_token` nelle risposte auth.
- `auth/me` deve essere coerente con login/register e restituire dati minimali utili al frontend.
- Per autenticazione e autorizzazione, il backend deve considerare il token come fonte di verità.

---

## Come estendere i mock
1. Creare `src/mocks/auth.ts`, `src/mocks/invoices.ts`, `src/mocks/documents.ts`, ecc.
2. In `src/lib/api.ts` sostituire i return mock attuali con import dinamici/consistenti dalle cartelle mocks.
3. Aggiungere delays artificiali con `await new Promise(r => setTimeout(r, ms))` per testare loading states.

---

Se vuoi, posso anche trasformare questo documento in una tabella per endpoint con colonne `Metodo`, `Request`, `Response`, `Errori`, `Note`, così diventa ancora più leggibile per il backend.
