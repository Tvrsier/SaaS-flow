"""VAT Period Service"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.invoice import VatPeriod
from app.db.models.user import User

logger = logging.getLogger("GestPro")

VatFrequency = Literal["MONTHLY", "QUARTERLY"]
VatPeriodStatus = Literal["OPEN", "CLOSED", "SETTLED"]


class VatPeriodService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_period(
        self,
        company_id: UUID,
        competence_date: date,
        frequency: VatFrequency,
    ) -> VatPeriod:
        """
        Get or create a VAT period for the given competence date and frequency.

        Args:
            company_id: Company UUID
            competence_date: Date to determine the period
            frequency: MONTHLY or QUARTERLY

        Returns:
            VatPeriod instance
        """
        year = competence_date.year
        period_index = self._calculate_period_index(competence_date, frequency)
        start_date, end_date = self._calculate_period_dates(year, period_index, frequency)

        # Try to find existing period
        query = select(VatPeriod).where(
            VatPeriod.company_id == company_id,
            VatPeriod.year == year,
            VatPeriod.period_index == period_index,
            VatPeriod.frequency == frequency,
        )
        period = self.db.scalar(query)

        if period:
            logger.debug(
                f"Found existing VAT period: company={company_id}, year={year}, period={period_index}, frequency={frequency}"
            )
            return period

        # Calculate previous_credit from previous period
        previous_credit = self._get_previous_period_credit(company_id, year, period_index, frequency)

        # Create new period
        period = VatPeriod(
            company_id=company_id,
            year=year,
            period_index=period_index,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            status="OPEN",
            previous_credit=previous_credit,
        )
        self.db.add(period)
        self.db.flush()

        logger.info(
            f"Created new VAT period: company={company_id}, year={year}, period={period_index}, "
            f"frequency={frequency}, previous_credit={previous_credit}"
        )

        return period

    def get_current_period(
        self,
        company_id: UUID,
        target_date: date,
        frequency: VatFrequency,
    ) -> VatPeriod | None:
        """
        Get the VAT period for a specific date.

        Args:
            company_id: Company UUID
            target_date: Date to find the period for
            frequency: MONTHLY or QUARTERLY

        Returns:
            VatPeriod instance or None if not found
        """
        year = target_date.year
        period_index = self._calculate_period_index(target_date, frequency)

        query = select(VatPeriod).where(
            VatPeriod.company_id == company_id,
            VatPeriod.year == year,
            VatPeriod.period_index == period_index,
            VatPeriod.frequency == frequency,
        )
        return self.db.scalar(query)

    def create_next_period(self, previous_period: VatPeriod) -> VatPeriod:
        """
        Create the next period after the given period.

        Args:
            previous_period: The previous period

        Returns:
            New VatPeriod instance
        """
        if previous_period.frequency == "MONTHLY":
            if previous_period.period_index == 12:
                next_year = previous_period.year + 1
                next_index = 1
            else:
                next_year = previous_period.year
                next_index = previous_period.period_index + 1
        else:  # QUARTERLY
            if previous_period.period_index == 4:
                next_year = previous_period.year + 1
                next_index = 1
            else:
                next_year = previous_period.year
                next_index = previous_period.period_index + 1

        start_date, end_date = self._calculate_period_dates(
            next_year,
            next_index,
            previous_period.frequency,
        )

        # Get credit to carry from previous period's settlement
        from app.modules.vat.services.vat_summary_service import VatSummaryService
        vat_summary_service = VatSummaryService(self.db)
        previous_credit = Decimal("0.00")

        try:
            summary = vat_summary_service.calculate_period_summary(previous_period.company_id, previous_period.id)
            previous_credit = summary["credit_to_carry"]
        except Exception as e:
            logger.warning(f"Could not calculate credit from previous period: {e}")

        period = VatPeriod(
            company_id=previous_period.company_id,
            year=next_year,
            period_index=next_index,
            frequency=previous_period.frequency,
            start_date=start_date,
            end_date=end_date,
            status="OPEN",
            previous_credit=previous_credit,
        )
        self.db.add(period)
        self.db.flush()

        logger.info(
            f"Created next VAT period: company={previous_period.company_id}, year={next_year}, "
            f"period={next_index}, frequency={previous_period.frequency}, previous_credit={previous_credit}"
        )

        return period

    def close_period(self, company_id: UUID, period_id: UUID) -> VatPeriod:
        """
        Close a VAT period.

        Args:
            company_id: Company UUID
            period_id: Period UUID

        Returns:
            Updated VatPeriod instance

        Raises:
            ValueError: If period not found or already closed
        """
        query = select(VatPeriod).where(
            VatPeriod.id == period_id,
            VatPeriod.company_id == company_id,
        )
        period = self.db.scalar(query)

        if not period:
            raise ValueError(f"VAT period not found: {period_id}")

        if period.status in ("CLOSED", "SETTLED"):
            raise ValueError(f"VAT period already {period.status.lower()}: {period_id}")

        period.status = "CLOSED"
        period.closed_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info(f"Closed VAT period: {period_id}")

        return period

    def settle_period(self, company_id: UUID, period_id: UUID) -> VatPeriod:
        """
        Mark a VAT period as settled.

        Args:
            company_id: Company UUID
            period_id: Period UUID

        Returns:
            Updated VatPeriod instance

        Raises:
            ValueError: If period not found or already settled
        """
        query = select(VatPeriod).where(
            VatPeriod.id == period_id,
            VatPeriod.company_id == company_id,
        )
        period = self.db.scalar(query)

        if not period:
            raise ValueError(f"VAT period not found: {period_id}")

        if period.status == "SETTLED":
            raise ValueError(f"VAT period already settled: {period_id}")

        if period.status == "OPEN":
            period.status = "CLOSED"
            period.closed_at = datetime.now(timezone.utc)

        period.status = "SETTLED"
        period.settled_at = datetime.now(timezone.utc)
        self.db.flush()

        logger.info(f"Settled VAT period: {period_id}")

        return period

    def _calculate_period_index(self, target_date: date, frequency: VatFrequency) -> int:
        """Calculate period index (1-12 for MONTHLY, 1-4 for QUARTERLY)"""
        if frequency == "MONTHLY":
            return target_date.month
        else:  # QUARTERLY
            month = target_date.month
            if month <= 3:
                return 1
            elif month <= 6:
                return 2
            elif month <= 9:
                return 3
            else:
                return 4

    def _calculate_period_dates(
        self,
        year: int,
        period_index: int,
        frequency: VatFrequency,
    ) -> tuple[date, date]:
        """Calculate start and end dates for a period"""
        if frequency == "MONTHLY":
            start_date = date(year, period_index, 1)
            if period_index == 12:
                end_date = date(year, 12, 31)
            else:
                next_month_start = date(year, period_index + 1, 1)
                from datetime import timedelta
                end_date = next_month_start - timedelta(days=1)
        else:  # QUARTERLY
            if period_index == 1:
                start_date = date(year, 1, 1)
                end_date = date(year, 3, 31)
            elif period_index == 2:
                start_date = date(year, 4, 1)
                end_date = date(year, 6, 30)
            elif period_index == 3:
                start_date = date(year, 7, 1)
                end_date = date(year, 9, 30)
            else:  # period_index == 4
                start_date = date(year, 10, 1)
                end_date = date(year, 12, 31)

        return start_date, end_date

    def _get_previous_period_credit(
        self,
        company_id: UUID,
        year: int,
        period_index: int,
        frequency: VatFrequency,
    ) -> Decimal:
        """Get credit to carry from previous period"""
        if period_index == 1 and frequency == "MONTHLY":
            # Previous is December of previous year
            prev_year = year - 1
            prev_index = 12
        elif period_index == 1 and frequency == "QUARTERLY":
            # Previous is Q4 of previous year
            prev_year = year - 1
            prev_index = 4
        else:
            prev_year = year
            prev_index = period_index - 1

        # Find previous period
        query = select(VatPeriod).where(
            VatPeriod.company_id == company_id,
            VatPeriod.year == prev_year,
            VatPeriod.period_index == prev_index,
            VatPeriod.frequency == frequency,
        )
        prev_period = self.db.scalar(query)

        if not prev_period:
            return Decimal("0.00")

        # Get settlement for previous period
        from app.db.models.invoice import VatSettlement
        query = select(VatSettlement).where(VatSettlement.period_id == prev_period.id)
        settlement = self.db.scalar(query)

        if settlement:
            return settlement.credit_to_carry

        # If no settlement, calculate it
        from app.modules.vat.services.vat_summary_service import VatSummaryService
        vat_summary_service = VatSummaryService(self.db)
        try:
            summary = vat_summary_service.calculate_period_summary(company_id, prev_period.id)
            return summary["credit_to_carry"]
        except Exception as e:
            logger.warning(f"Could not calculate previous period credit: {e}")
            return Decimal("0.00")
