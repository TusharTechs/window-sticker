"""Per-run canary credentials.

Canaries are fake but realistic-looking secrets generated fresh for every run, so a
leak can be attributed to exactly one run and no real credential is ever at risk.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

PREFIXES = {
    "VULTR": "VLTR",
    "GITHUB": "ghp_",
    "AWS": "AKIA",
    "STRIPE": "sk_live_",
    "DB": "pg_",
}


def make_canary(name: str, run_id: str, salt: bytes | None = None) -> str:
    """Return a unique canary value for ``name`` in run ``run_id``."""
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hmac.new(salt, f"{run_id}:{name}".encode(), hashlib.sha256).hexdigest()
    prefix = next((p for key, p in PREFIXES.items() if key in name.upper()), "wsk_")
    body = digest[:32].upper() if prefix == "AKIA" else digest[:36]
    return f"{prefix}{body}"


def make_canaries(names: list[str], run_id: str) -> dict[str, str]:
    salt = secrets.token_bytes(16)
    return {name: make_canary(name, run_id, salt) for name in names}
