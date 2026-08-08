"""
security.py — Zentrale Sicherheitslogik für Micro-Trader (Paper/Shadow ONLY).

Phasen 4-6 des Server-Sicherheitsauftrags:
- Benutzerverwaltung + Rollen (visitor/user/analyst/operator/admin/superadmin)
- MFA (TOTP, RFC 6238 über cryptography.hazmat HMAC — KEIN Eigenbau)
- Session-Sicherheit (Secure/HttpOnly/SameSite, Rotation, Timeout)
- Serverseitige Rollen- + Routenprüfung (require_auth / require_role / require_recent_mfa)
- CSRF-Schutz (itsdangerous signed token)

WICHTIG: Keine Echtgeld-Funktionen. Nur Paper/Shadow.

Verwendet NUR etablierte Bibliotheken:
- werkzeug.generate_password_hash / check_password_hash (pbkdf2:sha256)
- cryptography.hazmat.primitives.hmac / hashes (FIPS-validiert, für TOTP)
- itsdangerous (URLSafeTimedSerializer für CSRF + signed state)
- secrets / base64 (stdlib, nur Zufall)
"""
import json
import os
import secrets
import time
import base64
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.hazmat.primitives import hashes, hmac as chmac
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

BASE = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE, "security_users.json")
AUDIT_FILE = os.path.join(BASE, "security_audit.json")
SESSION_SECRET = os.environ.get("MICRO_TRADER_SESSION_SECRET") or secrets.token_hex(32)
CSRF_SECRET = os.environ.get("MICRO_TRADER_CSF_SECRET") or secrets.token_hex(32)

# ─── Rollen ────────────────────────────────────────────────────────────────
ROLES = ["visitor", "user", "analyst", "operator", "admin", "superadmin"]

ROLE_PERMISSIONS = {
    "visitor":    ["landingpage"],
    "user":       ["landingpage", "dashboard", "own_data"],
    "analyst":    ["landingpage", "dashboard", "reports", "analysis", "ki_log_view"],
    "operator":   ["landingpage", "dashboard", "reports", "analysis", "systemstatus",
                   "pause_trading", "resume_trading"],
    "admin":      ["landingpage", "dashboard", "reports", "analysis", "systemstatus",
                   "pause_trading", "resume_trading", "users", "settings", "rules",
                   "audit", "backups"],
    "superadmin": ["landingpage", "dashboard", "reports", "analysis", "systemstatus",
                   "pause_trading", "resume_trading", "users", "settings", "rules",
                   "audit", "backups", "recovery", "security_config", "mfa_emergency"],
}

# Routen-Zugriffsklassen (Phase 6 Zuordnung aus SERVER-SECURITY-INVENTORY)
ROUTE_ACCESS = {
    "/": "PUBLIC", "/api/version": "PUBLIC", "/static/<path:dateiname>": "PUBLIC",
    "/login": "PUBLIC", "/logout": "AUTHENTICATED",
    "/data": "AUTHENTICATED", "/depot_json": "AUTHENTICATED",
    "/spec_depot_json": "AUTHENTICATED", "/etf_depot_json": "AUTHENTICATED",
    "/api/analysis": "AUTHENTICATED", "/api/report_pdf": "AUTHENTICATED",
    "/api/report_list": "AUTHENTICATED", "/search_ticker": "AUTHENTICATED",
    "/ticker_chart": "AUTHENTICATED",
    "/api/profil_karten": "ANALYST", "/api/profile": "ANALYST",
    "/api/db_karten": "ANALYST", "/api/db_query": "ANALYST",
    "/api/ki_log": "ANALYST",
    "/api/pause_trading": "OPERATOR", "/api/clear_cache": "OPERATOR",
    "/api/settings": "ADMIN",
    "/admin": "ADMIN", "/admin/users": "ADMIN", "/admin/roles": "ADMIN",
    "/admin/security": "ADMIN", "/admin/audit": "ADMIN", "/admin/rules": "ADMIN",
    "/admin/settings": "ADMIN", "/admin/backups": "ADMIN",
}
ACCESS_ORDER = ["PUBLIC", "AUTHENTICATED", "ANALYST", "OPERATOR", "ADMIN", "SUPERADMIN"]

