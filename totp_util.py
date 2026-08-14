from cryptography.hazmat.primitives import hashes, hmac as chmac

def _b32_decode(secret):
    # Normalisiert secret (Entfernt Leerzeichen, Grossbuchstaben)
    s = secret.strip().upper().replace(" ", "")
    pad = (-len(s)) % 8
    return base64.b32decode(s + "=" * pad)


# -*- coding: utf-8 -*-
"""TOTP / MFA Helfer (aus security.py extrahiert, BUG-005 Refactor-Teil).
Reine stdlib, keine security-Abhaengigkeiten -> kein Circular-Import."""
import base64, secrets, time, hashlib, hmac
from datetime import datetime

RECOVERY_CODE_COUNT = 8
RECOVERY_CODE_LENGTH = 10

def generate_mfa_secret():
    """32 Byte Zufall → Base32 (TOTP-Standard)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp(secret_b32, timestamp, digits=6, period=30):
    """RFC 6238 TOTP. Nutzt cryptography.hazmat HMAC (FIPS-validiert)."""
    counter = int(timestamp // period)
    msg = counter.to_bytes(8, "big")
    h = chmac.HMAC(_b32_decode(secret_b32), hashes.SHA1())
    h.update(msg)
    digest = h.finalize()
    offset = digest[-1] & 0x0F
    binary = ((digest[offset] & 0x7F) << 24
              | (digest[offset + 1] & 0xFF) << 16
              | (digest[offset + 2] & 0xFF) << 8
              | (digest[offset + 3] & 0xFF))
    return str(binary % (10 ** digits)).zfill(digits)


def verify_mfa(secret_b32, code, window=1):
    """Prüft TOTP mit ±window Halbminuten-Toleranz."""
    now = int(time.time())
    for w in range(-window, window + 1):
        if _totp(secret_b32, now + w * 30) == code:
            return True
    return False


def mfa_provisioning_uri(secret_b32, username, issuer="MicroTrader"):
    """otpauth:// URI für Authenticator-Apps."""
    label = f"{issuer}:{username}"
    return (f"otpauth://totp/{label}?secret={secret_b32}"
            f"&issuer={issuer}&algorithm=SHA1&digits=6&period=30")


def _generate_recovery_codes(count=RECOVERY_CODE_COUNT):
    """Phase 1 (§6): 8 einmalige Recovery-Codes (Basis32, ohne 0/O/1/I)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    codes = []
    for _ in range(count):
        codes.append("".join(secrets.choice(alphabet)
                             for _ in range(RECOVERY_CODE_LENGTH)))
    return codes



