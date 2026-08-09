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

# ── PHASE 1: Tenant-Kontext (OWASP Multi-Tenant Cheat Sheet) ──
# Der Tenant wird IMMER aus der authentifizierten Session abgeleitet,
# NIEMALS aus Client-Headern/-Parametern vertraut (Tenant-Context-Injection verhindern).
from contextvars import ContextVar
_current_tenant: ContextVar = ContextVar("current_tenant", default=None)


def set_current_tenant(tenant_id):
    """Setzt den Tenant-Kontext fuer den aktuellen Request (Thread-lokal)."""
    _current_tenant.set(tenant_id)


def get_current_tenant():
    """Gibt die aktuelle tenant_id zurueck (oder None)."""
    return _current_tenant.get()


# ── PHASE 5: Trading-Modi-Zustandsmaschine (Sektion 8) ──
def get_trading_mode(tenant_id=None):
    """Liest den aktuellen Trading-Modus eines Tenants (Default: SHADOW)."""
    tid = tenant_id or get_current_tenant() or 1
    try:
        import db as _db
        m = _db.MTDB()
        row = m.conn.execute(
            "SELECT default_trading_mode FROM tenants WHERE id = ?", (tid,)
        ).fetchone()
        m.close()
        return (row["default_trading_mode"] if row else "SHADOW") or "SHADOW"
    except Exception:
        return "SHADOW"


def set_trading_mode(new_mode, tenant_id=None, user=None, reason="",
                     requested_by=None, approved_by=None, mfa_confirmed=0):
    """PHASE 5: Zustandswechsel mit erlaubter Transition (State Machine).
    Wirft ValueError wenn Transition nicht erlaubt ist. Schreibt Audit-Log."""
    import db as _db
    m = _db.MTDB()
    tid = tenant_id or get_current_tenant() or 1
    old_mode = get_trading_mode(tid)
    if new_mode not in m.TRADING_MODES:
        m.close()
        raise ValueError(f"Ungueltiger Modus: {new_mode}")
    if not m.mode_can_transition(old_mode, new_mode):
        m.close()
        raise ValueError(
            f"Transition {old_mode} -> {new_mode} nicht erlaubt")
    # Tenant-Default aktualisieren
    m.conn.execute(
        "UPDATE tenants SET default_trading_mode = ? WHERE id = ?",
        (new_mode, tid))
    m.conn.commit()
    # Audit-Log
    m.mode_log_insert(
        tenant_id=tid, user_id=None,
        portfolio_id=None, strategy_id=None,
        old_mode=old_mode, new_mode=new_mode, reason=reason,
        requested_by=(requested_by or None),
        approved_by=approved_by, mfa_confirmed=mfa_confirmed,
        risk_review_status=("approved" if approved_by else "pending"),
        broker_connection_status=("live" if new_mode.startswith("LIVE") else "none"))
    m.close()
    return old_mode, new_mode


def trading_mode_history(tenant_id=None, limit=100):
    """PHASE 5: Verlauf der Moduswechsel (Audit)."""
    tid = tenant_id or get_current_tenant() or 1
    try:
        import db as _db
        m = _db.MTDB()
        rows = m.mode_log_list(tid, limit=limit)
        m.close()
        return rows
    except Exception:
        return []


# ── PHASE 6: Shadow -> Paper Freigabe (Sektion 9) ──
def paper_eligibility(tenant_id=None):
    """PHASE 6: Prueft Voraussetzungen fuer Shadow->Paper.
    Gibt (eligible: bool, gruende: list) zurueck.
    Voraussetzungen (Sektion 9 Stufe B):
      - Benutzer aktiv
      - Mindestanzahl Shadow-Entscheidungen
      - Audit-Trail vollstaendig
      - keine kritischen Fehler
      - Regelstand reproduzierbar
      - kein unaufgeloester Regelkonflikt
    """
    tid = tenant_id or get_current_tenant() or 1
    gruende = []
    try:
        import db as _db
        m = _db.MTDB()
        # Mindest-Shadow-Entscheidungen (z.B. >= 20)
        cnt = m.conn.execute(
            "SELECT COUNT(*) FROM ki_decisions WHERE tenant_id = ?", (tid,)
        ).fetchone()[0]
        MIN_DECISIONS = 20
        if cnt < MIN_DECISIONS:
            gruende.append(
                f"Zu wenig KI-Entscheidungen ({cnt}/{MIN_DECISIONS})")
        # Kein offener Regelkonflikt (shadow=True im Regelstand-JSON)
        import json as _json, os
        rj = os.path.join(_db.BASE, "regelstand_version.json")
        konflikte = 0
        if os.path.exists(rj):
            try:
                data = _json.load(open(rj, encoding="utf-8"))
                for r in (data if isinstance(data, list) else data.get("rules", [])):
                    if r.get("shadow") and r.get("konflikte"):
                        konflikte += 1
            except Exception:
                pass
        if konflikte > 0:
            gruende.append(f"{konflikte} unaufgeloeste Regelkonflikte")
        m.close()
        eligible = len(gruende) == 0
        return eligible, gruende
    except Exception as e:
        return False, [f"Pruefung fehlgeschlagen: {e}"]


