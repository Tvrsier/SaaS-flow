from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.modules.auth.router import get_current_user
from app.modules.invoices.schemas.api import ClientsListResponse, InvoiceCreateRequest, InvoiceRead, InvoicesListResponse
from app.modules.invoices.services.invoice_service import InvoiceService


router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    invoice_form_test: str | None = Header(default=None, alias="Invoice-Form-Test"),
) -> InvoiceRead:
    service = InvoiceService(db)
    return service.create_invoice(current_user, payload, invoice_form_test=invoice_form_test)


@router.get("", response_model=InvoicesListResponse)
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int | None = Query(default=None, ge=1),
    per_page: int | None = Query(default=None, alias="perPage", ge=1),
) -> InvoicesListResponse:
    service = InvoiceService(db)
    return service.list_invoices(current_user, page=page, per_page=per_page)


@router.get("/clients", response_model=ClientsListResponse)
def list_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    q: str | None = Query(default=None, min_length=1, max_length=255),
) -> ClientsListResponse:
    service = InvoiceService(db)
    return service.list_clients(current_user, q=q)
