from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = value.strip("._")
    return value or "invoice"


def get_invoice_directory(root: Path, invoice_id: UUID) -> Path:
    return root / str(invoice_id)


def get_invoice_pdf_path(root: Path, invoice_id: UUID, invoice_number: str) -> Path:
    return get_invoice_directory(root, invoice_id) / f"{sanitize_filename(invoice_number)}.pdf"


def get_invoice_xml_path(root: Path, invoice_id: UUID, invoice_number: str) -> Path:
    return get_invoice_directory(root, invoice_id) / f"{sanitize_filename(invoice_number)}.xml"
