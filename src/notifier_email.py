import smtplib
import time
from email.message import EmailMessage
from typing import Any, Dict

from .config import getenv_required


def send_notification(config: Dict[str, Any], result: Dict[str, Any]) -> None:
    email_cfg = config["notify"]["email"]
    smtp_host = email_cfg["smtp_host"]
    smtp_port = email_cfg["smtp_port"]
    use_tls = email_cfg.get("use_tls", True)

    username = getenv_required(email_cfg["username_env"])
    password = getenv_required(email_cfg["password_env"])

    msg = EmailMessage()
    status = result["status"].upper()
    msg["Subject"] = f"[Terminland Watcher] Appointments {status}"
    msg["From"] = email_cfg["from"]
    msg["To"] = email_cfg["to"]

    msg.set_content(_render_body(result, email_cfg.get("max_slots_in_email", 10)))

    attempts = 3
    delay = 2
    last_exc = None
    for _ in range(attempts):
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                server.login(username, password)
                server.send_message(msg)
            return
        except Exception as exc:  # pragma: no cover - network
            last_exc = exc
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Failed to send email: {last_exc}")


def _render_body(result: Dict[str, Any], max_slots: int) -> str:
    lines = [
        f"Status: {result['status']}",
        f"Checked at: {result['checked_at']}",
        f"URL: {result['evidence'].get('url')}",
        "",
        "Evidence:",
    ]
    for key, value in result.get("evidence", {}).items():
        if key == "url":
            continue
        lines.append(f"- {key}: {value}")

    slots = result.get("slots") or []
    if slots:
        lines.append("")
        lines.append("Slots:")
        for slot in slots[:max_slots]:
            lines.append(f"- {slot['date']} {slot['time']}")
    return "\n".join(lines)
