import hashlib
import json
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def stable_json_dumps(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hash_json(data: Any) -> str:
    payload = stable_json_dumps(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_slots(slots: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized = []
    for slot in slots:
        date = (slot.get("date") or "").strip()
        time = (slot.get("time") or "").strip()
        if not date or not time:
            continue
        normalized.append({"date": date, "time": time})
    return sorted(normalized, key=lambda s: (s["date"], s["time"]))


def jittered_interval(base_seconds: int, jitter_percent: int) -> int:
    if jitter_percent <= 0:
        return base_seconds
    spread = base_seconds * jitter_percent / 100
    return max(1, int(base_seconds + random.uniform(-spread, spread)))
