#!/usr/bin/env python3
"""
test_server_security.py — Phase 10 Tests für Micro-Trader Server-Sicherheit.

Testet:
- Netzwerk: Bind 127.0.0.1 (config), keine 0.0.0.0, Debug off
- Auth: Login ok / falsch pw fail / Logout invalidiert
- Authz: Jede Rolle nur ihre Routen (PUBLIC/AUTHENTICATED/ANALYST/OPERATOR/ADMIN)
- Trading-Sicherheit: Paper/Shadow bleibt, keine Echtgeld-Pfade
- Regression: security.py Selbsttest, ROUTE_ACCESS Vollständigkeit

Start: python test_server_security.py  (Hermes-venv)
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import security as sec

OK = 0
FAIL = 0
def ck(name, cond, info=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [OK]   {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {info}")

print("=== PHASE 10: SECURITY TESTS ===\n")

# ─── 1. security.py Selbsttest (Basisfunktionen) ──────────────────
print("1. security.py Basisfunktionen")
ok, err = sec.create_user("__t__", "Test1234!", "user")
ck("create_user", ok, err)
ck("verify_password ok", sec.verify_password("__t__", "Test1234!"))
ck("verify_password wrong", not sec.verify_password("__t__", "falsch"))
sec_ = sec.generate_mfa_secret()
ck("mfa provisioning uri", sec.mfa_provisioning_uri(sec_, "__t__").startswith("otpauth://totp/"))
code = sec._totp(sec_, int(time.time()))
ck("mfa verify totp", sec.verify_mfa(sec_, code))
sid = sec.create_session("__t__", "127.0.0.1")
ck("session valid", sec.session_valid("__t__", sid))
tok = sec.generate_csrf_token()
ck("csrf token verify", sec.verify_csrf_token(tok))
sec.audit_log("test", "__t__", "selftest")
# cleanup
us = sec._load_users(); us.pop("__t__", None); sec._save_users(us)

# ─── 2. Rollen-Matrix (access_level_met) ─────────────────────────
print("\n2. Rollen-Vererbung (access_level_met)")
ck("visitor < user", not sec.access_level_met("visitor", "AUTHENTICATED"))
ck("user >= AUTHENTICATED", sec.access_level_met("user", "AUTHENTICATED"))
ck("analyst >= ANALYST", sec.access_level_met("analyst", "ANALYST"))
ck("operator >= OPERATOR", sec.access_level_met("operator", "OPERATOR"))
ck("admin >= ADMIN", sec.access_level_met("admin", "ADMIN"))
ck("superadmin >= SUPERADMIN", sec.access_level_met("superadmin", "SUPERADMIN"))
ck("user < ADMIN", not sec.access_level_met("user", "ADMIN"))
ck("analyst < OPERATOR", not sec.access_level_met("analyst", "OPERATOR"))

# ─── 3. ROUTE_ACCESS Vollständigkeit ────────────────────────────
print("\n3. ROUTE_ACCESS Mapping (Phase 6)")
# Alle echten Routen aus dashboard.py sammeln
import re
src = open("dashboard.py", encoding="utf-8", errors="replace").read()
routes = set(re.findall(r'@app\.route\("([^"]+)"', src))
missing = [r for r in routes if r not in sec.ROUTE_ACCESS and not r.startswith("/api/version")]
ck("alle HTML-Routen gemappt", len(missing) == 0, f"fehlend: {missing}")
# Kritische Routen korrekt klassifiziert
ck("/login PUBLIC", sec.route_class("/login") == "PUBLIC")
ck("/api/settings ADMIN", sec.route_class("/api/settings") == "ADMIN")
ck("/api/pause_trading OPERATOR", sec.route_class("/api/pause_trading") == "OPERATOR")
ck("/api/db_query ANALYST", sec.route_class("/api/db_query") == "ANALYST")
ck("/data AUTHENTICATED", sec.route_class("/data") == "AUTHENTICATED")
ck("/admin ADMIN", sec.route_class("/admin") == "ADMIN")

# ─── 4. Flask Bind (config) ─────────────────────────────────────
print("\n4. Netzwerk-Grenzen (Phase 2)")
m = re.search(r'app\.run\((.*?)\)', src, re.S)
runline = m.group(1) if m else ""
ck("bind 127.0.0.1 (nicht 0.0.0.0)", "127.0.0.1" in runline and "0.0.0.0" not in runline, runline)
ck("debug=False", "debug=False" in runline, runline)

# ─── 5. Trading-Sicherheit (Paper/Shadow ONLY) ─────────────────
print("\n5. Trading-Sicherheit (kein Echtgeld)")
ck("keine broker/api keys im Code", not re.search(r"(broker|live_trade|real_money|echetgeld)", src, re.I))
ck("pause_flag.json Mechanismus vorhanden", os.path.exists("pause_flag.json") or "pause_trading" in src)

# ─── 6. Flask test_client (Auth-Flow) ───────────────────────────
print("\n6. Auth-Flow via Flask test_client")
try:
    import dashboard
    app = dashboard.app
    app.config["TESTING"] = True
    c = app.test_client()
    # Landingpage öffentlich
    r = c.get("/")
    ck("Landingpage öffentlich (200)", r.status_code == 200)
    ck("Landingpage ohne internes JSON", "Depotwerte" not in r.get_data(as_text=True))
    # /data ohne Login -> redirect/login
    r = c.get("/data")
    ck("/data ohne Auth -> 302/401", r.status_code in (302, 401))
    # /admin ohne Login -> 302/401
    r = c.get("/admin")
    ck("/admin ohne Auth -> 302/401", r.status_code in (302, 401))
    # Login mit Testuser
    sec.create_user("__flow__", "Flow1234!", "admin")
    r = c.post("/login", data={"username": "__flow__", "password": "Flow1234!"})
    ck("Login POST -> redirect", r.status_code in (302, 303), str(r.status_code))
    # Session-Cookie vorhanden (prüfe alle Set-Cookie-Header)
    cookies = r.headers.getlist("Set-Cookie")
    ck("Session-Cookie gesetzt", any("sid=" in c for c in cookies), str(cookies))
    # /admin mit Session
    r2 = c.get("/admin")
    ck("/admin mit Auth -> 200", r2.status_code == 200)
    # Logout
    c.get("/logout")
    r3 = c.get("/admin")
    ck("/admin nach Logout -> 302/401", r3.status_code in (302, 401))
    # cleanup
    us = sec._load_users(); us.pop("__flow__", None); sec._save_users(us)
except Exception as e:
    ck("Flask test_client", False, str(e))

# ─── Phase 15: Benutzerverwaltung-API (v2.23.0) ─────────────────────────────
print("\n7. Benutzerverwaltung-API (v2.23.0)")
try:
    import dashboard
    app = dashboard.app; app.config["TESTING"] = True
    c = app.test_client()
    # Ohne Auth -> 401
    r = c.get("/api/users")
    ck("/api/users ohne Auth -> 401", r.status_code == 401)
    r = c.get("/api/me")
    ck("/api/me ohne Auth -> 401", r.status_code == 401)
    # Admin-Login
    c.post("/", data={"username": "admin", "password": "MicroTrader2026!"})
    r = c.get("/api/me")
    j = r.get_json()
    ck("/api/me als admin -> 200 + superadmin", r.status_code == 200 and j.get("role") == "superadmin")
    r = c.get("/api/users")
    ck("/api/users als admin -> 200", r.status_code == 200 and "users" in (r.get_json() or {}))
    # Create/409/Role/Deactivate/ResetPW/Revoke
    r = c.post("/api/users/create", json={"username": "__v23__", "password": "TestPass123!", "role": "analyst"})
    ck("create -> 200", r.status_code == 200)
    r = c.post("/api/users/create", json={"username": "__v23__", "password": "TestPass123!", "role": "analyst"})
    ck("create dup -> 409", r.status_code == 409)
    r = c.post("/api/users/__v23__/role", json={"role": "operator"})
    ck("role -> 200", r.status_code == 200)
    r = c.post("/api/users/__v23__/deactivate", json={"active": False})
    ck("deactivate -> 200", r.status_code == 200)
    r = c.post("/api/users/__v23__/reset-pw", json={"password": "NeuPass123!"})
    ck("reset-pw -> 200", r.status_code == 200)
    r = c.post("/api/users/__v23__/revoke")
    ck("revoke -> 200", r.status_code == 200)
    # Nicht-Admin darf /api/users NICHT sehen
    c2 = app.test_client()
    c2.post("/", data={"username": "__v23__", "password": "NeuPass123!"})
    r = c2.get("/api/users")
    ck("Nicht-Admin /api/users -> 403/401", r.status_code in (401, 403))
    # cleanup
    us = sec._load_users(); us.pop("__v23__", None); sec._save_users(us)
except Exception as e:
    ck("Benutzerverwaltung-API", False, str(e))

# ─── Zusammenfassung ─────────────────────────────────────────────
print(f"\n=== ERGEBNIS: {OK} OK, {FAIL} FAIL ===")
sys.exit(1 if FAIL else 0)
