"""
Spec-Bereinigung: Behalte die 20 besten Spec-Depots (nach aktuellem Wert),
loesche den Rest. Regel Nr.1: Backup vor jeder Aenderung.
"""
import os, json, glob, shutil, datetime

MT = os.path.dirname(os.path.abspath(__file__))
SPEC_DIR = os.path.join(MT, "spec_depots")
KEEP = 20

# ── 1) BACKUP (Regel Nr.1) ──
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = os.path.join(MT, f"spec_depots_backup_{ts}")
shutil.copytree(SPEC_DIR, backup_dir)
print(f"BACKUP angelegt: {backup_dir} ({len(glob.glob(os.path.join(SPEC_DIR,'*.json')))} Dateien)")

# ── 2) Live-Daten vom laufenden Dashboard holen (korrekte Werte) ──
import sys
sys.path.insert(0, MT)
import dashboard as dash
app = dash.app; app.config["TESTING"] = True
c = app.test_client()
c.post("/", data={"username": "goldi5", "password": "Goldi2026!"})
d = c.get("/data").get_json()
spec = d.get("spec_depots") or []

# Nach Wert sortieren (beste zuerst)
ranked = sorted(spec, key=lambda x: x.get("wert", 0), reverse=True)
keep_tickers = [x.get("ticker") for x in ranked[:KEEP]]
drop_tickers = [x.get("ticker") for x in ranked[KEEP:]]

print(f"\nBehalte {KEEP} (Top nach Wert):")
for t in keep_tickers:
    e = next(x for x in spec if x.get("ticker") == t)
    print(f"  {t:7} | wert {round(e.get('wert',0),2):8}")

# ── 3) Dateien loeschen ──
deleted = 0
for ticker in drop_tickers:
    f = os.path.join(SPEC_DIR, f"{ticker}.json")
    if os.path.exists(f):
        os.remove(f)
        deleted += 1

print(f"\nGeloescht: {deleted} Spec-Depots")
print(f"Verbleibend: {len(glob.glob(os.path.join(SPEC_DIR,'*.json')))}")

# ── 4) Verifizierung ──
c2 = app.test_client()
c2.post("/", data={"username": "goldi5", "password": "Goldi2026!"})
d2 = c2.get("/data").get_json()
new_spec = d2.get("spec_depots") or []
new_wert = sum((x.get("wert", 0) or 0) for x in new_spec)
print(f"\nVERIFIKATION: {len(new_spec)} Spec-Depots | Gesamtwert {round(new_wert,2)} EUR")
print(f"Alle Top-20 erhalten:", all(t in [x.get('ticker') for x in new_spec] for t in keep_tickers))
