import os
import time
from typing import Any, Dict

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .parser import detect_blocked, parse_availability
from .util import ensure_dir, iso_now


def check_with_playwright(config: Dict[str, Any]) -> Dict[str, Any]:
    url = config["target"]["url"]
    timeouts = config["limits"]
    runtime = config["runtime"]
    screenshots_dir = runtime["screenshots_dir"]
    html_dir = runtime["html_dir"]

    ensure_dir(screenshots_dir)
    ensure_dir(html_dir)

    checked_at = iso_now()
    evidence: Dict[str, Any] = {"url": url}

    browser = None
    page = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=runtime.get("headless", True))
            context = browser.new_context(user_agent=runtime.get("user_agent"))

            def route_handler(route):
                if route.request.resource_type in {"image", "font"}:
                    return route.abort()
                return route.continue_()

            context.route("**/*", route_handler)
            page = context.new_page()

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeouts["navigation_timeout_ms"],
            )
            status_code = response.status if response else None
            evidence["response_status"] = status_code

            try:
                page.wait_for_load_state(
                    "networkidle", timeout=timeouts["selector_timeout_ms"]
                )
            except PlaywrightTimeoutError:
                evidence["network_idle_timeout"] = True

            body_text = page.inner_text("body")
            blocked_text = detect_blocked(body_text)
            if status_code in {403, 429} or blocked_text:
                evidence["blocked_reason"] = "status" if status_code in {403, 429} else "text"
                _save_debug_assets(page, html_dir, screenshots_dir, "blocked")
                return {
                    "status": "blocked",
                    "slots": [],
                    "checked_at": checked_at,
                    "evidence": evidence,
                }

            status, slots, parse_evidence = parse_availability(
                body_text,
                url,
                config["matchers"]["unavailable_text_substrings"],
            )
            evidence.update(parse_evidence)

            return {
                "status": status,
                "slots": slots,
                "checked_at": checked_at,
                "evidence": evidence,
            }
    except Exception as exc:
        error_message = str(exc)
        evidence["error"] = error_message
        if page is not None:
            _save_debug_assets(page, html_dir, screenshots_dir, "error")
        return {
            "status": "error",
            "slots": [],
            "checked_at": checked_at,
            "evidence": evidence,
            "error": error_message,
        }
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass


def _save_debug_assets(page, html_dir: str, screenshots_dir: str, prefix: str) -> None:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    screenshot_path = os.path.join(screenshots_dir, f"{prefix}-{timestamp}.png")
    html_path = os.path.join(html_dir, f"{prefix}-{timestamp}.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
    except Exception:
        pass
    try:
        html = page.content()
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(html)
    except Exception:
        pass
