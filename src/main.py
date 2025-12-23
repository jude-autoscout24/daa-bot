import argparse
import json
import logging
import os

from .config import load_config
from .notifier_email import send_notification
from .scheduler import run_loop, run_once, run_once_and_store
from .util import iso_now, normalize_slots


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminland appointment watcher")
    parser.add_argument("--config", required=True, help="Path to config.yaml")

    subparsers = parser.add_subparsers(dest="command", required=True)
    check_once_parser = subparsers.add_parser("check-once", help="Run a single check")
    check_once_parser.add_argument(
        "--store",
        action="store_true",
        help="Persist result and notifications",
    )
    subparsers.add_parser("run", help="Run forever with scheduling")

    args = parser.parse_args()
    config = load_config(args.config)

    _configure_logging()

    if os.getenv("TEST_EMAIL") == "1":
        test_result = {
            "status": "test",
            "slots": [],
            "checked_at": iso_now(),
            "evidence": {"url": config["target"]["url"], "note": "test email"},
        }
        send_notification(config, test_result)
        logging.getLogger(__name__).info("Sent test email")
        return 0

    if args.command == "check-once":
        if args.store:
            result = run_once_and_store(config)
        else:
            result = run_once(config)
        result["slots"] = normalize_slots(result.get("slots") or [])
        print(json.dumps(result, sort_keys=True))
        if result["status"] == "blocked":
            return 2
        if result["status"] == "error":
            return 1
        return 0

    if args.command == "run":
        run_loop(config)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
