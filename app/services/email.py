"""Transactional email through Resend (https://resend.com/docs/api-reference/emails/send-email)."""

import logging
from dataclasses import dataclass
from html import escape

import httpx

from app.config import get_settings

log = logging.getLogger("oryne.email")

RESEND_URL = "https://api.resend.com/emails"


@dataclass
class EmailResult:
    sent: bool
    error: str | None = None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15)


async def send_email(to: str, subject: str, html: str, text: str) -> EmailResult:
    s = get_settings()
    if not s.resend_api_key:
        return EmailResult(False, "Email is not set up (RESEND_API_KEY missing). Copy the password and send it manually.")
    try:
        async with _client() as http:
            res = await http.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {s.resend_api_key}"},
                json={"from": s.email_from, "to": [to], "subject": subject, "html": html, "text": text},
            )
    except httpx.HTTPError as e:
        log.warning("Resend unreachable: %s", e)
        return EmailResult(False, "Could not reach the email service. Copy the password and send it manually.")
    if res.status_code >= 300:
        try:
            msg = res.json().get("message", res.text)
        except ValueError:
            msg = res.text
        log.warning("Resend rejected email to %s: %s", to, msg)
        return EmailResult(False, f"The email service rejected the message: {msg}")
    return EmailResult(True)


# ---------------------------------------------------------------------------
# Login details email
# ---------------------------------------------------------------------------

def login_email(*, name: str, business: str, email: str, password: str, login_url: str, welcome: bool) -> tuple[str, str, str]:
    """(subject, html, text) for a merchant's sign-in details. Inline styles only, so it renders in every client."""
    first = escape((name or "there").split()[0])
    biz = escape(business)
    subject = f"Welcome to Oryne, {business}" if welcome else f"Your new Oryne password for {business}"
    lead = (f"Your Oryne account for <strong style=\"color:#111827\">{biz}</strong> is ready. "
            "Here is everything you need to sign in.") if welcome else (
            f"We have set a new password for your <strong style=\"color:#111827\">{biz}</strong> account.")
    e, p, url = escape(email), escape(password), escape(login_url)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f5f5f4;-webkit-font-smoothing:antialiased">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0">Your sign-in details for {biz} on Oryne.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f4;padding:40px 16px">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:460px">
        <tr><td style="padding:0 4px 20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif">
          <span style="display:inline-block;width:22px;height:22px;border-radius:50%;background:#111827;vertical-align:middle"></span>
          <span style="font-size:17px;font-weight:600;letter-spacing:-0.02em;color:#111827;vertical-align:middle;margin-left:6px">oryne</span>
        </td></tr>
        <tr><td style="background:#ffffff;border:1px solid #e7e5e4;border-radius:14px;padding:36px 32px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif">
          <p style="margin:0 0 6px;font-size:13px;color:#a8a29e">&#10022; {'Welcome aboard' if welcome else 'Password updated'}</p>
          <h1 style="margin:0 0 14px;font-size:22px;line-height:1.3;font-weight:600;letter-spacing:-0.02em;color:#111827">Hi {first},</h1>
          <p style="margin:0 0 24px;font-size:14.5px;line-height:1.65;color:#57534e">{lead}</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fafaf9;border:1px solid #f0efed;border-radius:10px">
            <tr><td style="padding:16px 18px 6px;font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:#a8a29e">Email</td></tr>
            <tr><td style="padding:0 18px 14px;font-size:14.5px;color:#111827">{e}</td></tr>
            <tr><td style="padding:0 18px"><div style="border-top:1px dashed #e7e5e4"></div></td></tr>
            <tr><td style="padding:14px 18px 6px;font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:#a8a29e">Temporary password</td></tr>
            <tr><td style="padding:0 18px 16px;font-family:'SFMono-Regular',Menlo,Consolas,monospace;font-size:17px;letter-spacing:0.04em;color:#111827">{p}</td></tr>
          </table>
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px 0 8px"><tr><td style="border-radius:999px;background:#111827">
            <a href="{url}" style="display:inline-block;padding:12px 26px;font-size:14px;font-weight:500;color:#ffffff;text-decoration:none;border-radius:999px">Sign in to Oryne &rarr;</a>
          </td></tr></table>
          <p style="margin:22px 0 0;font-size:13px;line-height:1.6;color:#78716c">For your security, change this password after you sign in (Settings &rarr; Password). Never share it with anyone, including Oryne staff.</p>
        </td></tr>
        <tr><td style="padding:22px 4px 0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Helvetica,Arial,sans-serif;font-size:12px;line-height:1.6;color:#a8a29e">
          Sent by Oryne Network because an account was set up for {biz}. Not expecting this? You can ignore this email.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text = (
        f"Hi {(name or 'there').split()[0]},\n\n"
        + (f"Your Oryne account for {business} is ready.\n\n" if welcome else f"We have set a new password for your {business} account.\n\n")
        + f"Email: {email}\nTemporary password: {password}\n\nSign in: {login_url}\n\n"
        "Change this password after you sign in (Settings -> Password). Never share it with anyone.\n\n- Oryne Network\n"
    )
    return subject, html, text
