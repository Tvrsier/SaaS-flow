# Change request BE — Dati di pagamento emittente

## Obiettivo

Persistire i profili di pagamento dell'utente emittente, restituirli tramite auth e accettare uno snapshot dei dati di pagamento nella creazione/modifica della fattura.

I dati di pagamento non devono essere associati al `Client`: sono informazioni dell'utente/azienda che emette la fattura.


## Contratto condiviso FE/BE

> Terminologia vincolante: i dati di pagamento appartengono all'**utente/azienda emittente**, non al cliente destinatario della fattura.

### Nomi API (camelCase)

```ts
type PaymentDetails = {
  beneficiary?: string | null;
  financialInstitution?: string | null;
  iban?: string | null;
  abi?: string | null;
  cab?: string | null;
  bic?: string | null;
  paymentCode?: string | null;
  postalOfficeCode?: string | null;
};
```

### Nomi database/backend (snake_case)

| API | Backend/DB | FatturaPA |
|---|---|---|
| `beneficiary` | `beneficiary` | `Beneficiario` |
| `financialInstitution` | `financial_institution` | `IstitutoFinanziario` |
| `iban` | `iban` | `IBAN` |
| `abi` | `abi` | `ABI` |
| `cab` | `cab` | `CAB` |
| `bic` | `bic` | `BIC` |
| `paymentCode` | `payment_code` | `CodicePagamento` |
| `postalOfficeCode` | `postal_office_code` | `CodUfficioPostale` |

Non introdurre sinonimi come `bankName`, `swift`, `holderName`, `paymentReference` o `iuv` nel contratto pubblico. Eventuali etichette UI possono essere più descrittive, ma la proprietà trasmessa deve restare quella indicata sopra.

### Matrice dei campi mostrati

| Metodo | Campi mostrati | Campi obbligatori nell'app |
|---|---|---|
| `MP05` Bonifico | beneficiary, financialInstitution, iban, abi, cab, bic, paymentCode | beneficiary, iban |
| `MP11` Ri.Ba. | financialInstitution, abi, cab, paymentCode | paymentCode |
| `MP12` MAV | financialInstitution, paymentCode | paymentCode |
| `MP18` Bollettino c/c postale | postalOfficeCode, paymentCode | paymentCode |
| `MP19` SDD FAST | beneficiary, iban, bic, paymentCode | iban, paymentCode |
| `MP20` SDD B2B | beneficiary, iban, bic, paymentCode | iban, paymentCode |
| `MP23` PagoPA | paymentCode | paymentCode |
| Tutti gli altri | nessun campo aggiuntivo nell'MVP | nessuno |

`paymentCode` rappresenta il riferimento/codice necessario allo specifico pagamento. Per PagoPA la UI può etichettarlo come “IUV / codice avviso”, mantenendo però `paymentCode` nel payload.


## 1. Modello dati consigliato

Non aggiungere tutti i campi direttamente a `users`. Creare una tabella dedicata, perché un utente può configurare più metodi di pagamento.

```python
class UserPaymentProfile(Base):
    __tablename__ = "user_payment_profiles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "payment_method",
            name="uq_user_payment_profiles_user_method",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        SAEnum(PaymentMethod, name="payment_method"),
        nullable=False,
    )

    beneficiary: Mapped[str | None] = mapped_column(String(200))
    financial_institution: Mapped[str | None] = mapped_column(String(200))
    iban: Mapped[str | None] = mapped_column(String(34))
    abi: Mapped[str | None] = mapped_column(String(5))
    cab: Mapped[str | None] = mapped_column(String(5))
    bic: Mapped[str | None] = mapped_column(String(11))
    payment_code: Mapped[str | None] = mapped_column(String(60))
    postal_office_code: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="payment_profiles")
```

Estendere `User`:

```python
payment_profiles: Mapped[list["UserPaymentProfile"]] = relationship(
    back_populates="user",
    cascade="all, delete-orphan",
)
```

