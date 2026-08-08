"""Neuer Admin-Bereich (StufenPilot-Design) — wird in dashboard.py eingefuegt.
Ersetzt die 5 alten admin_*-Routen (Zeilen ~1793-1962)."""
import os, glob, time

ADMIN_CSS = """
:root{--bg1:#f8fafc;--bg2:#f1f5f9;--card-bg:rgba(255,255,255,.8);--card-border:rgba(15,23,42,.07);
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
.top .right{margin-left:auto;display:flex;align-items:center;gap:10px}
.pill{background:var(--card-bg);backdrop-filter:blur(10px);border:1px solid var(--card-border);border-radius:999px;padding:6px 14px;font-size:12px;font-weight:600;box-shadow:var(--shadow)}
.pill.green{color:var(--green)}.pill.amber{color:var(--amber)}.pill.red{color:var(--red)}
a.pill{color:var(--accent);text-decoration:none}
.nav{display:flex;gap:4px;background:rgba(118,118,128,.10);padding:4px;border-radius:999px;margin-bottom:22px;overflow-x:auto;scrollbar-width:none}
.nav a{padding:7px 16px;border-radius:999px;font-size:12.5px;font-weight:600;color:var(--text-dim);text-decoration:none;white-space:nowrap;transition:all .18s}
.nav a:hover{color:var(--text)}
.nav a.active{background:#fff;color:var(--text);box-shadow:0 1px 4px rgba(0,0,0,.1)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-bottom:22px}
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
.btn.ghost{background:transparent;border:1px solid var(--card-border);color:var(--text);cursor:pointer}
.btn.ghost:hover{background:rgba(15,23,42,.05)}
.btn.danger{background:rgba(239,68,68,.12);color:var(--red)}
.msg{font-size:12px;margin-top:8px}
.hint{font-size:11px;color:var(--text-dim);margin-top:10px}
.search{width:100%;padding:10px 14px;border:1px solid var(--card-border);border-radius:10px;font-size:13px;font-family:inherit;background:#fff;color:var(--text);margin-bottom:12px}
.search:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(37,99,235,.12)}
"""

def _admin_layout(aktiver_tab, titel, inhalt, u):
    """Gemeinsames Admin-Layout (StufenPilot-Design)."""
    tabs = [
        ("overview", "/admin", "📊 Übersicht"),
        ("system", "/admin/system", "🩺 System"),
        ("users", "/admin/users", "👥 Benutzer"),
        ("audit", "/admin/audit", "📜 Audit"),
        ("backups", "/admin/backups", "💾 Backups"),
    ]
    nav = "".join(
        f"<a href='{href}' class='{'active' if key==aktiver_tab else ''}'>{label}</a>"
        for key, href, label in tabs)
    mfa = "🛡️" if u.get("mfa_secret") else "⚠️"
    return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin – Micro-Trader</title><style>{ADMIN_CSS}</style></head><body>
<div class='wrap'>
<div class='top'>
<img src='/assets/logo.png' alt='Logo'>
<div><h1>🔧 Admin-Bereich</h1><div class='sub'>Micro-Trader · Server-Sicherheit · Audit-Trail aktiv</div></div>
<div class='right'>
<span class='pill'>{u['username']} · {u['role']} {mfa}</span>
<a class='pill' href='/dashboard'>← Dashboard</a>
<a class='pill' href='/logout'>🚪 Logout</a>
</div>
</div>
<div class='nav'>{nav}</div>
{titel}
{inhalt}
</div></body></html>"""


def _admin_overview_route(u, sec, json):
    users = sec.list_users()
    aktive = sum(1 for x in users if x.get("active", True))
    mfa_on = sum(1 for x in users if x.get("mfa_secret"))
    sessions = sum(len(x.get("sessions", {}) or {}) for x in users)
    audit = sec.read_audit(200)
    audit_count = len(audit)
    login_fails = sum(1 for a in audit if a.get("event") == "login_failed")
    bdir = os.path.join(sec.BASE, ".backup")
    backups = len(glob.glob(os.path.join(bdir, "*"))) if os.path.isdir(bdir) else 0
    pause = {}
    pf = os.path.join(sec.BASE, "pause_flag.json")
    if os.path.exists(pf):
        try:
            import json as _j
            pause = _j.load(open(pf, encoding="utf-8"))
        except Exception:
            pause = {}
    paused = pause.get("paused") or pause.get("state") == "on"
    stats = f"""
<div class='cards'>
<div class='stat'><div class='num'>{len(users)}</div><div class='lbl'>Benutzer</div></div>
<div class='stat'><div class='num'>{aktive}</div><div class='lbl'>Aktiv</div></div>
<div class='stat'><div class='num'>{mfa_on}</div><div class='lbl'>MFA aktiv</div></div>
<div class='stat'><div class='num'>{sessions}</div><div class='lbl'>Sessions</div></div>
<div class='stat'><div class='num'>{audit_count}</div><div class='lbl'>Audit-Einträge</div></div>
<div class='stat'><div class='num'>{login_fails}</div><div class='lbl'>Login-Fehlversuche</div></div>
<div class='stat'><div class='num'>{backups}</div><div class='lbl'>Backups</div></div>
<div class='stat'><div class='num {'bad' if paused else 'ok'}'>{'⏸' if paused else '▶'}</div><div class='lbl'>Trading {'pausiert' if paused else 'aktiv'}</div></div>
</div>"""
    letzte = "".join(
        f"<tr><td class='b'>{a.get('event','')}</td><td>{a.get('actor','')}</td>"
        f"<td style='color:var(--text-dim)'>{a.get('detail','')}</td>"
        f"<td style='color:var(--text-dim);white-space:nowrap'>{str(a.get('ts',''))[:19]}</td></tr>"
        for a in audit[:8])
    return _admin_layout("overview",
        f"<h2 style='font-size:17px;margin-bottom:4px'>Übersicht</h2>"
        f"<div style='font-size:12px;color:var(--text-dim);margin-bottom:16px'>Angemeldet als <b>{u['username']}</b> · Rolle <b>{u['role']}</b> · Alle Admin-Aktionen werden audit-logged.</div>",
        f"""{stats}
<div class='glass'><h2>🕘 Letzte Audit-Einträge</h2>
<table><tr><th>Ereignis</th><th>Wer</th><th>Detail</th><th>Zeit</th></tr>{letzte or '<tr><td colspan=4 style="color:var(--text-dim)">Keine Einträge</td></tr>'}</table>
<div class='hint'><a href='/admin/audit' style='color:var(--accent)'>Alle Einträge →</a></div></div>
<div class='glass'><h2>🩺 Schnellzugriff</h2>
<a class='btn primary' href='/admin/users'>👥 Benutzerverwaltung</a>&nbsp;
<a class='btn ghost' href='/admin/system'>🩺 Systemstatus</a>&nbsp;
<a class='btn ghost' href='/admin/backups'>💾 Backups</a>&nbsp;
<a class='btn ghost' href='/dashboard'>📊 Zum Dashboard</a></div>""", u)
