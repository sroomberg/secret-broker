"""Redact secret material from strings before they leave the broker."""

from __future__ import annotations

import base64
import binascii
import contextlib
import re
from urllib.parse import quote


def _variants(secret: str) -> set[str]:
    variants: set[str] = {secret}
    if not secret:
        return variants
    with contextlib.suppress(UnicodeError, ValueError):
        variants.add(base64.b64encode(secret.encode()).decode())
    variants.add(quote(secret, safe=""))
    with contextlib.suppress(UnicodeError, ValueError):
        variants.add(binascii.hexlify(secret.encode()).decode())
    return {v for v in variants if v}


def redact_text(text: str, secrets: list[str], placeholder: str = "[REDACTED]") -> tuple[str, bool]:
    """Replace known secret values (and common encodings) in text."""
    if not text or not secrets:
        return text, False
    out = text
    changed = False
    # Longest first to avoid partial overlaps
    needles: list[str] = []
    for s in secrets:
        needles.extend(_variants(s))
    needles = sorted({n for n in needles if n}, key=len, reverse=True)
    for needle in needles:
        if needle and needle in out:
            out = out.replace(needle, placeholder)
            changed = True
    return out, changed


def scrub_error_message(exc: BaseException, secrets: list[str]) -> str:
    msg = f"{type(exc).__name__}: {exc}"
    scrubbed, _ = redact_text(msg, secrets)
    # Never echo likely secret-shaped leftovers from adapter errors
    scrubbed = re.sub(r"(?i)(password|token|secret|key)\s*[:=]\s*\S+", r"\1=[REDACTED]", scrubbed)
    return scrubbed
