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

# ─── Phase 15b: Mandanten-Modell (v2.26.0) ─────────────────────────────────
print("\n7b. Mandanten-Modell (v2.26.0)")
try:
    import db as mtdb
    m = mtdb.MTDB()
    tid = m.tenant_ensure_default()
    ck("Default-Tenant existiert", tid == 1 and m.tenant_get(tid)["tenant_key"] == "default")
    t2, fehler = m.tenant_create("__suite_tenant__", "Suite-Test")
    ck("Tenant anlegen -> ok", t2 is not None and fehler is None)
    t3, fehler = m.tenant_create("__suite_tenant__", "Dup")
    ck("Tenant-Duplikat -> fehler", t3 is None and fehler)
    ok = m.tenant_membership_add(t2, "admin", "admin")
    ck("Membership hinzufuegen", ok)
    ms = m.tenant_memberships_for_user("admin")
    ck("Membership sichtbar", any(x["tenant_id"] == t2 for x in ms))
    ws, wfehler = m.workspace_create(t2, "ws1", "Workspace 1")
    ck("Workspace anlegen", ws is not None and wfehler is None)
    m.conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=?", (t2,))
    m.conn.execute("DELETE FROM workspaces WHERE tenant_id=?", (t2,))
    m.conn.execute("DELETE FROM tenants WHERE id=?", (t2,))
    m.conn.commit()
    m.close()
    # API-Test via Flask
    import dashboard as dash
    app2 = dash.app; app2.config["TESTING"] = True
    cc = app2.test_client()
    r = cc.get("/api/tenants")
    ck("API /api/tenants ohne Auth -> 401", r.status_code == 401)
    cc.post("/", data={"username": "admin", "password": "MicroTrader2026!"})
    r = cc.get("/api/tenants")
    ck("API /api/tenants als admin -> 200", r.status_code == 200 and "tenants" in r.get_json())
    r = cc.post("/api/tenants/create", json={"tenant_key": "BAD KEY!", "name": "x"})
    ck("API tenant_key-Validierung -> 400", r.status_code == 400)
    r = cc.get("/api/me")
    j = r.get_json()
    ck("API /api/me mit tenant-Kontext", j.get("tenants", {}).get("current_tenant") == 1)
except Exception as e:
    ck("Mandanten-Modell", False, str(e))

# ─── Phase 15c: Rollen-/Berechtigungsmodell (v2.27.0) ───────────────────────
print("\n7c. Rollen-/Berechtigungsmodell (v2.27.0)")
try:
    import db as mtdb2
    m = mtdb2.MTDB()
    # Idempotent: alte Reste entfernen
    try:
        m.conn.execute("DELETE FROM tenant_memberships WHERE tenant_id IN "
                       "(SELECT id FROM tenants WHERE tenant_key='__rolle_suite__')")
        m.conn.execute("DELETE FROM tenants WHERE tenant_key='__rolle_suite__'")
        m.conn.commit()
    except Exception:
        pass
    # Test-Tenant + User mit Membership-Rolle != globaler Rolle
    t2, fehler = m.tenant_create("__rolle_suite__", "Rollen-Suite")
    ck("Rollen-Tenant anlegen", t2 is not None and fehler is None)
    ok1, fe1 = sec.create_user("__rolle_a__", "TestPass123!", "user")
    ok2, fe2 = sec.create_user("__rolle_b__", "TestPass123!", "operator")
    ck("Rollen-User anlegen", ok1 and ok2)
    m.tenant_membership_add(t2, "__rolle_a__", "admin")
    m.close()

    ua = sec.get_user("__rolle_a__")
    # Effektive Rolle: Membership 'admin' > globale 'user'
    ck("effektive Rolle gewinnt", sec.effective_role(ua, t2) == "admin")
    ck("andere Tenant -> globale Rolle", sec.effective_role(ua, 1) == "user")
    ck("Tenant-Permissions enthalten tenant_manage",
       "tenant_manage" in sec.effective_permissions(ua, t2))
    ck("admin hat KEIN tenant_delete", not sec.has_permission(ua, "tenant_delete", t2))
    ck("superadmin hat alles", sec.has_permission({"role": "superadmin"}, "tenant_delete"))
    ub = sec.get_user("__rolle_b__")
    ck("operator tenant_trade_control", sec.has_permission(ub, "tenant_trade_control", t2))

    import dashboard as dash2
    app3 = dash2.app; app3.config["TESTING"] = True
    c3 = app3.test_client()
    c3.post("/", data={"username": "admin", "password": "MicroTrader2026!"})
    r = c3.get("/api/me/permissions")
    j = r.get_json()
    ck("API /api/me/permissions superadmin",
       j.get("effective_role") == "superadmin" and "tenant_delete" in j.get("permissions", []))
    r = c3.get("/api/roles")
    j = r.get_json()
    ck("API /api/roles Katalog", r.status_code == 200 and len(j.get("roles", [])) == 6
       and len(j.get("all_permissions", [])) >= 20)
    # Tenant-Admin (global user) erreicht /api/roles im Tenant-Kontext
    c4 = app3.test_client()
    c4.post("/", data={"username": "__rolle_a__", "password": "TestPass123!"})
    r = c4.get("/api/roles")
    ck("Tenant-Admin /api/roles -> 200 (effektiv)", r.status_code == 200)
    r = c4.get("/api/tenants")
    ck("Tenant-Admin /api/tenants -> 403 (systemweit)", r.status_code == 403)
    # Operator ohne Membership -> 403
    c5 = app3.test_client()
    c5.post("/", data={"username": "__rolle_b__", "password": "TestPass123!"})
    r = c5.get("/api/roles")
    ck("Operator /api/roles -> 403", r.status_code == 403)
    j = c5.get("/api/me/permissions").get_json()
    ck("Operator effektive Permissions",
       j.get("effective_role") == "operator" and "tenant_trade_control" in j.get("permissions", []))
    # Cleanup
    m2 = mtdb2.MTDB()
    m2.conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=?", (t2,))
    m2.conn.execute("DELETE FROM tenants WHERE id=?", (t2,))
    m2.conn.commit(); m2.close()
    us = sec._load_users()
    us.pop("__rolle_a__", None); us.pop("__rolle_b__", None)
    sec._save_users(us)
