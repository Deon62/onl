"""Merchant API keys.

Format:  ory_sk_live_<40 random chars>   (secret, server-to-server)
         ory_pk_live_<40 random chars>   (publishable, browser checkout snippet)
         ...test_... instead of live_ in sandbox environments.

Only an HMAC-SHA256 of the key (keyed with API_KEY_PEPPER) is stored, plus a short display prefix.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from app.config import get_settings
from app.models.enums import ApiKeyKind

_KIND_TAG = {ApiKeyKind.SECRET: "sk", ApiKeyKind.PUBLISHABLE: "pk"}
_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no look-alike characters
DISPLAY_PREFIX_LEN = 16


@dataclass(frozen=True)
class GeneratedKey:
    raw: str      # shown to the admin exactly once
    prefix: str   # safe to store and display
    hash: str     # stored


def hash_api_key(raw: str) -> str:
    pepper = get_settings().api_key_pepper.encode()
    return hmac.new(pepper, raw.encode(), hashlib.sha256).hexdigest()


def generate_api_key(kind: ApiKeyKind) -> GeneratedKey:
    mode = "live" if get_settings().environment == "production" else "test"
    body = "".join(secrets.choice(_ALPHABET) for _ in range(40))
    raw = f"ory_{_KIND_TAG[kind]}_{mode}_{body}"
    return GeneratedKey(raw=raw, prefix=raw[:DISPLAY_PREFIX_LEN], hash=hash_api_key(raw))


def kind_of(raw: str) -> ApiKeyKind | None:
    if raw.startswith("ory_sk_"):
        return ApiKeyKind.SECRET
    if raw.startswith("ory_pk_"):
        return ApiKeyKind.PUBLISHABLE
    return None