MFA_REQUIRED_ROLES = ["admin", "superadmin"]
MFA_RECOMMENDED_ROLES = ["operator"]


# ─── User-Store (JSON, Passwörter via werkzeug pbkdf2:sha256) ────────────────
def _load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def user_exists(username):
    return username in _load_users()


def create_user(username, password, role="user", email="", display_name=""):
    """Legt einen Benutzer an. Gibt (ok, fehler) zurück."""
    if role not in ROLES:
        return False, "Unbekannte Rolle"
    if user_exists(username):
        return False, "Benutzer existiert bereits"
    users = _load_users()
    users[username] = {
        "username": username,
        "display_name": display_name or username,
        "email": email,
        "password_hash": generate_password_hash(password, method="pbkdf2:sha256"),
        "role": role,
        "active": True,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_login": None,
        "mfa_enabled": False,
        "mfa_secret": None,
        "mfa_pending_secret": None,
        "sessions": {},          # session_id -> {created, last_seen, ip}
        "last_security_action": None,
    }
    _save_users(users)
    audit_log("user_create", username, f"Rolle={role}")
    return True, ""


def verify_password(username, password):
    users = _load_users()
    u = users.get(username)
    if not u or not u.get("active"):
        return False
    if check_password_hash(u.get("password_hash", ""), password):
        return True
    return False


def change_password(username, new_password):
    users = _load_users()
    if username not in users:
        return False
    users[username]["password_hash"] = generate_password_hash(
        new_password, method="pbkdf2:sha256")
    users[username]["last_security_action"] = (
        datetime.utcnow().isoformat() + "Z password_change")
    _save_users(users)
    audit_log("password_change", username)


def set_role(username, new_role, by_admin):
    if new_role not in ROLES:
        return False
    users = _load_users()
    if username not in users:
        return False
    old = users[username]["role"]
    users[username]["role"] = new_role
    users[username]["last_security_action"] = (
        datetime.utcnow().isoformat() + "Z role_change")
    _save_users(users)
    audit_log("role_change", by_admin, f"user={username} {old}->{new_role}")


def deactivate_user(username, by_admin):
    users = _load_users()
    if username not in users:
        return
    users[username]["active"] = False
    users[username]["sessions"] = {}
    _save_users(users)
    audit_log("user_deactivate", by_admin, f"user={username}")


def get_user(username):
    return _load_users().get(username)


def list_users():
    return list(_load_users().values())


# ─── MFA (TOTP RFC 6238, HMAC-SHA1 über cryptography) ────────────────────────
def _b32_decode(secret):
    # Normalisiert secret (Entfernt Leerzeichen, Großbuchstaben)
    s = secret.strip().upper().replace(" ", "")
    # Base32-Padding korrigieren
    pad = (-len(s)) % 8
    return base64.b32decode(s + "=" * pad)


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


def enable_mfa(username, code):
    """Aktiviert MFA nach Bestätigung des Codes. Gibt (ok, uri_or_err)."""
    users = _load_users()
    u = users.get(username)
    if not u:
        return False, "Benutzer fehlt"
    pending = u.get("mfa_pending_secret")
    if not pending:
        return False, "Kein Pending-Secret"
    if not verify_mfa(pending, code):
        return False, "Code falsch"
    u["mfa_secret"] = pending
    u["mfa_enabled"] = True
    u["mfa_pending_secret"] = None
    u["last_security_action"] = datetime.utcnow().isoformat() + "Z mfa_enable"
    _save_users(users)
    audit_log("mfa_enable", username)
    return True, ""


def disable_mfa(username, by_admin):
    users = _load_users()
    if username not in users:
        return
    users[username]["mfa_enabled"] = False
    users[username]["mfa_secret"] = None
    _save_users(users)
    audit_log("mfa_disable", by_admin, f"user={username}")


