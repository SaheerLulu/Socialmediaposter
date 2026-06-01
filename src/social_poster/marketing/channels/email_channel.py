"""Email outreach over SMTP, with an unsubscribe footer and dry-run staging."""

from __future__ import annotations

from ..config import marketing_settings
from ..schemas import SendResult
from ._outbox import stage


def _with_unsubscribe(body: str) -> str:
    footer = (
        f"\n\n—\nYou are receiving this because you opted in or expressed interest. "
        f"Unsubscribe: {marketing_settings.unsubscribe_url}"
    )
    return body.rstrip() + footer


def send_email_message(lead_id: str, to_email: str, subject: str, body: str) -> SendResult:
    body = _with_unsubscribe(body)

    if marketing_settings.dry_run:
        stage("email", to_email, {"lead_id": lead_id, "subject": subject, "body": body})
        return SendResult(lead_id, "email", ok=True, dry_run=True,
                          detail=f"[DRY RUN] email staged for {to_email}")

    import smtplib
    from email.mime.text import MIMEText

    s = marketing_settings
    if not (s.smtp_host and s.smtp_from):
        return SendResult(lead_id, "email", ok=False,
                          detail="SMTP not configured (set SMTP_HOST, SMTP_FROM, ...)")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = s.smtp_from
    msg["To"] = to_email
    msg["List-Unsubscribe"] = f"<{s.unsubscribe_url}>"

    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as server:
            if s.smtp_use_tls:
                server.starttls()
            if s.smtp_user and s.smtp_password:
                server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_from, [to_email], msg.as_string())
        return SendResult(lead_id, "email", ok=True, detail=f"sent to {to_email}")
    except Exception as exc:  # pragma: no cover - network/credential failures
        return SendResult(lead_id, "email", ok=False, detail=f"send failed: {exc}")
