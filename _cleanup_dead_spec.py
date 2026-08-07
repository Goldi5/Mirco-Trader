import os, glob, json, shutil, time, sys

base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base)
os.chdir(base)

from spec_watch import WATCHLIST

ts = time.strftime("%Y%m%d_%H%M%S")
backup_dir = os.path.join(base, ".backup", f"spec_depots-dead-{ts}")
os.makedirs(backup_dir, exist_ok=True)

dead = []
valid = []
for f in sorted(glob.glob("spec_depots/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    t = d.get("ticker", os.path.basename(f).replace(".json", ""))
    start = d.get("start", d.get("start_wert", 0))
    b = d.get("bargeld", 0)
    s = d.get("shares", 0)
    tr = d.get("trades", [])
    if t in WATCHLIST and (start > 0 or b > 0 or s > 0 or tr):
        valid.append(f)
    else:
        dead.append(f)

print(f"Valid: {len(valid)}, Dead: {len(dead)}")
print("Dead Ticker:", [os.path.basename(f).replace('.json', '') for f in dead])

for f in dead:
    shutil.copy2(f, os.path.join(backup_dir, os.path.basename(f)))
    os.remove(f)
print(f"\n✅ {len(dead)} tote Spec-Depots geloescht (Backup: {backup_dir})")
print(f"✅ {len(valid)} gueltige Spec-Depots uebrig")