Creare una migration Alembic con tabella, foreign key, indice e unique constraint.

## 2. Snapshot sulla fattura

I dati usati per una fattura devono essere salvati come snapshot e non letti dinamicamente dal profilo dopo la creazione.

Creare una tabella one-to-one:

```python
class InvoicePaymentDetails(Base):
    __tablename__ = "invoice_payment_details"

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        primary_key=True,
    )

    beneficiary: Mapped[str | None] = mapped_column(String(200))
    financial_institution: Mapped[str | None] = mapped_column(String(200))
    iban: Mapped[str | None] = mapped_column(String(34))
    abi: Mapped[str | None] = mapped_column(String(5))
    cab: Mapped[str | None] = mapped_column(String(5))
    bic: Mapped[str | None] = mapped_column(String(11))
    payment_code: Mapped[str | None] = mapped_column(String(60))
    postal_office_code: Mapped[str | None] = mapped_column(String(20))
```

Aggiungere la relazione one-to-one su `Invoice`.

La modalità di pagamento resta nel campo già esistente della fattura. Non duplicare `payment_method` nella tabella snapshot.

## 3. Schemi Pydantic condivisi

```python
class PaymentDetailsPayload(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
    )

    beneficiary: str | None = Field(default=None, max_length=200)
    financial_institution: str | None = Field(
        default=None,
        alias="financialInstitution",
        max_length=200,
    )
    iban: str | None = Field(default=None, max_length=34)
    abi: str | None = Field(default=None, pattern=r"^\d{5}$")
    cab: str | None = Field(default=None, pattern=r"^\d{5}$")
    bic: str | None = Field(default=None, max_length=11)
    payment_code: str | None = Field(
        default=None,
        alias="paymentCode",
        max_length=60,
    )
    postal_office_code: str | None = Field(
        default=None,
        alias="postalOfficeCode",
        max_length=20,
    )
```

Normalizzare:

- stringa vuota → `None`;
- IBAN → uppercase e senza spazi;
- BIC → uppercase;
- ABI/CAB → solo 5 cifre quando valorizzati.

## 4. Registrazione e profili utente

Estendere la request di registrazione con:

```python
payment_profiles: list[UserPaymentProfileCreate] = Field(
    default_factory=list,
    alias="paymentProfiles",
)
```

`UserPaymentProfileCreate` deve estendere `PaymentDetailsPayload` e aggiungere:

```python
payment_method: PaymentMethod = Field(alias="paymentMethod")
```

Durante la registrazione:

- i profili sono opzionali;
- rifiutare metodi duplicati;
- validare solo i campi valorizzati;
- non richiedere i campi obbligatori per fattura, perché la registrazione deve poter essere completata anche con profili incompleti o assenti.

Prevedere successivamente endpoint CRUD dedicati, evitando di dipendere dalla sola registrazione:

```text
GET    /users/me/payment-profiles
POST   /users/me/payment-profiles
PUT    /users/me/payment-profiles/{paymentMethod}
DELETE /users/me/payment-profiles/{paymentMethod}
```

## 5. Contratto `/auth/me`

Estendere `AuthMeResponse`:

```python
class UserPaymentProfileResponse(PaymentDetailsPayload):
    payment_method: PaymentMethod = Field(alias="paymentMethod")


class AuthMeResponse(BaseModel):
    # campi esistenti
    payment_profiles: list[UserPaymentProfileResponse] = Field(
        default_factory=list,
        alias="paymentProfiles",
    )
```

Aggiornare `_me_payload`:

```python
def _me_payload(user: User) -> AuthMeResponse:
    logger.debug("Building /auth/me payload for email=%s", user.email)

    return AuthMeResponse(
        name=user.first_name or user.company_name,
        surname=user.last_name,
        email=user.email,
        companyName=user.company_name,
        partitaIva=user.partita_iva,
        codiceFiscale=user.codice_fiscale,
        phone=user.phone,
        paymentProfiles=[
            UserPaymentProfileResponse.model_validate(profile)
            for profile in user.payment_profiles
        ],
    )
```

