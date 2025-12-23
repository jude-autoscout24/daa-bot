import os
from typing import Any, Dict

import yaml

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


DEFAULT_CONFIG: Dict[str, Any] = {
    "target": {
        "url": "https://www.terminland.de/DAAMuenchenDeutschkurse/",
        "mode": "playwright",
    },
    "matchers": {
        "unavailable_text_substrings": [
            "keine freien Termine",
            "keine freien termine",
        ],
    },
    "schedule": {
        "interval_seconds": 420,
        "jitter_percent": 20,
    },
    "limits": {
        "max_checks_per_hour": 12,
        "navigation_timeout_ms": 30000,
        "selector_timeout_ms": 15000,
        "backoff_base_seconds": 60,
        "max_backoff_seconds": 900,
        "blocked_cooldown_hours": 12,
    },
    "notify": {
        "on_available": True,
        "on_change": False,
        "email": {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "use_tls": True,
            "from": "YOUR_GMAIL@gmail.com",
            "to": "YOUR_EMAIL@gmail.com",
            "username_env": "SMTP_USER",
            "password_env": "SMTP_PASS",
            "max_slots_in_email": 10,
        },
    },
    "storage": {
        "sqlite_path": "./data/state.db",
        "postgres_url_env": "DATABASE_URL",
    },
    "runtime": {
        "headless": True,
        "screenshots_dir": "./data/screenshots",
        "html_dir": "./data/html",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        ),
    },
}


def deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str) -> Dict[str, Any]:
    if load_dotenv:
        load_dotenv()
    if not path:
        return DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return deep_merge(DEFAULT_CONFIG, loaded)


def getenv_required(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value