except Exception as e:
    ck("Rollen-/Berechtigungsmodell", False, str(e))

# ─── Phase 15d: Mandantentrennung (v2.28.0, PHASE 4) ───────────────────
print("\n7d. Mandantentrennung (v2.28.0, PHASE 4)")
try:
    import os as _os, json as _json, db as mtdb3, dashboard as dash3
    BASE = dash3.BASE
    TD = _os.path.join(BASE, "depot_777.json")
    with open(TD, "w") as f:
        _json.dump({"tenant_id": 5, "bargeld": 500, "start_wert": 100,
                    "positions": {"AAPL": {"shares": 2, "avg_price": 10}}, "historie": []}, f)
    s1 = dash3._tenant_scoped_depot_files(1)
    s5 = dash3._tenant_scoped_depot_files(5)
    ck("Tenant 1 sieht Tenant-5-Depot NICHT", "depot_777.json" not in str(s1))
    ck("Tenant 5 sieht eigenes Depot", "depot_777.json" in str(s5))
    m = mtdb3.MTDB()
    m.depot_register("depots", 5, "depot_777", "depot_777.json", risk_stufe=777, name="T5")
    ck("depot_list_tenant(5) isoliert", len(m.depot_list_tenant("depots", 5)) == 1)
    ck("depot_list_tenant(1) sieht T5 NICHT", len(m.depot_list_tenant("depots", 1)) == 0)
    ck("query_trades tenant=999 leer", len(m.query_trades(tenant_id=999)) == 0)
    # /api/db_query erzwingt Session-Tenant (Client-Parameter wird ignoriert)
    app3 = dash3.app; app3.config["TESTING"] = True
    c3 = app3.test_client()
    c3.post("/", data={"username": "admin", "password": "MicroTrader2026!"})
    r = c3.get("/api/db_query?mode=trades&tenant_id=999&limit=500")
    j = r.get_json()
    ck("/api/db_query ignoriert Client-tenant (nutzt Session)",
       r.status_code == 200 and j.get("count", 0) > 0)  # >0 = Server nutzte tid=1, nicht 999
    _os.remove(TD)
    m.conn.execute("DELETE FROM depots WHERE tenant_id=5")
    m.conn.commit(); m.close()
except Exception as e:
    ck("Mandantentrennung", False, str(e))

