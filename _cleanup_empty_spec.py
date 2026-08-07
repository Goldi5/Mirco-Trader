import os, glob, json, shutil, time, sys

base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base)
os.chdir(base)

from spec_watch import WATCHLIST

ts = time.strftime("%Y%m%d_%H%M%S")
backup_dir = os.path.join(base, ".backup", f"spec_empty-{ts}")
os.makedirs(backup_dir, exist_ok=True)

# NEU (Plan B): statt Loeschen -> Reset auf Startkapital, damit Trader sie befuellen kann
# Nur Depots loeschen, die NICHT in WATCHLIST sind (wirklich tote/veraltete).
START_KAPITAL = 100.0
empty = []
for f in sorted(glob.glob("spec_depots/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    t = d.get("ticker", os.path.basename(f).replace(".json", ""))
    b = d.get("bargeld", 0)
    s = d.get("shares", 0)
    tr = d.get("trades", [])
    if b > 1 and s == 0 and len(tr) == 0:
        if t in WATCHLIST:
            # In WATCHLIST, aber leer -> RESET (nicht loeschen)
            d["bargeld"] = START_KAPITAL
            if not d.get("start"):
                d["start"] = START_KAPITAL
            json.dump(d, open(f, "w", encoding="utf-8"), indent=2)
            print(f"  ↻ {t}: Reset auf Startkapital (war leer)")
        else:
            # Nicht in WATCHLIST -> wirklich tot -> loeschen
            empty.append((f, t))

print(f"Zu loeschende tote Depots (nicht in WATCHLIST): {len(empty)}")
for f, t in empty:
    print(f"  {t}")

for f, t in empty:
    shutil.copy2(f, os.path.join(backup_dir, os.path.basename(f)))
    os.remove(f)
print(f"\n✅ {len(empty)} tote Spec-Depots geloescht (Backup: {backup_dir})")
print(f"Uebrig: {len(glob.glob('spec_depots/*.json'))} Spec-Depots")
