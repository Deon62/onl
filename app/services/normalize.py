"""Input normalisation shared by schemas and services (mirrors src/lib/format.ts in the dashboard)."""

import re

_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def normalize_phone(value: str) -> str | None:
    """Kenyan mobile number -> 2547XXXXXXXX / 2541XXXXXXXX, or None if invalid."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("254") and len(digits) == 12:
        local = digits[3:]
    elif digits.startswith("0") and len(digits) == 10:
        local = digits[1:]
    elif len(digits) == 9:
        local = digits
    else:
        return None
    return "254" + local if local[0] in "71" else None


def normalize_domain(value: str) -> str | None:
    """'https://www.Acme.co.ke/shop' -> 'acme.co.ke' (www. stripped), or None if invalid."""
    v = (value or "").strip().lower()
    v = re.sub(r"^[a-z]+://", "", v).split("/", 1)[0].split(":", 1)[0]
    if v.startswith("www."):
        v = v[4:]
    return v if _DOMAIN_RE.match(v) else None


def mask_phone(phone: str) -> str:
    return phone[:6] + "***" + phone[-3:] if len(phone) >= 9 else phone
