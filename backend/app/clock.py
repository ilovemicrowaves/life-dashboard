"""Kleine tijd-helpers. Eén plek voor 'lokale tijd' zodat tz overal gelijk is."""

from datetime import date, datetime
from zoneinfo import ZoneInfo


def get_tz(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def today_local(tz_name: str) -> date:
    return now_local(tz_name).date()
