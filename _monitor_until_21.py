"""
Micro-Trader Monitoring bis 21:00 Uhr
Prueft alle 15 Min: Prozesse, Dashboard, Leerkonten, KI-Aktivitaet, ETF-Integritaet
"""
import os, glob, json, time, datetime, subprocess
from collections import Counter

base = "C:/Users/goldi/projects/micro-trader"
os.chdir(base)

def pz(z):
    if isinstance(z, str):
        try: return datetime.datetime.fromisoformat(z.replace("Z","+00:00"))
        except: return None
    return None

def is_empty(d):
    shares = d.get("shares", 0)
    pos = d.get("positions", {})
    has_pos = shares > 0 or (pos and any(p.get("shares",0)>0 for p in pos.values()))
    return d.get("bargeld", d.get("start",0)) > 1 and not has_pos and len(d.get("trades",[])) == 0

def audit():
    now = datetime.datetime.now()
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"MICRO-TRADER AUDIT — {now.strftime('%H:%M:%S')}")
    lines.append(f"{'='*60}")
    
    # Prozesse
    r = subprocess.run(["tasklist","/FI","IMAGENAME eq pythonw.exe","/FO","CSV"], capture_output=True, text=True)
    pids = [l.split(",")[1].strip('"') for l in r.stdout.splitlines() if "pythonw.exe" in l]
    lines.append(f"[1] Prozesse: {len(pids)} pythonw (PIDs: {', '.join(pids[:5])})")
    
    # Dashboard
    r = subprocess.run(["curl","-s","-m","5","-o","nul","-w","%{http_code}","http://127.0.0.1:5300/data"], capture_output=True, text=True)
    lines.append(f"[2] Dashboard :5300 → HTTP {r.stdout}")
    
    # Leerkonten
    for cat, pat in [("AKTIEN","depot_*.json"), ("ETF","etf_*.json"), ("SPEC","spec_depots/*.json")]:
        files = glob.glob(pat)
        empty = sum(1 for f in files if is_empty(json.load(open(f, encoding="utf-8"))))
        lines.append(f"[3] {cat}: {empty} leer von {len(files)}")
    
    # KI-Aktivitaet
    if os.path.exists("ki_log.json"):
        k = json.load(open("ki_log.json", encoding="utf-8"))
        if isinstance(k, list):
            now_ts = time.time()
            def parse(z):
                if isinstance(z,(int,float)): return float(z)
                if isinstance(z,str):
                    try: return datetime.datetime.fromisoformat(z.replace("Z","+00:00")).timestamp()
                    except: return 0
                return 0
            recent = [e for e in k if (now_ts - parse(e.get("zeit",0))) < 900]  # 15 min
            acts = Counter(e.get("aktion","?") for e in recent)
            lines.append(f"[4] KI (15min): {len(recent)} Entsch. | {dict(acts)}")
    
    # ETF-Integritaet
    etf = [f for f in glob.glob("etf_*.json") if "summary" not in f]
    tot_b, tot_s = 0, 0
    dead = 0
    for f in etf:
        d = json.load(open(f, encoding="utf-8"))
        tot_b += d.get("bargeld",0)
        tot_s += d.get("start", d.get("start_wert",100))
        if d.get("bargeld",0) < 50:  # <50$ = quasi tot
            dead += 1
    lines.append(f"[5] ETF: {dead} depots <50$ bargeld | Summe {tot_b:.0f}/{tot_s:.0f}$ ({tot_b/tot_s*100:.0f}%)")
    
    # Letzter Pipeline-Lauf
    if os.path.exists("cron_pipeline.log"):
        lines_log = open("cron_pipeline.log", encoding="utf-8", errors="ignore").read().splitlines()
        last = [l for l in lines_log if any(x in l for x in ["batch_trader","spec_trader","etf_trader","TIMEOUT","OK"])]
        for l in last[-3:]:
            lines.append(f"[6] {l[-75:]}")
    
    return "\n".join(lines)

if __name__ == "__main__":
    end_time = datetime.datetime.now().replace(hour=21, minute=0, second=0)
    print(f"Monitoring startet, Ende 21:00 ({int((end_time-datetime.datetime.now()).total_seconds()/60)} min)")
    while datetime.datetime.now() < end_time:
        print(audit())
        time.sleep(900)  # 15 min
    print("\n✅ Monitoring beendet (21:00 erreicht)")
