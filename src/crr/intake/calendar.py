"""Which months are open (SPEC §18.3).

A month folder holds the material for the month it names; quarterly material goes in the
quarter's last month. It is watched until `lookback_days` after that month's last day, then
closed for good (D-23).
"""

from __future__ import annotations

import calendar as _calendar
from datetime import date, timedelta

from crr.models import PeriodId


def parse_period(period: PeriodId) -> tuple[int, int]:
    year, _, month = period.partition("-")
    if not (len(year) == 4 and year.isdigit() and len(month) == 2 and month.isdigit()):
        raise ValueError(f"period {period!r} is not YYYY-MM")
    if not 1 <= int(month) <= 12:
        raise ValueError(f"period {period!r} has no month {int(month)}")
    return int(year), int(month)


def period_of(day: date) -> PeriodId:
    return f"{day.year:04d}-{day.month:02d}"


def add_months(period: PeriodId, count: int) -> PeriodId:
    year, month = parse_period(period)
    index = year * 12 + (month - 1) + count
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_end(period: PeriodId) -> date:
    year, month = parse_period(period)
    return date(year, month, _calendar.monthrange(year, month)[1])


def closes_on(period: PeriodId, lookback_days: int) -> date:
    """The last day changes to this month are acted on: September 2026 → 2026-11-11."""
    return month_end(period) + timedelta(days=lookback_days)


def is_open(period: PeriodId, today: date, lookback_days: int) -> bool:
    return today <= closes_on(period, lookback_days)


def months_to_prepare(today: date, ahead: int) -> list[PeriodId]:
    """The current month and the next `ahead` months: the folders that should exist before
    anyone needs them."""
    current = period_of(today)
    return [add_months(current, n) for n in range(ahead + 1)]