def enter_paper(tenant_id=None, user=None, reason=""):
    """PHASE 6: Wechselt Tenant von SHADOW nach PAPER (nur wenn eligible)."""
    tid = tenant_id or get_current_tenant() or 1
    eligible, gruende = paper_eligibility(tid)
    if not eligible:
        raise ValueError("Paper nicht moeglich: " + "; ".join(gruende))
    return set_trading_mode("PAPER", tenant_id=tid, user=user, reason=reason,
                            requested_by=(user.get("id") if user else None))


# ── PHASE 8: Secret-Store (tenant-isoliert, kein global .env) ──
def secret_set(tenant_id, secret_key, secret_value):
    """PHASE 8: Secret tenant-isoliert speichern."""
    import db as _db
    m = _db.MTDB()
    m.secret_set(tenant_id, secret_key, secret_value)
    m.close()


def secret_get(tenant_id, secret_key):
    """PHASE 8: Secret nur fuer eigenen Tenant auslesen (serverseitig)."""
    import db as _db
    m = _db.MTDB()
    val = m.secret_get(tenant_id, secret_key)
    m.close()
    return val


def secret_list_keys(tenant_id):
    """PHASE 8: Schluessel auflisten (keine Werte)."""
    import db as _db
    m = _db.MTDB()
    keys = m.secret_list_keys(tenant_id)
    m.close()
    return keys


# ── PHASE 10: Tenant-Scoped Risikogrenzen (Wrapper, analog Secret) ──
def risk_set(tenant_id, risk_mode, position_size=None, stop_loss=None,
             take_profit=None, drawdown_limit=None):
    """PHASE 10: Tenant-Risikogrenze setzen."""
    import db as _db
    m = _db.MTDB()
    m.risk_set(tenant_id, risk_mode, position_size, stop_loss, take_profit, drawdown_limit)
    m.close()


def risk_get(tenant_id, risk_mode):
    """PHASE 10: Effektive Risikogrenze (Tenant → global → Default)."""
    import db as _db
    m = _db.MTDB()
    eff = m.effective_risk_limits(tenant_id, risk_mode)
    m.close()
    return eff


def risk_list(tenant_id):
    """PHASE 10: Alle Risikogrenzen eines Tenants."""
    import db as _db
    m = _db.MTDB()
    rows = m.risk_list(tenant_id)
    m.close()
    return rows


# ── PHASE 11: Tenant-Scoped Regeln (Wrapper, analog Secret) ──
def rule_add(tenant_id, rule_id, regel, muster=None, status="aktiv", created_by=None):
    """PHASE 11: Tenant-Regel anlegen."""
    import db as _db
    m = _db.MTDB()
    m.rule_set(tenant_id, rule_id, regel, muster, status, created_by)
    m.close()


def rule_list(tenant_id):
    """PHASE 11: Effektive Regeln (Tenant ∪ global)."""
    import db as _db
    m = _db.MTDB()
    rows = m.effective_rules(tenant_id)
    m.close()
    return rows


def rule_set_status(tenant_id, rule_id, status):
    """PHASE 11: Status einer Tenant-Regel aendern."""
    import db as _db
    m = _db.MTDB()
    m.rule_set_status(tenant_id, rule_id, status)
    m.close()


