#!/usr/bin/env python3
"""Build risk_profile.py from JSON tiers + ticker_sectors."""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")

with open(os.path.join(STATIC, "cleaned_tiers.json")) as f:
    TIERS = {int(k): v for k, v in json.load(f).items()}

# Build reverse map
T2T = {}
for tier, tickers in TIERS.items():
    for t in tickers:
        T2T[t] = tier

# Build TICKER_TO_TIER dict literal  
t2t_lines = []
for t in sorted(T2T):
    t2t_lines.append(f'    "{t}": {T2T[t]}')

# Sectors for fallback name generation
sectors = {}
sec_path = os.path.join(STATIC, "ticker_sectors.json")
if os.path.exists(sec_path):
    with open(sec_path) as f:
        sectors = json.load(f)

# Build content
lines = []
lines.append('#!/usr/bin/env python3')
lines.append('"""Risikoprofil – definiert 5 Tiers und Risk→Parameter Mapping."""')
lines.append('import math')
lines.append('')
lines.append('# ─── 5 Aktien-Tiers ──────────────────────────────────────────')
lines.append('# Tier 0 = defensiv (Blue Chips, Utilities, REITs, Healthcare)')
lines.append('# Tier 1 = balanced (Large-Cap Tech, Finance, Industrie)')
lines.append('# Tier 2 = growth (Mid-Cap, Biotech, Cloud, Consumer Disc.)')
lines.append('# Tier 3 = speculative (Meme, Crypto, EV, Space, China)')
lines.append('# Tier 4 = ETFs/heavily leveraged (3x Bull/Bear, Volatility, Crypto)')
lines.append('')
lines.append(f'TIERS = {{')
for t in range(5):
    tlist = TIERS.get(t, [])
    # Split long lines
    items_per_line = 12
    chunks = []
    for i in range(0, len(tlist), items_per_line):
        chunk = ', '.join(f'"{t}"' for t in tlist[i:i+items_per_line])
        chunks.append(chunk)
    inner = ',\n        '.join(chunks)
    lines.append(f'    {t}: [\n        {inner}\n    ],')
lines.append('}')

lines.append('')
lines.append('# ─── Ticker → Tier ───────────────────────────────────────────')
lines.append('TICKER_TO_TIER = {')
for t in sorted(T2T):
    lines.append(f'    "{t}": {T2T[t]},')
lines.append('}')

lines.append('')
lines.append('# ─── Ticker → Name (für Dashboard-Fallback) ───────────────────')
lines.append('TICKER_NAMES = {')
for t in sorted(T2T):
    sec = sectors.get(t, '')
    if sec:
        lines.append(f'    "{t}": "{t} [{sec}]",')
    else:
        tier_names = {0: 'Defensiv', 1: 'Large-Cap', 2: 'Growth', 3: 'Spekulativ', 4: 'ETF/Hebel'}
        tn = tier_names.get(T2T[t], '')
        lines.append(f'    "{t}": "{t} – {tn}",')
lines.append('}')

lines.append('')
lines.append('# ─── Risk-Stufen ──────────────────────────────────────────────')
lines.append('RISK_STUFEN = list(range(0, 100, 5))  # 0,5,10,…,95')
lines.append('')

# get_allowed_tiers function
lines.append('def get_allowed_tiers(risk: int) -> list:')
lines.append('    """Welche Tiers für diese Risk-Stufe erlaubt sind."""')
lines.append('    if risk <= 10:')
lines.append('        return [0]')
lines.append('    elif risk <= 30:')
lines.append('        return [0, 1]')
lines.append('    elif risk <= 50:')
lines.append('        return [0, 1, 2]')
lines.append('    elif risk <= 70:')
lines.append('        return [0, 1, 2, 3]')
lines.append('    else:')
lines.append('        return [1, 2, 3, 4]')
lines.append('')

# get_params function
lines.append('def get_params(risk: int) -> dict:')
lines.append('    """Risk→Parameter: Positionen, Größe, Stop-Loss, Take-Profit, Score-Grenzen."""')
lines.append('    # Dynamisch: defensiv → viele kleine Positionen, spekulativ → wenige große')
lines.append('    max_pos = max(2, min(6, 6 - (risk // 25)))  # 6 bei Risk 0 → 2 bei Risk 95')
lines.append('    pos_size = 0.30 + (risk / 100) * 0.30  # 0.30 bei Risk 0 → 0.60 bei Risk 95')
lines.append('    min_score = max(25, 50 - (risk // 3))  # 50 bei Risk 0 → 25 bei Risk 95')
lines.append('')
lines.append('    return {')
lines.append('        "max_positions": max_pos,')
lines.append('        "position_size": round(pos_size, 3),')
lines.append('        "stop_loss": max(0.85, 0.97 - (risk * 0.001)),  # 0.97→0.87')
lines.append('        "take_profit": min(1.30, 1.10 + (risk * 0.002)),  # 1.10→1.30')
lines.append('        "min_score": min_score,')
lines.append('    }')
lines.append('')
lines.append('')
lines.append('# ─── Alias für Abwärtskompatibilität ───────────────────────────')
lines.append('fuer_risk_stufe = get_params')
lines.append('')

lines.append('if __name__ == "__main__":')
lines.append('    print("Risk Profile – Validierung")')
lines.append('    for t in range(5):')
lines.append('        print(f"  Tier {t}: {len(TIERS[t])} tickers")')
lines.append('    print(f"  Total: {sum(len(v) for v in TIERS.values())} tickers")')
lines.append('    print(f"  Ticker→Tier: {len(TICKER_TO_TIER)} mappings")')
lines.append('    print(f"  Names: {len(TICKER_NAMES)} entries")')
lines.append('    print()')
lines.append('    for risk in [0, 10, 25, 50, 75, 95]:')
lines.append('        p = get_params(risk)')
lines.append('        a = get_allowed_tiers(risk)')
lines.append('        print(f"  Risk {risk:3d}: allowed={a}  max_pos={p[\'max_positions\']}  size={p[\'position_size\']}  sl={p[\'stop_loss\']}  tp={p[\'take_profit\']}  min_score={p[\'min_score\']}")')

with open(os.path.join(BASE, "risk_profile.py"), "w", encoding="utf-8") as f:
    f.write('\n'.join(lines))

print(f"Written risk_profile.py ({len(lines)} lines)")