Assicurarsi che la query auth carichi `payment_profiles` senza N+1, ad esempio con `selectinload(User.payment_profiles)`.

## 6. Estensione `InvoiceCreateRequest`

Aggiungere:

```python
payment_details: PaymentDetailsPayload | None = Field(
    default=None,
    alias="paymentDetails",
)
```

Contratto finale rilevante:

```python
class InvoiceCreateRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
    )

    # campi esistenti
    payment_method: PaymentMethod = Field(alias="paymentMethod")
    payment_details: PaymentDetailsPayload | None = Field(
        default=None,
        alias="paymentDetails",
    )
```

Non recuperare automaticamente i dati dal profilo durante la POST della fattura: il frontend invia lo snapshot effettivamente confermato dall'utente. Il backend deve validarlo e salvarlo.

## 7. Validazione condizionale fattura

Nel `model_validator(mode="after")` validare la combinazione `payment_method` + `payment_details`.

Regole:

```python
REQUIRED_PAYMENT_FIELDS: dict[PaymentMethod, tuple[str, ...]] = {
    PaymentMethod.MP05: ("beneficiary", "iban"),
    PaymentMethod.MP11: ("payment_code",),
    PaymentMethod.MP12: ("payment_code",),
    PaymentMethod.MP18: ("payment_code",),
    PaymentMethod.MP19: ("iban", "payment_code"),
    PaymentMethod.MP20: ("iban", "payment_code"),
    PaymentMethod.MP23: ("payment_code",),
}
```

Comportamento:

- metodo senza campi aggiuntivi: accettare `paymentDetails = null`;
- metodo presente nella matrice: richiedere `paymentDetails`;
- rifiutare i campi obbligatori mancanti;
- ignorare mai silenziosamente dati incoerenti;
- per metodi senza campi aggiuntivi, preferire errore se vengono inviati dettagli non vuoti, così da intercettare bug FE.

Mantenere questa matrice in un modulo condiviso nel backend ed esportare, se possibile, una configurazione API per evitare divergenze con il frontend.

## 8. Salvataggio fattura

Nella stessa transazione che crea `Invoice`:

1. creare la fattura;
2. effettuare `flush()` per ottenere `invoice.id`;
3. se `payment_details` non è `None`, creare `InvoicePaymentDetails`;
4. proseguire con righe, allegati e movimenti IVA;
5. effettuare un unico commit finale.

In aggiornamento:

- sostituire lo snapshot esistente con i dati ricevuti;
- eliminare lo snapshot se il nuovo metodo non richiede dettagli;
- non modificare `UserPaymentProfile`.

## 9. Serializzazione FatturaPA

Quando viene generato l'XML:

- `payment_method` → `ModalitaPagamento`;
- i campi dello snapshot → tag omonimi indicati nella tabella condivisa;
- omettere i tag con valore `None`;
- non leggere i dati correnti dal profilo utente;
- usare esclusivamente lo snapshot della fattura.

## 10. Test BE richiesti

- migration applicabile e reversibile;
- registrazione senza profili;
- registrazione con profilo MP05;
- rifiuto di due profili con stesso metodo;
- `/auth/me` restituisce `paymentProfiles: []` se assenti;
- `/auth/me` restituisce i nomi camelCase corretti;
- creazione MP05 senza `paymentDetails` → 422;
- creazione MP05 senza IBAN → 422;
- creazione MP05 valida → snapshot persistito;
- creazione MP01 con `paymentDetails: null` → successo;
- creazione MP01 con dettagli valorizzati → 422;
- MP23 richiede `paymentCode`;
- modifica profilo utente non altera fatture già create;
- generazione XML usa lo snapshot della fattura;
- update fattura da MP05 a MP01 elimina lo snapshot;
- normalizzazione IBAN/BIC/ABI/CAB.