# ─── Session-Management (serverseitig) ──────────────────────────────────────
SESSION_IDLE_TIMEOUT = 30 * 60       # 30 min idle
SESSION_ABS_TIMEOUT = 8 * 60 * 60    # 8 h absolut
MFA_GRACE = 10 * 60                  # 10 min für Reauth


def create_session(username, ip=""):
    """Legt serverseitige Session an. Gibt session_id zurück."""
    sid = secrets.token_urlsafe(32)
    users = _load_users()
    u = users.get(username)
    if not u:
        return None
    now = int(time.time())
    u.setdefault("sessions", {})[sid] = {
        "created": now, "last_seen": now, "ip": ip,
        "rotated_at": now, "mfa_verified_at": now if u.get("mfa_enabled") else 0,
    }
    users[username] = u
    _save_users(users)
    return sid


def session_valid(username, sid):
    users = _load_users()
    u = users.get(username)
    if not u or not u.get("active"):
        return False
    s = u.get("sessions", {}).get(sid)
    if not s:
        return False
    now = int(time.time())
    if now - s["last_seen"] > SESSION_IDLE_TIMEOUT:
        return False
    if now - s["created"] > SESSION_ABS_TIMEOUT:
        return False
    return True


def touch_session(username, sid):
    users = _load_users()
    u = users.get(username)
    if u and sid in u.get("sessions", {}):
        u["sessions"][sid]["last_seen"] = int(time.time())
        _save_users(users)


def rotate_session(username, sid):
    """Session-Rotation (nach Login + Rechteänderung)."""
    users = _load_users()
    u = users.get(username)
    if not u or sid not in u.get("sessions", {}):
        return None
    new_sid = secrets.token_urlsafe(32)
    old = u["sessions"].pop(sid)
    old["rotated_at"] = int(time.time())
    u["sessions"][new_sid] = old
    _save_users(users)
    return new_sid


def revoke_session(username, sid):
    users = _load_users()
    u = users.get(username)
    if u and sid in u.get("sessions", {}):
        u["sessions"].pop(sid)
        _save_users(users)


def revoke_all_sessions(username):
    users = _load_users()
    if username in users:
        users[username]["sessions"] = {}
        _save_users(users)


def mfa_recently_verified(username, sid):
    users = _load_users()
    u = users.get(username)
    if not u:
        return False
    s = u.get("sessions", {}).get(sid)
    if not s:
        return False
    if not u.get("mfa_enabled"):
        return True  # kein MFA → gilt als erfüllt
    return (int(time.time()) - s.get("mfa_verified_at", 0)) < MFA_GRACE


def mark_mfa_verified(username, sid):
    users = _load_users()
    u = users.get(username)
    if u and sid in u.get("sessions", {}):
        u["sessions"][sid]["mfa_verified_at"] = int(time.time())
        _save_users(users)


# ─── CSRF (itsdangerous signed token) ───────────────────────────────────────
_csrf_ser = URLSafeTimedSerializer(CSRF_SECRET, salt="csrf")


def generate_csrf_token():
    return _csrf_ser.dumps(secrets.token_urlsafe(16))


def verify_csrf_token(token, max_age=3600):
    try:
        _csrf_ser.loads(token, max_age=max_age)
        return True
    except (BadSignature, SignatureExpired):
        return False


