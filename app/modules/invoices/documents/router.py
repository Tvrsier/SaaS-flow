from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.session import get_db
from app.modules.auth.router import get_current_user
from app.modules.invoices.documents.exceptions import InvalidInvoiceNumberError, InvoiceDocumentGenerationError, InvoiceNotFoundError
from app.modules.invoices.documents.service import DocumentType, InvoiceDocumentService

router = APIRouter(prefix="/api/v1/invoices", tags=["Invoices"])


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def _download(
    invoice_number: str,
    document_type: DocumentType,
    current_user: User,
    db: Session,
) -> FileResponse:
    try:
        result = await InvoiceDocumentService(db).get_for_download(
            authenticated_company_id=UUID(str(current_user.id)),
            invoice_number=invoice_number,
            document_type=document_type,
        )
        return FileResponse(path=result.path, media_type=result.media_type, filename=result.download_name)
    except InvalidInvoiceNumberError as exc:
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "INVALID_INVOICE_NUMBER", "Invalid invoice number") from exc
    except InvoiceNotFoundError as exc:
        raise _error(status.HTTP_404_NOT_FOUND, "INVOICE_NOT_FOUND", "Invoice not found") from exc
    except InvoiceDocumentGenerationError as exc:
        raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DOCUMENT_GENERATION_FAILED", "Document generation failed") from exc


# The path converter intentionally supports encoded invoice numbers containing '/'.
@router.get("/{invoice_number:path}/pdf", response_class=FileResponse)
async def download_invoice_pdf(
    invoice_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    return await _download(invoice_number, "pdf", current_user, db)


@router.get("/{invoice_number:path}/xml", response_class=FileResponse)
async def download_invoice_xml(
    invoice_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    return await _download(invoice_number, "xml", current_user, db)

