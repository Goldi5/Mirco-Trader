p = 'skill_sync.py'
s = open(p, encoding='utf-8').read()

# Block 3: Skill-Sync exportiert nur freigegebene (live) Regeln, keine Shadow
old = '''def _ist_aktiv(r):
    """Nur aktive, nicht veraltete Regeln exportieren."""'''
new = '''def _ist_aktiv(r):
    """Nur aktive, nicht veraltete Regeln exportieren.

    Block 3: Shadow-Regeln (freigabe_status != 'freigegeben') werden
    NICHT in den Skill exportiert — nur live-freigegebene Regeln.
    """'''
assert old in s, '_ist_aktiv nicht gefunden'
s = s.replace(old, new)

old2 = '    aktiv = [r for r in regeln if _ist_aktiv(r)]'
new2 = '    # Block 3: zusätzlich Shadow/ nicht-freigegebene rausfiltern
    aktiv = [r for r in regeln if _ist_aktiv(r)
             and not r.get("shadow")
             and r.get("freigabe_status", "freigegeben") == "freigegeben"]'
assert old2 in s, 'regeln_nach_gewicht filter nicht gefunden'
s = s.replace(old2, new2)

open(p, 'w', encoding='utf-8').write(s)
print('skill_sync.py: Block 3 (nur freigegebene Regeln exportieren)')