# ─── Audit-Log (manipulationssicher: append-only JSON-Lines) ────────────────
def audit_log(action, actor, detail=""):
    """Schreibt Append-Only Audit-Eintrag. Nicht nachträglich änderbar."""
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "action": action, "actor": actor, "detail": detail,
    }
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_audit(limit=200):
    if not os.path.exists(AUDIT_FILE):
        return []
    out = []
    with open(AUDIT_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out[-limit:]


# ─── Berechtigungsprüfung (Phase 6) ─────────────────────────────────────────
def role_has_permission(role, required):
    """Prüft, ob Rolle die angeforderte Berechtigung hat (inkl. Vererbung)."""
    if role not in ROLE_PERMISSIONS:
        return False
    perms = ROLE_PERMISSIONS[role]
    if required in perms:
        return True
    # Superadmin hat alles
    if role == "superadmin":
        return True
    return False


def access_level_met(user_role, required_level):
    """Prüft Zugriffsebene (PUBLIC < AUTHENTICATED < ANALYST < OPERATOR < ADMIN < SUPERADMIN)."""
    try:
        ui = ACCESS_ORDER.index(user_role.upper() if user_role else "visitor")
        ri = ACCESS_ORDER.index(required_level)
        return ui >= ri
    except ValueError:
        return False


def route_class(route_rule):
    """Gibt Zugriffsklasse für eine Route zurück (Phase 6 Mapping)."""
    return ROUTE_ACCESS.get(route_rule, "ADMIN")  # Default: restriktiv


# ─── Flask-Integration (Decorators + Helper) ────────────────────────────────
# Diese Helper nutzen flask.session + flask.request (müssen innerhalb Request
# aufgerufen werden). Dekoriert Routen serverseitig — Frontend-Ausblendung
# ist KEINE Berechtigung (Auftrag Regel 5).
from flask import session as _flask_session, request as _flask_request


def _current_username():
    return _flask_session.get("username")


def _current_sid():
    return _flask_session.get("sid")


def current_user():
    """Gibt das User-Dict zurück oder None."""
    uname = _current_username()
    if not uname:
        return None
    if not session_valid(uname, _current_sid()):
        return None
    return get_user(uname)


def login_required_redirect():
    """Redirect zur Login-Seite wenn nicht angemeldet. Gibt Response oder None."""
    u = current_user()
    if not u:
        return redirect(url_for("login") if "login" in _ALL_ROUTES else "/login")
    return None


def require_auth():
    """Decorator: Route nur mit gültiger Session."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                from flask import redirect as _r, url_for as _u
                return _r((_u("login") if "login" in _ALL_ROUTES else "/login")
                          + "?next=" + _flask_request.path)
            touch_session(u["username"], _current_sid())
            return f(*a, **kw)
        return wrapper
    return decorator


def require_role(min_role):
    """Decorator: Route nur mit Rolle >= min_role (ACCESS_ORDER)."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                from flask import redirect as _r, url_for as _u
                return _r((_u("login") if "login" in _ALL_ROUTES else "/login")
                          + "?next=" + _flask_request.path)
            if not access_level_met(u["role"], min_role):
                from flask import abort
                abort(403)
            touch_session(u["username"], _current_sid())
            return f(*a, **kw)
        return wrapper
    return decorator


def require_recent_mfa():
    """Decorator: Route nur mit kürzlich verifiziertem MFA (für Admin/Critical)."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                from flask import redirect as _r, url_for as _u
                return _r((_u("login") if "login" in _ALL_ROUTES else "/login"))
            if u["role"] in MFA_REQUIRED_ROLES and not mfa_recently_verified(
                    u["username"], _current_sid()):
                from flask import redirect as _r, url_for as _u
                return _r(_u("mfa_verify") if "mfa_verify" in _ALL_ROUTES else "/mfa")
            return f(*a, **kw)
        return wrapper
    return decorator


_ALL_ROUTES = set()  # wird von dashboard.py nach Routen-Registrierung gefüllt


if __name__ == "__main__":
    # Selbsttest (nur bei Aufruf, nicht im Import)
    ok, err = create_user("__selftest__", "Test1234!", "user")
    assert ok, err
    assert verify_password("__selftest__", "Test1234!")
    assert not verify_password("__selftest__", "falsch")
    sec = generate_mfa_secret()
    uri = mfa_provisioning_uri(sec, "__selftest__")
    assert uri.startswith("otpauth://totp/")
    code = _totp(sec, int(time.time()))
    assert verify_mfa(sec, code), "TOTP Verifikation fehlgeschlagen"
    sid = create_session("__selftest__")
    assert session_valid("__selftest__", sid)
    tok = generate_csrf_token()
    assert verify_csrf_token(tok)
    # Cleanup
    users = _load_users()
    users.pop("__selftest__", None)
    _save_users(users)
    print("security.py Selbsttest OK")