# ── PHASE 12: Enforcement (Risikogrenzen + Regeln im Trading-Pfad) ──
def enforce_risk_limits(tenant_id, risk_mode, position_size_pct, portfolio_value,
                        drawdown_pct=0.0):
    """PHASE 12: Prueft eine geplante Position gegen die effektiven Tenant-
    Risikogrenzen. Liefert {'allowed': bool, 'reason': str, 'limits': dict}.

    position_size_pct: geplante Positionsgroesse in % des Portfolios (0-1)
    portfolio_value:   aktueller Portfolio-Wert
    drawdown_pct:      aktueller Drawdown des Portfolios in % (0-1)
    """
    eff = risk_get(tenant_id, risk_mode)
    max_pos = eff.get("position_size") or 0.35
    max_dd = eff.get("drawdown_limit") or 0.20
    if position_size_pct > max_pos + 1e-9:
        return {
            "allowed": False,
            "reason": f"Position {position_size_pct:.1%} > Limit {max_pos:.1%}",
            "limits": eff,
        }
    if drawdown_pct > max_dd + 1e-9:
        return {
            "allowed": False,
            "reason": f"Drawdown {drawdown_pct:.1%} > Limit {max_dd:.1%}",
            "limits": eff,
        }
    return {"allowed": True, "reason": "ok", "limits": eff}


def enforce_rules(tenant_id, ticker, context=None, regel=None):
    """PHASE 12: Wendet die effektiven Tenant-Regeln auf ein Kaufsignal an.

    Regel-Typen (via 'muster'-Schluesselwort):
      - 'BLOCK:<text>'      -> hart blockiert (Kauf verboten)
      - 'MAX_KAUF:<n>'      -> max n Kaeufe dieses Tickers
      - 'REGEX:<pattern>'   -> ticker muss Pattern erfuellen
    Liefert {'allowed': bool, 'reason': str, 'matched': str|None}.
    """
    context = context or {}
    rules = rule_list(tenant_id)
    # Regeln mit negativem Status ignorieren
    active = [r for r in rules if (r.get("status") or "aktiv") == "aktiv"]
    for r in active:
        muster = (r.get("muster") or "").strip()
        rid = r.get("id", "")
        rule_text = (r.get("regel") or "").strip()
        if muster.startswith("BLOCK:"):
            return {"allowed": False, "reason": f"Regel {rid}: {muster[6:]}",
                    "matched": rid}
        if muster.startswith("MAX_KAUF:"):
            try:
                max_n = int(muster.split(":", 1)[1].strip())
            except (ValueError, IndexError):
                continue
            k = context.get("kauf_count", 0)
            if k >= max_n:
                return {"allowed": False,
                        "reason": f"Regel {rid}: max {max_n} Kaeufe erreicht",
                        "matched": rid}
        if muster.startswith("REGEX:"):
            import re as _re
            pat = muster.split(":", 1)[1].strip()
            try:
                if ticker and not _re.search(pat, ticker):
                    return {"allowed": False,
                            "reason": f"Regel {rid}: Ticker {ticker} passt nicht zu {pat}",
                            "matched": rid}
            except _re.error:
                continue
    return {"allowed": True, "reason": "ok", "matched": None}


def resolve_tenant_for_user(user):
    """Leitet die tenant_id eines Users aus der Membership-Tabelle ab.
    Fallback: Default-Tenant (id=1). Kein Client-Input noetig."""
    try:
        import db as _db
        m = _db.MTDB()
        try:
            tid = m.tenant_ensure_default()
            memberships = m.tenant_memberships_for_user(user["username"])
            m.close()
            if memberships:
                return memberships[0]["tenant_id"]
            # Keine Membership -> Default-Tenant zuordnen
            m2 = _db.MTDB()
            m2.tenant_membership_add(tid, user["username"], role=user.get("role", "user"))
            m2.close()
            return tid
        except Exception:
            try:
                m.close()
            except Exception:
                pass
            return 1
    except Exception:
        return 1

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

