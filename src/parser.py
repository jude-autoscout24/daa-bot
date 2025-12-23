import re
from datetime import datetime
from typing import Dict, List, Tuple

from .util import normalize_slots

TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")


BLOCKED_SUBSTRINGS = [
    "captcha",
    "access denied",
    "unusual traffic",
    "robot",
    "bot detection",
    "not authorized",
    "forbidden",
    "too many requests",
]


def _normalize_time(value: str) -> str:
    parts = value.split(":")
    if len(parts) != 2:
        return value
    hour = parts[0].zfill(2)
    minute = parts[1].zfill(2)
    return f"{hour}:{minute}"


def _normalize_date(day: str, month: str, year: str) -> str:
    try:
        parsed = datetime(int(year), int(month), int(day))
    except ValueError:
        return ""
    return parsed.strftime("%Y-%m-%d")


def detect_blocked(body_text: str) -> bool:
    lower = (body_text or "").lower()
    return any(token in lower for token in BLOCKED_SUBSTRINGS)


def extract_slots(body_text: str) -> Tuple[List[Dict[str, str]], int, int]:
    times = sorted({_normalize_time(match) for match in TIME_RE.findall(body_text or "")})
    dates = []
    for day, month, year in DATE_RE.findall(body_text or ""):
        normalized = _normalize_date(day, month, year)
        if normalized:
            dates.append(normalized)
    dates = sorted(set(dates))

    slots: List[Dict[str, str]] = []
    if times and len(dates) == 1:
        slots = [{"date": dates[0], "time": time} for time in times]
    return normalize_slots(slots), len(times), len(dates)


def parse_availability(
    body_text: str,
    url: str,
    unavailable_substrings: List[str],
) -> Tuple[str, List[Dict[str, str]], Dict[str, object]]:
    lowered = (body_text or "").lower()
    found_unavailable = any(token.lower() in lowered for token in unavailable_substrings)

    slots, time_count, date_count = extract_slots(body_text or "")

    if found_unavailable and not time_count:
        status = "unavailable"
    elif time_count or date_count:
        status = "available"
    else:
        status = "unavailable"

    evidence: Dict[str, object] = {
        "url": url,
        "found_unavailable_text": found_unavailable,
        "slot_time_count": time_count,
        "date_count": date_count,
    }
    return status, slots, evidence
