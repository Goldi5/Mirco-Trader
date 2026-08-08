"""Kompletter neuer Admin-Bereich fuer dashboard.py (ersetzt Zeilen ~1793-1962)."""

ADMIN_NEW = r'''
# ─── PHASE 8+ : Admin-Bereich (StufenPilot-Design, v2.24.0) ──────────────────
ADMIN_CSS = """
:root{--bg1:#f8fafc;--bg2:#f1f5f9;--card-bg:rgba(255,255,255,.82);--card-border:rgba(15,23,42,.07);
--accent:#2563eb;--accent-dark:#1d4ed8;--green:#10b981;--amber:#f59e0b;--red:#ef4444;
--text:#0f172a;--text-dim:#64748b;--radius:14px;--r-lg:18px;
--shadow:0 10px 28px rgba(15,23,42,.08);--shadow-lg:0 24px 48px rgba(61,93,153,.12)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI Variable','Segoe UI',system-ui,sans-serif;background:linear-gradient(160deg,var(--bg1),var(--bg2));
background-image:radial-gradient(ellipse at 15% 0%,rgba(37,99,235,.07) 0%,transparent 55%),radial-gradient(ellipse at 85% 0%,rgba(16,185,129,.05) 0%,transparent 50%);
min-height:100vh;color:var(--text);-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:24px 20px 60px}
.top{display:flex;align-items:center;gap:14px;margin-bottom:22px}
.top img{width:40px;height:40px;border-radius:10px}
.top h1{font-size:21px;font-weight:700}
.top .sub{font-size:11.5px;color:var(--text-dim)}
.top .right{margin-left:auto;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pill{background:var(--card-bg);backdrop-filter:blur(10px);border:1px solid var(--card-border);border-radius:999px;padding:6px 14px;font-size:12px;font-weight:600;box-shadow:var(--shadow)}
a.pill{color:var(--accent);text-decoration:none}
.nav{display:flex;gap:4px;background:rgba(118,118,128,.10);padding:4px;border-radius:999px;margin-bottom:22px;overflow-x:auto;scrollbar-width:none}
.nav a{padding:7px 16px;border-radius:999px;font-size:12.5px;font-weight:600;color:var(--text-dim);text-decoration:none;white-space:nowrap;transition:all .18s}
.nav a:hover{color:var(--text)}
.nav a.active{background:#fff;color:var(--text);box-shadow:0 1px 4px rgba(0,0,0,.1)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:22px}
.stat{background:var(--card-bg);backdrop-filter:blur(14px);border:1px solid var(--card-border);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}
.stat .num{font-size:22px;font-weight:700;margin-bottom:2px}
.stat .lbl{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.05em}
.glass{background:var(--card-bg);backdrop-filter:blur(14px);border:1px solid var(--card-border);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow);margin-bottom:14px}
.glass h2{font-size:14px;font-weight:700;margin-bottom:12px;color:var(--text)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;color:var(--text-dim);font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;padding:8px 10px;border-bottom:1px solid var(--card-border)}
td{padding:9px 10px;border-bottom:1px solid var(--card-border);vertical-align:top}
tr:last-child td{border-bottom:none}
code{background:rgba(15,23,42,.06);padding:2px 7px;border-radius:6px;font-size:11.5px}
.b{font-weight:600}
.ok{color:var(--green)}.bad{color:var(--red)}.warn{color:var(--amber)}
.btn{display:inline-block;padding:8px 16px;border-radius:10px;border:none;cursor:pointer;font-size:12.5px;font-weight:600;font-family:inherit;transition:all .15s;text-decoration:none}
.btn.primary{background:var(--accent);color:#fff}.btn.primary:hover{background:var(--accent-dark)}
.btn.ghost{background:transparent;border:1px solid var(--card-border);color:var(--text)}
.btn.ghost:hover{background:rgba(15,23,42,.05)}
.btn.danger{background:rgba(239,68,68,.12);color:var(--red)}
.hint{font-size:11px;color:var(--text-dim);margin-top:10px}
"""


def _admin_layout(aktiver_tab, u, titel, inhalt):
    """Gemeinsames Admin-Layout (StufenPilot-Design)."""
    tabs = [
        ("overview", "/admin", "📊 Übersicht"),
        ("system", "/admin/system", "🩺 System"),
        ("users", "/admin/users", "👥 Benutzer"),
        ("audit", "/admin/audit", "📜 Audit"),
        ("backups", "/admin/backups", "💾 Backups"),
    ]
    nav = "".join(
        f"<a href='{href}' class='{'active' if key == aktiver_tab else ''}'>{label}</a>"
        for key, href, label in tabs)
    mfa = "🛡️ MFA" if u.get("mfa_secret") else "⚠️ kein MFA"
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin – Micro-Trader</title><style>{ADMIN_CSS}</style></head><body>
<div class='wrap'>
<div class='top'>
<img src='/assets/logo.png' alt='Logo'>
<div><h1>🔧 Admin-Bereich</h1><div class='sub'>Micro-Trader · Server-Sicherheit · Audit-Trail aktiv</div></div>
<div class='right'>
<span class='pill'>{u['username']} · {u['role']} · {mfa}</span>
<a class='pill' href='/dashboard'>📊 Dashboard</a>
<a class='pill' href='/logout'>🚪 Logout</a>
</div>
</div>
<div class='nav'>{nav}</div>
{titel}
{inhalt}
</div></body></html>"""


@app.route("/admin")
@sec.require_role("admin")
def admin_overview():
    """Admin-Übersicht: Stat-Cards + letzte Audit-Einträge."""
    u = sec.current_user()
    users = sec.list_users()
    aktive = sum(1 for x in users if x.get("active", True))
    mfa_on = sum(1 for x in users if x.get("mfa_secret"))
    sessions = sum(len(x.get("sessions", {}) or {}) for x in users)
    audit = sec.read_audit(200)
    login_fails = sum(1 for a in audit if a.get("event") == "login_failed")
    bdir = os.path.join(BASE, ".backup")
    backups = len(glob.glob(os.path.join(bdir, "*"))) if os.path.isdir(bdir) else 0
    pause = {}
    pf = os.path.join(BASE, "pause_flag.json")
    if os.path.exists(pf):
        try:
            pause = json.load(open(pf, encoding="utf-8"))
        except Exception:
            pause = {}
    paused = pause.get("paused") or pause.get("state") == "on"
    stats = f"""
<div class='cards'>
<div class='stat'><div class='num'>{len(users)}</div><div class='lbl'>Benutzer</div></div>
<div class='stat'><div class='num'>{aktive}</div><div class='lbl'>Aktiv</div></div>
<div class='stat'><div class='num'>{mfa_on}</div><div class='lbl'>MFA aktiv</div></div>
<div class='stat'><div class='num'>{sessions}</div><div class='lbl'>Sessions</div></div>
<div class='stat'><div class='num'>{len(audit)}</div><div class='lbl'>Audit</div></div>
<div class='stat'><div class='num bad'>{login_fails}</div><div class='lbl'>Login-Fails</div></div>
<div class='stat'><div class='num'>{backups}</div><div class='lbl'>Backups</div></div>
<div class='stat'><div class='num {'bad' if paused else 'ok'}'>{'⏸' if paused else '▶'}</div><div class='lbl'>Trading {'pausiert' if paused else 'aktiv'}</div></div>
</div>"""
    letzte = "".join(
        f"<tr><td class='b'>{a.get('event','')}</td><td>{a.get('actor','')}</td>"
        f"<td style='color:var(--text-dim)'>{a.get('detail','')}</td>"
        f"<td style='color:var(--text-dim);white-space:nowrap'>{str(a.get('ts',''))[:19]}</td></tr>"
        for a in audit[:8])
    inhalt = f"""{stats}
<div class='glass'><h2>🕘 Letzte Audit-Einträge</h2>
<table><tr><th>Ereignis</th><th>Wer</th><th>Detail</th><th>Zeit</th></tr>{letzte or '<tr><td colspan=4 style="color:var(--text-dim)">Keine Einträge</td></tr>'}</table>
<div class='hint'><a href='/admin/audit' style='color:var(--accent)'>Alle Einträge →</a></div></div>
<div class='glass'><h2>🩺 Schnellzugriff</h2>
<a class='btn primary' href='/admin/users'>👥 Benutzerverwaltung</a>&nbsp;
<a class='btn ghost' href='/admin/system'>🩺 Systemstatus</a>&nbsp;
<a class='btn ghost' href='/admin/backups'>💾 Backups</a>&nbsp;
<a class='btn ghost' href='/dashboard'>📊 Zum Dashboard</a></div>"""
    return _admin_layout("overview", u,
        f"<h2 style='font-size:17px;margin-bottom:4px'>Übersicht</h2>"
        f"<div style='font-size:12px;color:var(--text-dim);margin-bottom:16px'>Angemeldet als <b>{u['username']}</b> · Rolle <b>{u['role']}</b></div>",
        inhalt)


@app.route("/admin/system")
@sec.require_role("admin")
def admin_system():
    """Systemstatus (Phase 8 Bereich 1) – erweitert."""
    u = sec.current_user()
    pause = {}
    pf = os.path.join(BASE, "pause_flag.json")
    if os.path.exists(pf):
        try:
            pause = json.load(open(pf, encoding="utf-8"))
        except Exception:
            pause = {}
    paused = pause.get("paused") or pause.get("state") == "on"
    grund = pause.get("grund", "manuell")
    # Dashboard-Prozess-Check
    port_offen = False
    try:
        import socket
        s = socket.socket(); s.settimeout(1)
        port_offen = s.connect_ex(("127.0.0.1", PORT)) == 0
        s.close()
    except Exception:
        port_offen = False
    status_rows = [
        ("Dashboard (Port %d)" % PORT, port_offen),
        ("Paper-/Shadow-Modus", True),
        ("Echtgeld-Funktionen", False),
        ("Trading-Pause", paused),
    ]
    rows = "".join(
        f"<tr><td class='b'>{name}</td><td class='{'ok' if val else 'bad'}'>{'✅ aktiv' if val else '❌ inaktiv'}</td></tr>"
        for name, val in status_rows)
    inhalt = f"""
<div class='cards'>
<div class='stat'><div class='num {'ok' if port_offen else 'bad'}'>{'🟢' if port_offen else '🔴'}</div><div class='lbl'>Dashboard</div></div>
<div class='stat'><div class='num ok'>✅</div><div class='lbl'>Shadow-Modus</div></div>
<div class='stat'><div class='num {'bad' if paused else 'ok'}'>{'⏸' if paused else '▶'}</div><div class='lbl'>Trading</div></div>
<div class='stat'><div class='num'>{'Mo–Fr 15–22 MEZ'}</div><div class='lbl'>Cron-Zeitfenster</div></div>
</div>
<div class='glass'><h2>🩺 Systemstatus</h2><table><tr><th>Komponente</th><th>Status</th></tr>{rows}</table></div>
<div class='glass'><h2>⏸ Trading-Pause</h2>
<p style='font-size:13px;margin-bottom:12px'>Status: <b class='{'bad' if paused else 'ok'}'>{'PAUSIERT (' + grund + ')' if paused else 'aktiv'}</b></p>
<a class='btn primary' href='/api/pause_trading?state={'off' if paused else 'on'}&grund=admin_ui'>▶ {'Trading wieder aktivieren' if paused else 'Trading pausieren'}</a>
<div class='hint'>Pause-Flag: <code>pause_flag.json</code> · Wird vom Cron-Pipeline respektiert.</div></div>"""
    return _admin_layout("system", u,
        f"<h2 style='font-size:17px;margin-bottom:4px'>Systemstatus</h2>"
        f"<div style='font-size:12px;color:var(--text-dim);margin-bottom:16px'>Server-Sicherheit Phasen 2–9 · Netzwerk-Grenze: 127.0.0.1</div>",
        inhalt)


@app.route("/admin/users")
@sec.require_role("admin")
def admin_users():
    """Benutzerverwaltung (StufenPilot-Design)."""
    u = sec.current_user()
    rows = ""
    for usr in sec.list_users():
        name = usr.get("username", "?")
        role = usr.get("role", "user")
        aktiv = usr.get("active", True)
        mfa = bool(usr.get("mfa_secret"))
        sess = len(usr.get("sessions", {}) or {})
        last = str(usr.get("last_login", "") or "")[:19] or "–"
        rows += f"""<tr>
<td class='b'>{name}{' <span class="warn">(du)</span>' if name == u['username'] else ''}</td>
<td><code>{role}</code></td>
<td class='{'ok' if aktiv else 'bad'}'>{'✅ aktiv' if aktiv else '⛔ inaktiv'}</td>
<td>{'🛡️' if mfa else '–'}</td>
<td>{sess}</td>
<td style='color:var(--text-dim)'>{last}</td>
</tr>"""
    inhalt = f"""<div class='glass'><h2>👥 Benutzerverwaltung</h2>
<div style='margin-bottom:10px;font-size:12.5px;color:var(--text-dim)'>Benutzer anlegen, Rollen und Status ändern → im Dashboard unter <b>Einstellungen → Benutzer</b> (voll interaktiv).</div>
<table><tr><th>Benutzer</th><th>Rolle</th><th>Status</th><th>MFA</th><th>Sessions</th><th>Letzter Login</th></tr>{rows or '<tr><td colspan=6 style="color:var(--text-dim)">Keine Benutzer</td></tr>'}</table>
<div class='hint'>Passwörter/MFA-Secrets werden niemals angezeigt. Admin-Aktionen → <a href='/admin/audit' style='color:var(--accent)'>Audit</a>.</div></div>"""
    return _admin_layout("users", u,
        f"<h2 style='font-size:17px;margin-bottom:4px'>Benutzer</h2>"
        f"<div style='font-size:12px;color:var(--text-dim);margin-bottom:16px'>{len(sec.list_users())} Benutzer · volle Verwaltung im Dashboard</div>",
        inhalt)


@app.route("/admin/audit")
@sec.require_role("admin")
def admin_audit():
    """Audit-Log (StufenPilot-Design) mit Suche."""
    u = sec.current_user()
    q = request.args.get("q", "").strip().lower()
    entries = sec.read_audit(300)
    if q:
        entries = [a for a in entries if q in str(a.get("event", "")).lower()
                   or q in str(a.get("actor", "")).lower()
                   or q in str(a.get("detail", "")).lower()]
    rows = "".join(
        f"<tr><td class='b'>{a.get('event','')}</td><td>{a.get('actor','')}</td>"
        f"<td style='color:var(--text-dim)'>{a.get('detail','')}</td>"
        f"<td style='color:var(--text-dim);white-space:nowrap'>{str(a.get('ts',''))[:19]}</td></tr>"
        for a in entries)
    inhalt = f"""<div class='glass'><h2>📜 Audit-Log ({len(entries)} Einträge)</h2>
<form method='get' action='/admin/audit' style='margin-bottom:4px'>
<input class='search' name='q' placeholder='🔍 Suchen (Ereignis, Benutzer, Detail)…' value='{request.args.get("q","")}'>
</form>
<div style='overflow-x:auto'><table><tr><th>Ereignis</th><th>Wer</th><th>Detail</th><th>Zeit</th></tr>{rows or '<tr><td colspan=4 style="color:var(--text-dim)">Keine Einträge gefunden</td></tr>'}</table></div>
<div class='hint'>Append-only · nicht nachträglich änderbar. Letzte {len(entries)} Einträge (gefiltert: {'ja' if q else 'nein'}).</div></div>"""
    return _admin_layout("audit", u,
        f"<h2 style='font-size:17px;margin-bottom:4px'>Audit</h2>"
        f"<div style='font-size:12px;color:var(--text-dim);margin-bottom:16px'>Sicherheitsrelevante Aktionen, append-only</div>",
        inhalt)


@app.route("/admin/backups")
@sec.require_role("admin")
def admin_backups():
    """Backups (StufenPilot-Design) mit Details."""
    u = sec.current_user()
    bdir = os.path.join(BASE, ".backup")
    items = sorted(glob.glob(os.path.join(bdir, "*")), reverse=True)[:15] if os.path.isdir(bdir) else []
    rows = "".join(
        f"<tr><td class='b'>{os.path.basename(i)}</td><td>{os.path.getsize(i)//1024} KB</td>"
        f"<td style='color:var(--text-dim)'>{time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(i)))}</td></tr>"
        for i in items)
    inhalt = f"""<div class='glass'><h2>💾 Backups (zuletzt {len(items)})</h2>
<table><tr><th>Name</th><th>Größe</th><th>Erstellt</th></tr>{rows or '<tr><td colspan=3 style="color:var(--text-dim)">Keine Backups</td></tr>'}</table>
<div class='hint'>Backup-Ordner: <code>.backup/</code> · wird via <code>backup.py</code> erzeugt (Regel Nr. 1).</div></div>"""
    return _admin_layout("backups", u,
        f"<h2 style='font-size:17px;margin-bottom:4px'>Backups</h2>"
        f"<div style='font-size:12px;color:var(--text-dim);margin-bottom:16px'>Snapshot-Sicherungen vor Änderungen</div>",
        inhalt)


'''
