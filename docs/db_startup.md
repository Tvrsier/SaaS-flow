Devi implementare gli schemi utente e la base per le migrazioni DB in un backend FastAPI esistente.

## Contesto progetto

Backend Python/FastAPI per SaaS gestionale e fatturazione elettronica.

L’app FastAPI principale esiste già nel file:

```text
app/main.py
```

Per ora devi occuparti SOLO della struttura dati utente e della predisposizione DB/migrazioni, non degli endpoint completi.

---

## Stack richiesto

Usare:

- SQLAlchemy 2.x
- PostgreSQL
- psycopg v3
- Alembic per le migrazioni
- Pydantic
- FastAPI

Dipendenze attese:

```bash
pip install sqlalchemy psycopg[binary] alembic pydantic pydantic-settings python-dotenv email-validator
```

---

## Obiettivo

Generare la struttura minima ma solida per gestire utenti del SaaS.

La password NON deve essere salvata nel database.

In futuro l’autenticazione sarà gestita da AWS Cognito, quindi il DB deve già prevedere campi compatibili con autenticazione esterna.

Per ora login/register useranno una password mock letta da `.env`, ma questo verrà implementato in seguito.

---

## Struttura richiesta

Creare o integrare una struttura simile:

```text
app/
  db/
    __init__.py
    base.py
    session.py
    models/
      __init__.py
      user.py

  schemas/
    __init__.py
    user.py

  config/
    __init__.py
    settings.py

  scripts/
    migrate.py

alembic/
  env.py
  versions/

alembic.ini
```

Se il progetto ha già una struttura diversa, integrarsi senza stravolgerla.

---

## Configurazione

Creare:

```text
app/config/settings.py
```

Usare `pydantic-settings`.

Leggere almeno queste variabili:

```env
DATABASE_URL=postgresql+psycopg://dev:dev@localhost:5432/gestionale
JWT_SECRET_KEY=dev-secret
MOCK_LOGIN_PASSWORD=dev-password
ALLOW_ORIGINS=*
```

---

## SQLAlchemy Base

Creare:

```text
app/db/base.py
```

Usare `DeclarativeBase`.

Usare typing moderno SQLAlchemy 2.x:

- `Mapped`
- `mapped_column`

---

## Sessione DB

Creare:

```text
app/db/session.py
```

Implementare:

- `engine`
- `SessionLocal`
- dependency FastAPI `get_db()`

La sessione deve essere sync, non async.

---

## Modello User

Creare:

```text
app/db/models/user.py
```

Tabella:

```text
users
```

Campi richiesti:

```text
id: UUID primary key

email: string unique not null indexed
account_type: enum/string not null

first_name: string nullable
last_name: string nullable
company_name: string nullable

codice_fiscale: string nullable/indexed
partita_iva: string nullable/indexed

phone: string nullable
mobile: string nullable

profile_picture_url: string nullable

is_active: bool default true
is_verified: bool default false

external_auth_provider: string nullable
external_auth_subject: string nullable unique

accepted_terms_at: datetime nullable
accepted_privacy_at: datetime nullable

last_login_at: datetime nullable

created_at: datetime default now
updated_at: datetime default now/update
```

NON creare `password_hash`.

---

## Enum account type

Creare enum Python per:

```text
privato
libero_professionista
azienda
ditta_individuale
pubblica_amministrazione
```

L’enum deve essere utilizzabile sia lato SQLAlchemy sia lato Pydantic.

---

## Schemi Pydantic

Creare:

```text
app/schemas/user.py
```

Implementare almeno:

### UserBase

Campi comuni:

```text
email
account_type
phone
mobile
```

---

### UserCreate

Deve rappresentare il payload di registrazione frontend.

Campi:

```text
accountType
email
password
codiceFiscale
partitaIva
phone
mobile

firstName
lastName
nationality
birthDate
birthProvince
birthComune

companyName

residenceCountry
residenceProvince
residenceComune
residenceAddress
residencePostal
```

Requisiti:

- mantenere alias camelCase compatibili con frontend
- internamente usare snake_case dove possibile
- password presente SOLO nello schema request
- password NON presente nel modello DB

---

### UserLogin

Campi:

```text
email
password
```

---

### UserRead

Risposta pubblica utente:

```text
id
email
account_type
first_name
last_name
company_name
profile_picture_url
is_active
is_verified
created_at
```

Non includere dati sensibili inutili.

---

### TokenResponse

Compatibile con frontend:

```json
{
  "access_token": "...",
  "user": {}
}
```

---

## Validazioni minime

Implementare validazioni Pydantic base:

- email valida
- password minimo 8 caratteri
- account_type obbligatorio
- se account_type è:
  - `privato`
  - `libero_professionista`
  - `ditta_individuale`

  richiedere:
  - `firstName`
  - `lastName`

- se account_type è:
  - `azienda`
  - `pubblica_amministrazione`

  richiedere:
  - `companyName`

- `codiceFiscale` obbligatorio
- `partitaIva` opzionale SOLO per `privato`

NON implementare validazioni fiscali avanzate ora.

---

## Alembic

Configurare Alembic correttamente.

Obiettivi:

- `alembic.ini` usa DATABASE_URL da env/config
- `alembic/env.py` importa Base SQLAlchemy e modelli
- autogenerate funzionante

Creare una prima migration per la tabella `users`.

---

## Script migrazioni

Creare:

```text
app/scripts/migrate.py
```

Deve supportare:

```bash
python -m app.scripts.migrate revision "create users table"
python -m app.scripts.migrate upgrade
python -m app.scripts.migrate downgrade
python -m app.scripts.migrate current
python -m app.scripts.migrate history
```

Comportamento richiesto:

- `revision "<message>"`
  - esegue:
    ```bash
    alembic revision --autogenerate -m "<message>"
    ```

- `upgrade`
  - esegue:
    ```bash
    alembic upgrade head
    ```

- `downgrade`
  - esegue:
    ```bash
    alembic downgrade -1
    ```

- `current`
  - esegue:
    ```bash
    alembic current
    ```

- `history`
  - esegue:
    ```bash
    alembic history
    ```

Gestire errori in modo leggibile.

---

## Qualità codice

- usare type hints
- usare import assoluti
- codice semplice e leggibile
- compatibile Python 3.12+
- niente logica auth completa ora
- niente Cognito ora
- niente password nel DB
- evitare hardcoded inutili

---

## Output atteso

Alla fine mostra:

1. struttura file creata
2. dipendenze richieste
3. esempio `.env`
4. comandi per creare/applicare migration
5. note per futura integrazione login/register e Cognito

---

## Note
Ignora il contenuto di app/modules/invoices. Non è collegato direttamente a questa parte di progetto, 
contiene codice relativo alla fatturazione.
Leggi il file .env per la configurazione a DB