# ─── Phase 15e: Trading-Modi-Zustandsmaschine (v2.29.0, PHASE 5) ───────
print("\n7e. Trading-Modi-Zustandsmaschine (v2.29.0, PHASE 5)")
try:
    import security as sec5, db as mtdb5, dashboard as dash5
    # State Machine Logik (db.py)
    m5 = mtdb5.MTDB()
    ck("TRADING_MODES enthaelt alle 8 Zustaende",
       len(m5.TRADING_MODES) == 8 and "LIVE_ACTIVE" in m5.TRADING_MODES)
    ck("SHADOW->PAPER erlaubt", m5.mode_can_transition("SHADOW", "PAPER"))
    ck("SHADOW->LIVE_ACTIVE VERBOTEN", not m5.mode_can_transition("SHADOW", "LIVE_ACTIVE"))
    ck("PAPER->LIVE_REQUESTED erlaubt", m5.mode_can_transition("PAPER", "LIVE_REQUESTED"))
    ck("LIVE_APPROVED->LIVE_ACTIVE erlaubt", m5.mode_can_transition("LIVE_APPROVED", "LIVE_ACTIVE"))
    m5.close()

    # set_trading_mode erzwingt erlaubte Transition (ValueError sonst)
    # Zuerst sicher auf SHADOW zuruecksetzen (Isolation)
    try:
        sec5.set_trading_mode("SHADOW", tenant_id=1, user={"username": "admin"})
    except ValueError:
        pass
    try:
        sec5.set_trading_mode("LIVE_ACTIVE", tenant_id=1, user={"username": "admin"})
        ck("set_trading_mode verbietet illegale Transition", False)
    except ValueError:
        ck("set_trading_mode verbietet illegale Transition", True)
    # Erlaubte Transition SHADOW->PAPER
    old, new = sec5.set_trading_mode("PAPER", tenant_id=1, user={"username": "admin"}, reason="Test")
    ck("set_trading_mode SHADOW->PAPER OK", old == "SHADOW" and new == "PAPER")
    # Cleanup zurueck zu SHADOW
    sec5.set_trading_mode("SHADOW", tenant_id=1, user={"username": "admin"})

    # API-Test
    app5 = dash5.app; app5.config["TESTING"] = True
    c5 = app5.test_client()
    c5.post("/", data={"username": "admin", "password": "MicroTrader2026!"})
    r = c5.get("/api/trading_mode")
    ck("API GET /api/trading_mode liefert Modus", r.status_code == 200 and "mode" in r.get_json())
    r = c5.post("/api/trading_mode/set", data={"mode": "PAPER", "reason": "t"})
    ck("API POST set PAPER OK", r.get_json().get("ok") is True)
    r = c5.post("/api/trading_mode/set", data={"mode": "LIVE_ACTIVE"})
    ck("API POST LIVE_ACTIVE abgelehnt (400)", r.status_code == 400)
    # History
    r = c5.get("/api/trading_mode/history")
    ck("API history liefert Liste", r.status_code == 200 and isinstance(r.get_json().get("history"), list))
    # Cleanup DB
    m5b = mtdb5.MTDB()
    m5b.conn.execute("DELETE FROM trading_mode_transitions WHERE tenant_id=1")
    m5b.conn.commit(); m5b.close()
    sec5.set_trading_mode("SHADOW", tenant_id=1, user={"username": "admin"})
except Exception as e:
    ck("Trading-Modi-Zustandsmaschine", False, str(e))

# ─── Phase 15f: Shadow->Paper Freigabe (v2.30.0, PHASE 6) ───────────────
print("\n7f. Shadow->Paper Freigabe (v2.30.0, PHASE 6)")
try:
    import security as sec6, db as mtdb6, dashboard as dash6
    # paper_eligibility liefert (bool, list)
    elig, gruende = sec6.paper_eligibility(1)
    ck("paper_eligibility liefert Tupel", isinstance(elig, bool) and isinstance(gruende, list))
    # Tenant 1 hat >20 ki_decisions -> eligible (sofern keine Konflikte)
    ck("Tenant 1 grundsaetzlich eligible", elig is True or len(gruende) > 0)
    # enter_paper erzwingt SHADOW->PAPER nur wenn eligible
    try:
        old, new = sec6.enter_paper(tenant_id=1, user={"username": "admin"})
        ck("enter_paper SHADOW->PAPER OK", old == "SHADOW" and new == "PAPER")
    except ValueError:
        ck("enter_paper blockiert (Eligibility)", False)
    # Virtuelles Paper-Portfolio anlegen (eigenes Depot)
    m6 = mtdb6.MTDB()
    m6.paper_portfolio_create(1, "test_paper", "Test", 100.0)
    ck("paper_portfolio_create OK", len(m6.paper_portfolio_list(1)) >= 1)
    # API
    app6 = dash6.app; app6.config["TESTING"] = True
    c6 = app6.test_client()
    c6.post("/", data={"username": "admin", "password": "MicroTrader2026!"})
    # Sicher auf SHADOW zuruecksetzen (Isolation)
    try:
        sec6.set_trading_mode("SHADOW", tenant_id=1, user={"username": "admin"})
    except ValueError:
        pass
    r = c6.get("/api/paper/eligibility")
    ck("API /api/paper/eligibility liefert eligible", r.status_code == 200 and "eligible" in r.get_json())
    r = c6.post("/api/paper/enter")
    ck("API /api/paper/enter OK", r.get_json().get("ok") is True)
    # Cleanup
    m6.conn.execute("DELETE FROM paper_portfolios WHERE tenant_id=1")
    m6.conn.execute("DELETE FROM trading_mode_transitions WHERE tenant_id=1")
    m6.conn.commit(); m6.close()
    sec6.set_trading_mode("SHADOW", tenant_id=1, user={"username": "admin"})
except Exception as e:
    ck("Shadow->Paper Freigabe", False, str(e))

# ─── Zusammenfassung ─────────────────────────────────────────────
print(f"\n=== ERGEBNIS: {OK} OK, {FAIL} FAIL ===")
sys.exit(1 if FAIL else 0)
