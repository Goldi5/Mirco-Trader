#!/usr/bin/env python3
"""Diagnostic: capture raw KI response from fallback chain for batch-style prompt."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from ki_provider import call_ki

# Mini-Batch-Prompt (3 Depots) wie im batch_trader
prompt = (
    'Analysiere 3 Aktien-Depots. Entscheide pro Depot: Welche Positionen KAUFEN/VERKAUFEN/HALTEN.\n\n'
    'Risk 10: Cash $100.0, Wert $100.5, Pos: AAPL 1 @ $100.0, Kandidaten: MSFT $410.0\n'
    'Risk 20: Cash $50.0, Wert $98.5, Pos: TSLA 1 @ $95.0, Kandidaten: NVDA $120.0\n'
    'Risk 30: Cash $80.0, Wert $102.0, Pos: keine, Kandidaten: AMZN $180.0\n\n'
    'Antworte NUR mit JSON [{"risk":0, "aktionen":[{"ticker":"AAPL","aktion":"kaufen"|"verkaufen"|"halten","menge":"voll"|"teil","grund":"..."}]}]'
)
raus, provider = call_ki([
    {"role": "system", "content": "Du antwortest NUR mit JSON. Kein Denken, keine Erklärung, nur das JSON-Array."},
    {"role": "user", "content": prompt}
], temperature=0.1, max_tokens=4096)

with open("_raw_ki_response.txt", "w", encoding="utf-8") as f:
    f.write(f"PROVIDER: {provider}\n\n{raus}")

print("Provider:", provider)
print("Länge:", len(raus) if raus else 0)
print("Erste 200 Zeichen:", repr(raus[:200]) if raus else "LEER")