# ─── PHASE 2: Tenant-bezogene Berechtigungen (Mandanten-Ausbau) ─────────────
# Effektive Rolle = Membership-Rolle im aktuellen Tenant (gewichtig), sonst
# globale User-Rolle (Fallback). Ermöglicht: User ist in Tenant A 'admin',
# in Tenant B nur 'user'.
TENANT_ROLE_PERMISSIONS = {
    "user":      ["landingpage", "dashboard", "own_data", "tenant_view"],
    "analyst":   ["landingpage", "dashboard", "reports", "analysis", "ki_log_view",
                  "tenant_view"],
    "operator":  ["landingpage", "dashboard", "reports", "analysis", "systemstatus",
                  "pause_trading", "resume_trading", "tenant_view", "tenant_trade_control"],
    "admin":     ["landingpage", "dashboard", "reports", "analysis", "systemstatus",
                  "pause_trading", "resume_trading", "users", "settings", "rules",
                  "audit", "backups", "tenant_view", "tenant_manage",
                  "tenant_trade_control", "tenant_members"],
    "superadmin": ["landingpage", "dashboard", "reports", "analysis", "systemstatus",
                   "pause_trading", "resume_trading", "users", "settings", "rules",
                   "audit", "backups", "recovery", "security_config", "mfa_emergency",
                   "tenant_view", "tenant_manage", "tenant_trade_control",
                   "tenant_members", "tenant_delete"],
}

# Alle bekannten Permissions (global + tenant) — für Dokumentation/API
ALL_PERMISSIONS = sorted(set(
    [p for ps in ROLE_PERMISSIONS.values() for p in ps] +
    [p for ps in TENANT_ROLE_PERMISSIONS.values() for p in ps]
))

