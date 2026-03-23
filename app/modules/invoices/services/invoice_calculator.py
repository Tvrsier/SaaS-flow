from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple

from app.modules.invoices.domain.enums import NatureCode
from app.modules.invoices.schemas.request import InvoiceCreatePayload, InvoiceLinePayload


TWOPLACES = Decimal("0.01")
ONE_HUNDRED = Decimal("100.00")
ZERO = Decimal("0.00")


def money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass(slots=True, frozen=True)
class CalculatedInvoiceLine:
    line_number: int
    name: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    vat_rate: Decimal
    nature: NatureCode | None
    taxable_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal


@dataclass(slots=True, frozen=True)
class CalculatedVatSummary:
    vat_rate: Decimal
    nature: NatureCode | None
    taxable_amount: Decimal
    tax_amount: Decimal


@dataclass(slots=True, frozen=True)
class CalculatedInvoiceTotals:
    lines: list[CalculatedInvoiceLine]
    vat_summaries: list[CalculatedVatSummary]
    subtotal: Decimal
    total_tax: Decimal
    stamp_duty: Decimal
    grand_total: Decimal


class InvoiceCalculator:
    def calculate(self, invoice: InvoiceCreatePayload) -> CalculatedInvoiceTotals:
        calculated_lines: list[CalculatedInvoiceLine] = []

        vat_groups: Dict[Tuple[Decimal, NatureCode | None], Dict[str, Decimal]] = {}

        for item in invoice.items:
            calculated_line = self._calculate_line(item)
            calculated_lines.append(calculated_line)

            group_key = (calculated_line.vat_rate, calculated_line.nature)

            if group_key not in vat_groups:
                vat_groups[group_key] = {
                    "taxable_amount": ZERO,
                    "tax_amount": ZERO,
                }

            vat_groups[group_key]["taxable_amount"] = money(
                vat_groups[group_key]["taxable_amount"] + calculated_line.taxable_amount
            )
            vat_groups[group_key]["tax_amount"] = money(
                vat_groups[group_key]["tax_amount"] + calculated_line.tax_amount
            )

        vat_summaries = [
            CalculatedVatSummary(
                vat_rate=vat_rate,
                nature=nature,
                taxable_amount=money(values["taxable_amount"]),
                tax_amount=money(values["tax_amount"]),
            )
            for (vat_rate, nature), values in sorted(
                vat_groups.items(),
                key=lambda entry: (entry[0][0], entry[0][1].value if entry[0][1] else "")
            )
        ]

        subtotal = money(sum((line.taxable_amount for line in calculated_lines), ZERO))
        total_tax = money(sum((summary.tax_amount for summary in vat_summaries), ZERO))
        stamp_duty = money(invoice.stamp_duty.amount if invoice.stamp_duty.enabled else ZERO)
        grand_total = money(subtotal + total_tax + stamp_duty)

        return CalculatedInvoiceTotals(
            lines=calculated_lines,
            vat_summaries=vat_summaries,
            subtotal=subtotal,
            total_tax=total_tax,
            stamp_duty=stamp_duty,
            grand_total=grand_total,
        )

    @staticmethod
    def _calculate_line(item: InvoiceLinePayload) -> CalculatedInvoiceLine:
        discount_multiplier = Decimal("1.00") - (item.discount_percent / ONE_HUNDRED)
        discounted_unit_price = money(item.unit_price * discount_multiplier)
        taxable_amount = money(discounted_unit_price * item.quantity)

        if item.vat_rate == ZERO:
            tax_amount = ZERO
        else:
            tax_amount = money(taxable_amount * (item.vat_rate / ONE_HUNDRED))

        total_amount = money(taxable_amount + tax_amount)

        return CalculatedInvoiceLine(
            line_number=item.line_number,
            name=item.name,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount_percent=item.discount_percent,
            vat_rate=item.vat_rate,
            nature=item.nature,
            taxable_amount=taxable_amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
        )

