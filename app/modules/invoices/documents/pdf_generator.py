from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from app.modules.invoices.documents.dto import InvoiceDocumentDTO
from app.modules.invoices.documents.exceptions import InvoiceDocumentGenerationError


def build_invoice_pdf(invoice: InvoiceDocumentDTO) -> bytes:
    try:
        image = Image.new("RGB", (1240, 1754), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=22)
        title_font = ImageFont.load_default(size=34)
        y = 70

        def row(text: str, *, title: bool = False, gap: int = 42) -> None:
            nonlocal y
            safe_text = text.encode("latin-1", "replace").decode("latin-1")
            draw.text((70, y), safe_text, fill="black", font=title_font if title else font)
            y += gap

        row(f"FATTURA {invoice.invoice_number}", title=True, gap=58)
        row(f"Data: {invoice.issue_date.isoformat()}")
        row(f"Cedente: {invoice.seller.name}")
        row(f"P.IVA/CF: {invoice.seller.vat_number or invoice.seller.tax_code or '-'}")
        row(f"Cliente: {invoice.customer.name}")
        row(f"P.IVA/CF: {invoice.customer.vat_number or invoice.customer.tax_code or '-'}", gap=62)
        row("Righe", title=True, gap=50)
        for line in invoice.lines:
            row(f"{line.number}. {line.description[:65]}")
            row(f"   {line.quantity} x {line.unit_price:.2f}  IVA {line.vat_rate:.2f}%  = {line.taxable_amount:.2f}")
        y += 25
        row(f"Imponibile: {invoice.taxable_amount:.2f} {invoice.currency}")
        row(f"IVA: {invoice.vat_amount:.2f} {invoice.currency}")
        row(f"Totale: {invoice.total_amount:.2f} {invoice.currency}", title=True, gap=55)
        row(f"Esigibilita IVA: {invoice.vat_collectability}")
        if invoice.payment_details:
            row(f"Pagamento: {invoice.payment_details.method}")
            if invoice.payment_details.iban:
                row(f"IBAN: {invoice.payment_details.iban}")

        output = BytesIO()
        image.save(output, format="PDF", resolution=150.0)
        content = output.getvalue()
        if not content.startswith(b"%PDF"):
            raise ValueError("invalid PDF output")
        return content
    except Exception as exc:
        raise InvoiceDocumentGenerationError("PDF generation failed") from exc
