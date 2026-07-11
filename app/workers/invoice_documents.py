from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from fastapi import BackgroundTasks

from app.db.session import SessionLocal
from app.modules.invoices.documents.service import InvoiceDocumentService

logger = logging.getLogger("GestPro")
MAX_ATTEMPTS = 3


async def generate_invoice_documents_job(invoice_id: UUID) -> None:
    started = time.monotonic()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with SessionLocal() as session:
                service = InvoiceDocumentService(session)
                await service.generate_documents(invoice_id=invoice_id, origin="post_create_worker")
            logger.info("invoice_document worker_complete invoice_id=%s attempt=%d duration_ms=%d", invoice_id, attempt, int((time.monotonic() - started) * 1000))
            return
        except Exception:
            logger.exception("invoice_document worker_error invoice_id=%s attempt=%d", invoice_id, attempt)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(0.1 * attempt)


class InvoiceDocumentJobDispatcher:
    """Replaceable adapter around FastAPI's initial in-process background queue."""

    def __init__(self, background_tasks: BackgroundTasks):
        self.background_tasks = background_tasks

    def enqueue(self, *, invoice_id: UUID) -> None:
        self.background_tasks.add_task(generate_invoice_documents_job, invoice_id)
