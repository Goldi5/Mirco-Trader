#!/usr/bin/env python3
"""Prio4 Patcher FIX: min_samples (alle Regeln) + OOS-Bestätigung."""
BASE = 'C:/Users/goldi/projects/micro-trader'

# ── 1) settings_loader.py ──
sp = f'{BASE}/settings_loader.py'
s = open(sp, encoding='utf-8').read()

old_limit = '"lernen.anti_min_n":       (1, 20, 3, 10, "n", "Anti-Regeln aus Einzel-Spikes → Überreaktion", "Anti-Regeln brauchen ewig → Fehler wiederholt"),'
new_limit = '"lernen.anti_min_n":       (1, 20, 3, 10, "n", "Anti-Regeln aus Einzel-Spikes → Überreaktion", "Anti-Regeln brauchen ewig → Fehler wiederholt"),\n    "lernen.min_samples":      (1, 50, 3, 15, "n", "Regeln aus zu wenig Daten → Rauschen/Überanpassung", "Regeln brauchen ewig → veraltet"),'
assert old_limit in s
s = s.replace(old_limit, new_limit)

old_lbl = '    "lernen.anti_min_n": ("Mindest-Anzahl für Gegen-Regeln",\n        "Aus wie vielen ähnlichen Fällen die KI erst eine \'Mach-das-nicht\'-Regel ableitet. Niedrig = überreagiert auf einen einzelnen Fehler. Hoch = braucht viele Beweise."),'
new_lbl = '    "lernen.anti_min_n": ("Mindest-Anzahl für Gegen-Regeln",\n        "Aus wie vielen ähnlichen Fällen die KI erst eine \'Mach-das-nicht\'-Regel ableitet. Niedrig = überreagiert auf einen einzelnen Fehler. Hoch = braucht viele Beweise."),\n    "lernen.min_samples": ("Mindest-Stichprobe pro Regel",\n        "Wie viele unabhängige Trades eine Regel mindestens haben muss, bevor sie als \'bestätigt\' gilt. Niedrig = Regel aus Rauschen (Overfitting). Hoch = sehr konservativ, aber langsam."),'
assert old_lbl in s
s = s.replace(old_lbl, new_lbl)

old_def = '            "lernen": {"decay_lambda": 0.01, "anti_min_n": 5, "anti_min_widerlegt_pct": 60,'
new_def = '            "lernen": {"decay_lambda": 0.01, "anti_min_n": 5, "anti_min_widerlegt_pct": 60, "min_samples": 5,'
assert old_def in s
s = s.replace(old_def, new_def)
open(sp, 'w', encoding='utf-8').write(s)
print('settings_loader.py OK')

# ── 2) learned_rules.py ──
lp = f'{BASE}/learned_rules.py'
l = open(lp, encoding='utf-8').read()
old_lc = '''def lebenszyklus_status(regel):
    """Status einer Regel (Prio 2): stabil | wackelig | veraltet.

    - veraltet:   effektiv_gewicht < 0.3 (Decay hat zugeschlagen)
                  ACHTUNG: Anti-Regeln haben NEGATIVES Gewicht → der
                  Betrag zählt: |effektiv_gewicht| < 0.3 = veraltet
    - wackelig:   violation_count > support_count (mehr Widerlegungen)
    - stabil:     sonst (Support ≥ Violations, Gewicht noch relevant)
    """
    ew = abs(float(regel.get("effektiv_gewicht", regel.get("gewicht", 0))))
    sup = regel.get("support_count", 0) or 0
    vio = regel.get("violation_count", 0) or 0
    if ew < 0.3:
        return "veraltet"
    if vio > sup:
        return "wackelig"
    return "stabil"'''
new_lc = '''def lebenszyklus_status(regel):
    """Status einer Regel (Prio 2 + Prio4): unbestätigt | stabil | wackelig | veraltet.

    - unbestätigt: zu wenig Samples (< min_samples) ODER keine OOS-Bestätigung
    - veraltet:    effektiv_gewicht < 0.3 (Anti: |ew| < 0.3)
    - wackelig:    violation_count > support_count
    - stabil:      sonst
    """
    from settings_loader import lernen as _lernen
    min_samples = int(_lernen("min_samples", 5))
    ew = abs(float(regel.get("effektiv_gewicht", regel.get("gewicht", 0))))
    sup = regel.get("support_count", 0) or 0
    vio = regel.get("violation_count", 0) or 0
    oos = bool(regel.get("oos_confirmed", False))
    if sup < min_samples or not oos:
        return "unbestätigt"
    if ew < 0.3:
        return "veraltet"
    if vio > sup:
        return "wackelig"
    return "stabil"'''
assert old_lc in l
l = l.replace(old_lc, new_lc)
open(lp, 'w', encoding='utf-8').write(l)
print('learned_rules.py OK')

# ── 3) skill_sync.py ──
ssp = f'{BASE}/skill_sync.py'
ss = open(ssp, encoding='utf-8').read()
old_aktiv = '''        st = lebenszyklus_status(r)
        return st in ("stabil", "wackelig", "aktiv", None)'''
new_aktiv = '''        st = lebenszyklus_status(r)
        # Prio4: unbestätigt (zu wenig Samples / keine OOS) NICHT exportieren
        return st in ("stabil", "wackelig", "aktiv", None)'''
assert old_aktiv in ss
ss = ss.replace(old_aktiv, new_aktiv)
open(ssp, 'w', encoding='utf-8').write(ss)
print('skill_sync.py OK')

# ── 4) ki_learning.py ──
kp = f'{BASE}/ki_learning.py'
k = open(kp, encoding='utf-8').read()
oos_helper = '''
def _oos_bestätigung(regel, ergebnisse):
    """Prio4: Regel gilt erst als bestätigt, wenn sie auf NACHFOLGENDEN,
    unabhängigen Trades (nach created_at) mit mindestens min_samples Stützen hält."""
    from settings_loader import lernen as _lernen
    min_samples = int(_lernen("min_samples", 5))
    created = regel.get("created_at", "")
    try:
        ct = datetime.fromisoformat(created) if created else datetime.min
    except Exception:
        ct = datetime.min
    nach = [e for e in ergebnisse
            if e.get("regel_id") == regel.get("id")
            and e.get("zeit")
            and datetime.fromisoformat(e["zeit"]) > ct]
    if len(nach) >= min_samples and any((e.get("lerneffekt", 0) or 0) > 0 for e in nach):
        return True
    return (regel.get("support_count", 0) or 0) >= 2 * min_samples

'''
assert 'def _oos_bestätigung' not in k
marker = 'def anti_muster_regeln(ergebnisse):'
assert marker in k
k = k.replace(marker, oos_helper + marker)

old_anti_min = '''    if not ergebnisse or len(ergebnisse) < MIN_N:
        return []'''
new_anti_min = '''    if not ergebnisse or len(ergebnisse) < MIN_N:
        return []
    global _OOS_ERGEBNISSE
    _OOS_ERGEBNISSE = ergebnisse'''
assert old_anti_min in k
k = k.replace(old_anti_min, new_anti_min)

old_build = '                    "created_at": datetime.now().isoformat(),'
new_build = '                    "created_at": datetime.now().isoformat(),\n                    "oos_confirmed": False,'
first = k.find(old_build)
assert first >= 0
k = k[:first] + new_build + k[first+len(old_build):]
open(kp, 'w', encoding='utf-8').write(k)
print('ki_learning.py OK')
print('ALL Prio4 patches applied')
