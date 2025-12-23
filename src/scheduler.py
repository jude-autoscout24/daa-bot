import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .checker_endpoint import check_with_endpoint
from .checker_playwright import check_with_playwright
from .notifier_email import send_notification
from .store import (
    count_checks_since,
    get_state,
    init_db,
    insert_check,
    oldest_check_since,
    serialize_evidence,
    serialize_slots,
    set_state,
)
from .util import hash_json, iso_now, jittered_interval, normalize_slots

logger = logging.getLogger(__name__)


def run_once(config: Dict[str, Any]) -> Dict[str, Any]:
    mode = config["target"].get("mode", "playwright")
    if mode == "endpoint":
        try:
            return check_with_endpoint(config)
        except Exception as exc:
            logger.warning("Endpoint checker failed, falling back to Playwright: %s", exc)
    return check_with_playwright(config)

def run_once_and_store(config: Dict[str, Any]) -> Dict[str, Any]:
    storage_cfg = config["storage"]
    init_db(storage_cfg)

    blocked_until = get_state(storage_cfg, "blocked_until")
    if blocked_until:
        try:
            until_dt = datetime.fromisoformat(blocked_until)
        except ValueError:
            until_dt = None
        if until_dt and datetime.now(timezone.utc) < until_dt:
            blocked_payload = {
                "status": "blocked",
                "slots": [],
                "evidence": {
                    "url": config["target"]["url"],
                    "blocked_until": blocked_until,
                    "cooldown_active": True,
                },
            }
            result = {
                "status": "blocked",
                "slots": [],
                "checked_at": iso_now(),
                "evidence": blocked_payload["evidence"],
            }
            result_hash = hash_json(blocked_payload)
            insert_check(
                storage_cfg,
                result["checked_at"],
                result["status"],
                serialize_slots([]),
                result_hash,
                serialize_evidence(result["evidence"]),
                None,
            )
            _handle_state_and_notifications(config, storage_cfg, result, result_hash)
            return result

    result = run_once(config)
    normalized_slots = normalize_slots(result.get("slots") or [])
    result["slots"] = normalized_slots

    hash_payload = {
        "status": result["status"],
        "slots": normalized_slots,
        "evidence": result.get("evidence", {}),
    }
    result_hash = hash_json(hash_payload)

    insert_check(
        storage_cfg,
        result["checked_at"],
        result["status"],
        serialize_slots(normalized_slots),
        result_hash,
        serialize_evidence(result.get("evidence", {})),
        result.get("error"),
    )
    _handle_state_and_notifications(config, storage_cfg, result, result_hash)
    return result

def run_loop(config: Dict[str, Any]) -> None:
    storage_cfg = config["storage"]
    init_db(storage_cfg)

    while True:
        _maybe_sleep_for_block(storage_cfg)
        _enforce_rate_limit(config, storage_cfg)

        result = run_once(config)
        normalized_slots = normalize_slots(result.get("slots") or [])
        result["slots"] = normalized_slots

        hash_payload = {
            "status": result["status"],
            "slots": normalized_slots,
            "evidence": result.get("evidence", {}),
        }
        result_hash = hash_json(hash_payload)

        insert_check(
            storage_cfg,
            result["checked_at"],
            result["status"],
            serialize_slots(normalized_slots),
            result_hash,
            serialize_evidence(result.get("evidence", {})),
            result.get("error"),
        )

        _handle_state_and_notifications(config, storage_cfg, result, result_hash)

        delay = _compute_next_delay(config, storage_cfg, result)
        logger.info("Sleeping for %s seconds", delay)
        time.sleep(delay)


def _compute_next_delay(config: Dict[str, Any], storage_cfg: Dict[str, Any], result: Dict[str, Any]) -> int:
    schedule = config["schedule"]
    limits = config["limits"]
    base_interval = jittered_interval(schedule["interval_seconds"], schedule["jitter_percent"])

    failures = int(get_state(storage_cfg, "consecutive_failures") or 0)
    if result["status"] in {"error", "blocked"} and failures:
        backoff = limits["backoff_base_seconds"] * (2 ** max(failures - 1, 0))
        backoff = min(backoff, limits["max_backoff_seconds"])
        base_interval = max(base_interval, backoff)

    return base_interval


def _maybe_sleep_for_block(storage_cfg: Dict[str, Any]) -> None:
    blocked_until = get_state(storage_cfg, "blocked_until")
    if not blocked_until:
        return
    try:
        until_dt = datetime.fromisoformat(blocked_until)
    except ValueError:
        return
    now = datetime.now(timezone.utc)
    if now < until_dt:
        sleep_seconds = int((until_dt - now).total_seconds())
        logger.warning("Blocked until %s, sleeping for %s seconds", blocked_until, sleep_seconds)
        time.sleep(max(1, sleep_seconds))


def _enforce_rate_limit(config: Dict[str, Any], storage_cfg: Dict[str, Any]) -> None:
    max_checks = config["limits"]["max_checks_per_hour"]
    if not max_checks:
        return
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)
    window_start_iso = window_start.isoformat()

    recent = count_checks_since(storage_cfg, window_start_iso)
    if recent < max_checks:
        return

    oldest = oldest_check_since(storage_cfg, window_start_iso)
    if not oldest:
        return
    oldest_dt = datetime.fromisoformat(oldest)
    sleep_until = oldest_dt + timedelta(hours=1)
    sleep_seconds = int((sleep_until - now).total_seconds())
    if sleep_seconds > 0:
        logger.warning("Rate limit reached, sleeping for %s seconds", sleep_seconds)
        time.sleep(sleep_seconds)


def _handle_state_and_notifications(
    config: Dict[str, Any],
    storage_cfg: Dict[str, Any],
    result: Dict[str, Any],
    result_hash: str,
) -> None:
    status = result["status"]
    last_status = get_state(storage_cfg, "last_status")
    last_hash = get_state(storage_cfg, "last_hash")
    last_notified_hash = get_state(storage_cfg, "last_notified_hash")

    if status in {"error", "blocked"}:
        failures = int(get_state(storage_cfg, "consecutive_failures") or 0) + 1
        set_state(storage_cfg, "consecutive_failures", str(failures))
        if status == "blocked":
            cooldown_hours = config["limits"]["blocked_cooldown_hours"]
            blocked_until = datetime.now(timezone.utc) + timedelta(hours=cooldown_hours)
            set_state(storage_cfg, "blocked_until", blocked_until.isoformat())
            if last_status != "blocked":
                _safe_notify(config, result)
        set_state(storage_cfg, "last_status", status)
        set_state(storage_cfg, "last_hash", result_hash)
        return

    set_state(storage_cfg, "consecutive_failures", "0")
    set_state(storage_cfg, "blocked_until", "")

    notify_cfg = config["notify"]
    should_notify = False

    if status == "available" and notify_cfg.get("on_available", True):
        if last_status != "available":
            should_notify = True

    if status == "available" and notify_cfg.get("on_change"):
        if last_notified_hash != result_hash:
            should_notify = True

    if should_notify:
        _safe_notify(config, result)
        set_state(storage_cfg, "last_notified_hash", result_hash)

    set_state(storage_cfg, "last_status", status)
    set_state(storage_cfg, "last_hash", result_hash)


def _safe_notify(config: Dict[str, Any], result: Dict[str, Any]) -> None:
    try:
        send_notification(config, result)
    except Exception as exc:
        logger.error("Failed to send email: %s", exc)
