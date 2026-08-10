"""
Watchlist auf Top-20 reduzieren (Root-Cause: spec_trader.py erstellt fuer
jeden Watchlist-Ticker ein Spec-Depot -> 155 Depots = 15500 EUR gebunden).
Backup liegt bereits vor (spec_watch.json.bak-*).
"""
import os, json

MT = os.path.dirname(os.path.abspath(__file__))
WP = os.path.join(MT, "spec_watch.json")

watch = json.load(open(WP, encoding="utf-8"))
print("Watchlist vorher:", len(watch), "Ticker")

# Top-20 nach Wert (wie in cleanup_spec.py ermittelt)
TOP20 = ["BBAI","FNGU","QS","SOUN","NRGU","BB","IONQ","MRNA","PLTR","TNA",
         "CRSP","SCO","RKLB","JDST","FAZ","BOIL","BITX","TQQQ","RGTI","QQQ"]

reduced = {k: v for k, v in watch.items() if k in TOP20}
print("Watchlist nachher:", len(reduced), "Ticker")
print("Behalten:", ", ".join(sorted(reduced.keys())))

json.dump(reduced, open(WP, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("GESPEICHERT.")
