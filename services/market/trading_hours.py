# -*- coding: utf-8 -*-
"""
Vietnam Stock Exchange Trading Hours & Calendar Engine.
Authoritative source for market session states, holidays, and effective trading date resolution.

HOSE / HNX / UPCoM Schedule (Asia/Ho_Chi_Minh, UTC+7):
- Monday - Friday:
  * 09:00 - 11:30: Morning Trading Session (ATO + Continuous)
  * 11:30 - 13:00: Intermission (Lunch break)
  * 13:00 - 14:45: Afternoon Trading Session (Continuous + ATC)
  * 14:45 - 15:00: Post-close / Put-through
  * 15:00 - 09:00 (Next day): Closed / After-hours
- Saturday - Sunday: Closed
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional, Set

VN_TZ = timezone(timedelta(hours=7))

# Standard Vietnam Public Holidays (fixed dates; Lunar holidays can be added or configured)
# Formatted as (month, day)
_FIXED_VN_HOLIDAYS: Set[tuple[int, int]] = {
    (1, 1),    # New Year's Day
    (4, 30),   # Liberation Day
    (5, 1),    # International Workers' Day
    (9, 2),    # National Day
    (9, 3),    # National Day observed
}


def get_vn_now() -> datetime:
    """Returns current datetime in Vietnam timezone (UTC+7)."""
    return datetime.now(VN_TZ)


def is_trading_day(d: date) -> bool:
    """Returns True if date is a standard weekday and not a designated holiday."""
    # Weekend check: 5 is Saturday, 6 is Sunday
    if d.weekday() >= 5:
        return False
    if (d.month, d.day) in _FIXED_VN_HOLIDAYS:
        return False
    return True


def get_previous_trading_day(from_date: Optional[date] = None) -> date:
    """
    Finds the most recent closed trading day strictly before from_date.
    """
    cur = (from_date or get_vn_now().date()) - timedelta(days=1)
    while not is_trading_day(cur):
        cur -= timedelta(days=1)
    return cur


def get_effective_trading_date(dt: Optional[datetime] = None) -> date:
    """
    Returns the authoritative date for pricing and market analysis:
    - If market is currently open or completed for today (weekday >= 09:00): returns today's date.
    - If before 09:00 on a weekday or on a weekend/holiday: returns the previous completed trading day.
    """
    now = dt or get_vn_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=VN_TZ)
    else:
        now = now.astimezone(VN_TZ)

    today = now.date()
    current_time = now.time()

    # Weekend
    if not is_trading_day(today):
        return get_previous_trading_day(today + timedelta(days=1))

    # Pre-market on a weekday (before 09:00 AM ICT)
    if current_time < time(9, 0, 0):
        return get_previous_trading_day(today)

    return today


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """Returns True if the market is currently actively trading."""
    now = dt or get_vn_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=VN_TZ)
    else:
        now = now.astimezone(VN_TZ)

    if not is_trading_day(now.date()):
        return False

    t = now.time()
    # Morning: 09:00 to 11:30
    if time(9, 0, 0) <= t < time(11, 30, 0):
        return True
    # Afternoon: 13:00 to 15:00
    if time(13, 0, 0) <= t <= time(15, 0, 0):
        return True

    return False


def get_market_session_summary(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Comprehensive session state descriptor for UI, AI context, and data pipelines.
    """
    now = dt or get_vn_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=VN_TZ)
    else:
        now = now.astimezone(VN_TZ)

    today = now.date()
    t = now.time()
    effective_date = get_effective_trading_date(now)
    eff_str = effective_date.strftime("%d/%m/%Y")
    today_str = today.strftime("%d/%m/%Y")

    if today.weekday() >= 5:
        session_code = "WEEKEND_CLOSED"
        label = f"Thị trường đóng cửa cuối tuần · Phiên đóng cửa gần nhất: {eff_str}"
        is_open = False
    elif (today.month, today.day) in _FIXED_VN_HOLIDAYS:
        session_code = "HOLIDAY_CLOSED"
        label = f"Thị trường nghỉ lễ · Phiên đóng cửa gần nhất: {eff_str}"
        is_open = False
    elif t < time(9, 0, 0):
        session_code = "PRE_MARKET"
        label = f"Trước giờ mở cửa phiên {today_str} · Phiên đóng cửa gần nhất: {eff_str}"
        is_open = False
    elif time(9, 0, 0) <= t < time(11, 30, 0):
        session_code = "OPEN_MORNING"
        label = f"Đang trong phiên sáng {today_str} (09:00 – 11:30)"
        is_open = True
    elif time(11, 30, 0) <= t < time(13, 0, 0):
        session_code = "LUNCH_BREAK"
        label = f"Nghỉ giữa phiên {today_str} · Tiếp tục phiên chiều lúc 13:00"
        is_open = False
    elif time(13, 0, 0) <= t <= time(15, 0, 0):
        session_code = "OPEN_AFTERNOON"
        label = f"Đang trong phiên chiều {today_str} (13:00 – 15:00)"
        is_open = True
    else:
        session_code = "POST_MARKET"
        label = f"Đã đóng cửa phiên {today_str}"
        is_open = False

    return {
        "session_code": session_code,
        "is_open": is_open,
        "current_time_ict": now.strftime("%H:%M:%S ICT"),
        "effective_date": effective_date,
        "effective_date_iso": effective_date.isoformat(),
        "effective_date_display": eff_str,
        "label": label,
    }
