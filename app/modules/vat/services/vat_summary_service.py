"""VAT Summary Service"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal, TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.invoice import VatMovement, VatPeriod, VatSettlement

logger = logging.getLogger("GestPro")

PaymentStatus = Literal["UNPAID", "PARTIALLY_PAID", "PAID", "OVERPAID"]


class PeriodSummary(TypedDict):
    total_debit: Decimal
    total_credit: Decimal
    previous_credit: Decimal
    balance: Decimal
    amount_to_pay: Decimal
    credit_to_carry: Decimal


class VatSummaryService:
    def __init__(self, db: Session):
        self.db = db

    def calculate_period_summary(self, company_id: UUID, period_id: UUID) -> PeriodSummary:
        """
        Calculate VAT summary for a period.

        Args:
            company_id: Company UUID
            period_id: Period UUID

        Returns:
            PeriodSummary dict with calculations

        Raises:
            ValueError: If period not found
        """
        # Get period
        period = self.db.get(VatPeriod, period_id)
        if not period or period.company_id != company_id:
            raise ValueError(f"VAT period not found: {period_id}")

        # Get all movements for the period
        query = select(VatMovement).where(
            VatMovement.company_id == company_id,
            VatMovement.period_id == period_id,
        )
        movements = self.db.scalars(query).all()

        # Calculate totals
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for movement in movements:
            if movement.movement_type == "DEBIT":
                total_debit += movement.vat_amount
            elif movement.movement_type == "CREDIT":
                total_credit += movement.vat_amount

        # Get previous credit
        previous_credit = period.previous_credit

        # Calculate balance: total_debit - total_credit - previous_credit
        balance = total_debit - total_credit - previous_credit

        # Determine amount to pay and credit to carry
        if balance > 0:
            amount_to_pay = balance
            credit_to_carry = Decimal("0.00")
        elif balance < 0:
            amount_to_pay = Decimal("0.00")
            credit_to_carry = abs(balance)
        else:
            amount_to_pay = Decimal("0.00")
            credit_to_carry = Decimal("0.00")

        summary: PeriodSummary = {
            "total_debit": total_debit,
            "total_credit": total_credit,
            "previous_credit": previous_credit,
            "balance": balance,
            "amount_to_pay": amount_to_pay,
            "credit_to_carry": credit_to_carry,
        }

        logger.debug(
            f"Calculated VAT summary for period {period_id}: "
            f"debit={total_debit}, credit={total_credit}, balance={balance}"
        )

        return summary

    def close_period_and_create_settlement(
        self,
        company_id: UUID,
        period_id: UUID,
    ) -> VatSettlement:
        """
        Close a period and create a settlement snapshot.

        Args:
            company_id: Company UUID
            period_id: Period UUID

        Returns:
            VatSettlement instance

        Raises:
            ValueError: If period not found or already has settlement
        """
        # Get period
        period = self.db.get(VatPeriod, period_id)
        if not period or period.company_id != company_id:
            raise ValueError(f"VAT period not found: {period_id}")

        # Check if settlement already exists
        query = select(VatSettlement).where(VatSettlement.period_id == period_id)
        existing_settlement = self.db.scalar(query)
        if existing_settlement:
            raise ValueError(f"Settlement already exists for period {period_id}")

        # Calculate summary
        summary = self.calculate_period_summary(company_id, period_id)

        # Create settlement
        settlement = VatSettlement(
            company_id=company_id,
            period_id=period_id,
            total_debit=summary["total_debit"],
            total_credit=summary["total_credit"],
            previous_credit=summary["previous_credit"],
            balance=summary["balance"],
            amount_to_pay=summary["amount_to_pay"],
            credit_to_carry=summary["credit_to_carry"],
            amount_paid=Decimal("0.00"),
            payment_status="UNPAID" if summary["amount_to_pay"] > 0 else "PAID",
        )
        self.db.add(settlement)

        # Update period status
        if period.status == "OPEN":
            period.status = "CLOSED"
            period.closed_at = datetime.now(timezone.utc)

        self.db.flush()

        logger.info(
            f"Created VAT settlement for period {period_id}: "
            f"balance={summary['balance']}, amount_to_pay={summary['amount_to_pay']}"
        )

        return settlement

    def record_settlement_payment(
        self,
        settlement_id: UUID,
        amount_paid: Decimal,
        payment_date: date,
        reference: str | None = None,
    ) -> VatSettlement:
        """
        Record a payment for a settlement.

        Args:
            settlement_id: Settlement UUID
            amount_paid: Amount paid
            payment_date: Date of payment
            reference: Payment reference (optional)

        Returns:
            Updated VatSettlement instance

        Raises:
            ValueError: If settlement not found or amount invalid
        """
        # Get settlement
        settlement = self.db.get(VatSettlement, settlement_id)
        if not settlement:
            raise ValueError(f"Settlement not found: {settlement_id}")

        if amount_paid < 0:
            raise ValueError("Payment amount cannot be negative")

        # Update settlement
        old_amount_paid = settlement.amount_paid
        settlement.amount_paid += amount_paid
        settlement.payment_date = payment_date
        if reference:
            settlement.payment_reference = reference

        # Determine payment status
        total_paid = settlement.amount_paid
        amount_to_pay = settlement.amount_to_pay

        if amount_to_pay == 0:
            settlement.payment_status = "PAID"
        elif total_paid == 0:
            settlement.payment_status = "UNPAID"
        elif total_paid < amount_to_pay:
            settlement.payment_status = "PARTIALLY_PAID"
        elif total_paid == amount_to_pay:
            settlement.payment_status = "PAID"
        else:  # total_paid > amount_to_pay
            settlement.payment_status = "OVERPAID"

        # Update period status to SETTLED if fully paid
        if settlement.payment_status in ("PAID", "OVERPAID"):
            period = self.db.get(VatPeriod, settlement.period_id)
            if period and period.status != "SETTLED":
                period.status = "SETTLED"
                period.settled_at = datetime.now(timezone.utc)

        self.db.flush()

        logger.info(
            f"Recorded payment for settlement {settlement_id}: "
            f"paid={amount_paid} (total={total_paid}), status={settlement.payment_status}"
        )

        return settlement

    def get_settlement_by_period(self, company_id: UUID, period_id: UUID) -> VatSettlement | None:
        """
        Get settlement for a period.

        Args:
            company_id: Company UUID
            period_id: Period UUID

        Returns:
            VatSettlement instance or None
        """
        query = select(VatSettlement).where(
            VatSettlement.company_id == company_id,
            VatSettlement.period_id == period_id,
        )
        return self.db.scalar(query)
