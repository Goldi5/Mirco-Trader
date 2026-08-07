#!/usr/bin/env python3
"""Diagnostic 2: real batch prompt (20 depots) -> capture + parse test."""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from ki_provider import call_ki
import batch_trader as bt

# Baue echten Prompt via batch_trader Logik (ohne Ausführung)
RISK_STUFEN = getattr(bt, "RISK_STUFEN", list(range(0, 100, 5)))
args_list = []
for risk in RISK_STUFEN[:20]:
    depot = bt.laden_oder_erstellen(risk)
    params = bt.fuer_risk_stufe(risk)
    kandidaten = []
    args_list.append((risk, params, depot, kandidaten, 1))

# Rekonstruiere ki_call_alleeps prompt-Bau (vereinfacht)
depot_infos = []
for risk, params, depot, kandidaten, prio in args_list:
    dep = {"risk": risk, "bargeld": depot.bargeld, "positions": getattr(depot, "positions", {}), "start": depot.start_wert}
    pos_liste = []
    for t, pos in dep.get("positions", {}).items():
        if pos.get("shares", 0) > 0:
            pos_liste.append(f"{t} {pos['shares']}@{pos.get('avg_price',0):.1f}")
    depot_infos.append(f"Risk {risk}: Cash ${dep.get('bargeld',0):.1f}, Wert ${sum(p['shares']*p.get('avg_price',0) for p in dep['positions'].values()):.1f}, Pos: {', '.join(pos_liste) if pos_liste else 'keine'}")

prompt = f"Analysiere {len(args_list)} Aktien-Depots. Entscheide pro Depot: Welche Positionen KAUFEN/VERKAUFEN/HALTEN.\n\n"
prompt += "\n".join(depot_infos)
prompt += '\n\nAntworte NUR mit JSON [{"risk":0, "aktionen":[{"ticker":"AAPL","aktion":"kaufen"|"verkaufen"|"halten","menge":"voll"|"teil","grund":"..."}]}]'

raus, provider = call_ki([
    {"role": "system", "content": "Du antwortest NUR mit JSON. Kein Denken, keine Erklärung, nur das JSON-Array."},
    {"role": "user", "content": prompt}
], temperature=0.1, max_tokens=4096)

with open("_raw_ki_20.txt", "w", encoding="utf-8") as f:
    f.write(f"PROVIDER: {provider}\n\n{raus}")

# Parse-Test
try:
    start = raus.find("[")
    end = raus.rfind("]") + 1
    entscheidungen = json.loads(raus[start:end])
    print("PARSE OK:", len(entscheidungen), "Depots")
except Exception as e:
    print("PARSE FEHLER:", e)
    # Zeige Kontext um Fehlerstelle
    import re
    m = re.search(r"line (\d+) column (\d+)", str(e))
    if m:
        ln, col = int(m.group(1)), int(m.group(2))
        lines = raus.split("\n")
        if ln <= len(lines):
            print(f"Zeile {ln}: {lines[ln-1][:200]}")
            print(f"Spalte {col}: ...{lines[ln-1][max(0,col-30):col+10]}...")