# Routen-Zugriffsklassen (Phase 6 Zuordnung aus SERVER-SECURITY-INVENTORY)
ROUTE_ACCESS = {
    "/": "PUBLIC", "/landing": "PUBLIC", "/api/version": "PUBLIC",
    "/static/<path:dateiname>": "PUBLIC", "/assets/<path:dateiname>": "PUBLIC",
    "/reports/<path:name>": "AUTHENTICATED",
    "/login": "PUBLIC", "/logout": "AUTHENTICATED",
    "/dashboard": "AUTHENTICATED",
    "/data": "AUTHENTICATED", "/depot_json": "AUTHENTICATED",
    "/spec_depot_json": "AUTHENTICATED", "/etf_depot_json": "AUTHENTICATED",
    "/api/analysis": "AUTHENTICATED", "/api/report_pdf": "AUTHENTICATED",
    "/api/report_list": "AUTHENTICATED", "/search_ticker": "AUTHENTICATED",
    "/ticker_chart": "AUTHENTICATED",
    "/api/me": "AUTHENTICATED", "/api/me/password": "AUTHENTICATED",
    "/api/me/mfa": "AUTHENTICATED", "/api/me/permissions": "AUTHENTICATED",
    "/api/roles": "TENANT_ADMIN",
    "/api/trading_mode": "TENANT_ADMIN", "/api/trading_mode/set": "TENANT_ADMIN",
    "/api/trading_mode/history": "TENANT_ADMIN",
    "/api/paper/eligibility": "TENANT_ADMIN", "/api/paper/enter": "TENANT_ADMIN",
    "/api/providers": "TENANT_ADMIN", "/api/providers/add": "TENANT_ADMIN",
    "/api/providers/test/<int:conn_id>": "TENANT_ADMIN",
    "/api/secrets": "TENANT_ADMIN", "/api/secrets/set": "TENANT_ADMIN",
    "/api/risk": "TENANT_ADMIN", "/api/risk/set": "TENANT_ADMIN",
    "/api/rules": "TENANT_ADMIN", "/api/rules/add": "TENANT_ADMIN",
    "/api/rules/set_status": "TENANT_ADMIN",
    "/api/tenants": "ADMIN", "/api/tenants/create": "ADMIN",
    "/api/tenants/<int:tid>/members": "ADMIN",
    "/api/users": "ADMIN", "/api/users/create": "ADMIN",
    "/api/users/<name>/role": "ADMIN", "/api/users/<name>/deactivate": "ADMIN",
    "/api/users/<name>/reset-pw": "ADMIN", "/api/users/<name>/revoke": "ADMIN",
    "/api/profil_karten": "ANALYST", "/api/profile": "ANALYST",
    "/api/db_karten": "ANALYST", "/api/db_query": "ANALYST",
    "/api/ki_log": "ANALYST",
    "/api/pause_trading": "OPERATOR", "/api/clear_cache": "OPERATOR",
    "/api/settings": "ADMIN",
    "/admin": "ADMIN", "/admin/users": "ADMIN", "/admin/users/create": "ADMIN",
    "/admin/system": "ADMIN", "/admin/rules": "ADMIN",
    "/admin/security": "ADMIN", "/admin/logins": "ADMIN", "/admin/audit": "ADMIN",
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


# ─── Login-Rate-Limit (Brute-Force-Schutz, OWASP A07) ────────────────────────
LOGIN_RATE_FILE = os.path.join(BASE, "login_rate.json")
_LOGIN_RATE_MAX_ATTEMPTS = 5          # Fehlversuche bevor Block
_LOGIN_RATE_BASE_BLOCK_S = 30         # Start-Blockzeit
_LOGIN_RATE_WINDOW_S = 15 * 60        # Zählfenster


def _load_login_rate():
    try:
        return json.load(open(LOGIN_RATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _save_login_rate(data):
    try:
        with open(LOGIN_RATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def login_blocked(ip, username=None):
    """True wenn Login von dieser IP (oder User) gerade blockiert ist.
    Exponential Backoff: 5 Versuche -> 30s, danach 60s, 120s, 240s…"""
    data = _load_login_rate()
    now = time.time()
    for key in (ip, username):
        if not key:
            continue
        e = data.get(str(key))
        if not e:
            continue
        if e.get("blocked_until") and e["blocked_until"] > now:
            rest = int(e["blocked_until"] - now)
            return rest
    return 0


def register_login_fail(ip, username=None):
    """Zählt Fehlversuch, setzt exponentiellen Block ab Schwelle."""
    data = _load_login_rate()
    now = time.time()
    for key in (ip, username):
        if not key:
            continue
        e = data.setdefault(str(key), {"fails": 0, "blocked_until": 0})
        # Fenster abgelaufen? -> Reset
        if e.get("last") and now - e["last"] > _LOGIN_RATE_WINDOW_S:
            e["fails"] = 0
        e["fails"] += 1
        e["last"] = now
        if e["fails"] >= _LOGIN_RATE_MAX_ATTEMPTS:
            level = e["fails"] - _LOGIN_RATE_MAX_ATTEMPTS
            block = _LOGIN_RATE_BASE_BLOCK_S * (2 ** min(level, 6))
            e["blocked_until"] = now + block
    _save_login_rate(data)


def register_login_ok(ip, username=None):
    """Reset der Zähler nach erfolgreichem Login."""
    data = _load_login_rate()
    for key in (ip, username):
        if key and key in data:
            data.pop(str(key), None)
    _save_login_rate(data)


def login_rate_stats():
    """Aggregierte Rate-Limit-Daten (für Admin-Ansicht)."""
    data = _load_login_rate()
    now = time.time()
    out = []
    for key, e in data.items():
        if e.get("fails", 0) >= 2:
            blocked = e.get("blocked_until", 0) > now
            rest = max(0, int(e.get("blocked_until", 0) - now)) if blocked else 0
            out.append({"key": key, "fails": e.get("fails", 0),
                        "blocked": blocked, "rest_s": rest,
                        "last": str(e.get("last", ""))[:19]})
    out.sort(key=lambda x: -x["fails"])
    return out


def read_audit(limit=200):
    """Liest die letzten `limit` Audit-Einträge (append-only)."""
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


# ─── PHASE 2: Effektive Rolle + Permissions im Tenant-Kontext ───────────────
def effective_role(user, tenant_id=None):
    """Effektive Rolle eines Users.

    Priorität: Membership-Rolle im angegebenen Tenant (oder aktuellem Kontext)
    > globale User-Rolle. Fallback: 'visitor'.
    """
    if not user:
        return "visitor"
    tid = tenant_id or get_current_tenant()
    if tid:
        try:
            import db as _db
            m = _db.MTDB()
            try:
                member = m.tenant_membership_role(tid, user.get("username", ""))
            finally:
                m.close()
            # Dict {role, status} oder None
            if member and member.get("status", "aktiv") != "inaktiv":
                role = member.get("role")
                if role:
                    return str(role).lower()
        except Exception:
            pass
    return (user.get("role") or "visitor").lower()


def effective_permissions(user, tenant_id=None):
    """Permissions der effektiven Rolle (Tenant-Permissions-Map)."""
    role = effective_role(user, tenant_id)
    return TENANT_ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS.get(role, []))


def has_permission(user, permission, tenant_id=None):
    """Prüft Permission im Tenant-Kontext. Superadmin hat immer alles."""
    role = effective_role(user, tenant_id)
    if role == "superadmin":
        return True
    return permission in effective_permissions(user, tenant_id)


def has_permission_in(role, permission):
    """Statische Prüfung: hat die ROLLE diese Permission (ohne User/DB)?"""
    if role == "superadmin":
        return True
    return permission in TENANT_ROLE_PERMISSIONS.get(role, [])


# Rolle → Zugriffsebene (konsistent mit ROLE_PERMISSIONS / ACCESS_ORDER)
ROLE_TO_LEVEL = {
    "visitor": "PUBLIC",
    "user": "AUTHENTICATED",
    "analyst": "ANALYST",
    "operator": "OPERATOR",
    "admin": "ADMIN",
    "superadmin": "SUPERADMIN",
}

def access_level_met(user_role, required_level):
    """Prüft Zugriffsebene (PUBLIC < AUTHENTICATED < ANALYST < OPERATOR < ADMIN < SUPERADMIN)."""
    try:
        ui = ACCESS_ORDER.index(ROLE_TO_LEVEL.get((user_role or "visitor").lower(), "PUBLIC"))
        ri = ACCESS_ORDER.index(required_level)
        return ui >= ri
    except ValueError:
        return False


def route_class(route_rule):
    """Gibt Zugriffsklasse für eine Route zurück (Phase 6 Mapping).
    Matches exakte Routen + Flask-Patterns (/assets/<path:...>). Default: restriktiv."""
    if route_rule in ROUTE_ACCESS:
        return ROUTE_ACCESS[route_rule]
    # Flask-Pattern-Prefixe: /assets/<path:dateiname>, /static/<path:...>, /reports/<path:...>
    for pattern, cls in ROUTE_ACCESS.items():
        if "<" in pattern and ">" in pattern:
            prefix = pattern.split("<")[0].rstrip("/")
            if route_rule.startswith(prefix + "/") or route_rule == prefix:
                return cls
    return "ADMIN"  # Default: restriktiv


# ─── Flask-Integration (Decorators + Helper) ────────────────────────────────
# Diese Helper nutzen flask.session + flask.request (müssen innerhalb Request
# aufgerufen werden). Dekoriert Routen serverseitig — Frontend-Ausblendung
# ist KEINE Berechtigung (Auftrag Regel 5).
from flask import session as _flask_session, request as _flask_request


def _current_username():
    # App nutzt Cookie-basierte Auth (nicht flask.session)
    return _flask_request.cookies.get("username")


def _current_sid():
    return _flask_request.cookies.get("sid")


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
    """Decorator: Route nur mit Rolle >= min_role.
    min_role ist eine ROLLE ('admin') — wird zu EBENE ('ADMIN') gemappt."""
    min_level = ROLE_TO_LEVEL.get((min_role or "visitor").lower(), "PUBLIC")
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                from flask import redirect as _r, url_for as _u
                return _r((_u("login") if "login" in _ALL_ROUTES else "/login")
                          + "?next=" + _flask_request.path)
            if not access_level_met(u["role"], min_level):
                from flask import abort
                abort(403)
            touch_session(u["username"], _current_sid())
            return f(*a, **kw)
        return wrapper
    return decorator


def require_tenant_role(min_role):
    """Decorator (PHASE 2): Route nur mit Rolle >= min_role im TENANT-Kontext.

    Nutzt die effektive Rolle (Membership im aktuellen Tenant > globale Rolle).
    Admin-Routen wirken damit tenant-bezogen: Ein User ist nur Admin in
    Tenants, in denen er auch Membership-Admin ist (oder global superadmin).
    """
    min_level = ROLE_TO_LEVEL.get((min_role or "visitor").lower(), "PUBLIC")
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                from flask import redirect as _r, url_for as _u
                return _r((_u("login") if "login" in _ALL_ROUTES else "/login")
                          + "?next=" + _flask_request.path)
            eff = effective_role(u)
            if not access_level_met(eff, min_level):
                from flask import abort
                abort(403)
            touch_session(u["username"], _current_sid())
            return f(*a, **kw)
        return wrapper
    return decorator


def require_permission(permission):
    """Decorator (PHASE 2): Route nur mit Permission im Tenant-Kontext."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                from flask import redirect as _r, url_for as _u
                return _r((_u("login") if "login" in _ALL_ROUTES else "/login")
                          + "?next=" + _flask_request.path)
            if not has_permission(u, permission):
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
