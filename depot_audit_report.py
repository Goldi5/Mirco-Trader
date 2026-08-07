#!/usr/bin/env python3
"""
Depot-Audit-Report — taeglicher Snapshot aller Aktien/ETF/Spec-Depots.
Optik kompatibel mit report_pdf.py (Arial, A4, Farb-Tables).
KEIN KI-Call. Reine Datei-Analyse + ki_log.json Auswertung.
Erzeugt:
  - Markdown: Archiv/Depot-Audit/depot-audit_YYYY-MM-DD.md
  - PDF:       Archiv/Depot-Audit/depot-audit_YYYY-MM-DD.pdf
"""
import os, json, datetime, glob

BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = r"C:\Users\goldi\OneDrive\Server und Projekt Ordner\Obsidian\Hermes Gedächtniss"
ARCHIV = os.path.join(VAULT, "Archiv", "Depot-Audit")
os.makedirs(ARCHIV, exist_ok=True)

now = datetime.datetime.now()
DATUM = now.strftime("%Y-%m-%d")
ZEIT = now.strftime("%H:%M")

# ─── Daten sammeln ───────────────────────────────────────────────
def lade(risk, prefix="depot"):
    p = os.path.join(BASE, f"{prefix}_{risk:03d}.json")
    if os.path.exists(p):
        try: return json.load(open(p, encoding="utf-8"))
        except: return None
    return None

ki_log = []
if os.path.exists(os.path.join(BASE, "ki_log.json")):
    try: ki_log = json.load(open(os.path.join(BASE, "ki_log.json"), encoding="utf-8"))
    except: pass

letzte_ki = {}
for e in ki_log:
    if e.get("typ") == "decision":
        t = e.get("ticker"); z = e.get("zeit", "")
        if t not in letzte_ki or z > letzte_ki[t][0]:
            letzte_ki[t] = (z, e.get("aktion"), e.get("grund", ""), e.get("konfidenz"))

def grund_fuer(risk, prefix, ticker=None):
    dep_typ = f"spec_{risk}" if prefix == "spec" else ("etf" if prefix == "etf" else "aktien")
    hg = []
    for e in ki_log:
        if e.get("typ") == "decision" and e.get("aktion") == "halten":
            if ticker and e.get("ticker") == ticker:
                return e.get("grund", "")[:90]
            dt = e.get("depot_typ"); did = str(e.get("decision_id", ""))
            if (dt == dep_typ) or (f"_{risk}_" in did) or (f"_{risk}na" in did):
                hg.append(f"{e.get('ticker')}: {e.get('grund','')[:60]}")
    return " | ".join(hg[:3]) if hg else ""

def audit_aktien_etf(prefix, label):
    zeilen = []
    for r in range(0, 100, 5):
        d = lade(r, prefix)
        if not d: continue
        cash = d.get("bargeld", 0) or 0
        pos = d.get("positions", {}) or {}
        offen = {t: p for t, p in pos.items() if isinstance(p, dict) and p.get("shares", 0) > 0}
        trades = d.get("trades", []) or []
        mst = None
        if trades:
            try: mst = (now - datetime.datetime.fromisoformat(trades[-1].get("zeit", ""))).total_seconds() / 60
            except: pass
        n = len(offen)
        if cash > 1 and n == 0:
            g = grund_fuer(r, prefix) or "KI haelt (siehe ki_log)"
            status = "CASH OHNE POS"
        elif n == 0 and cash <= 1:
            g = "KEIN CASH, KEINE POS"; status = "LEER"
        elif n > 0:
            g = ", ".join(offen.keys()); status = "POS"
        else:
            g = "?"; status = "?"
        mst_s = f"{mst:.0f}m" if mst is not None else "nie"
        zeilen.append((r, status, round(cash, 2), n, mst_s, g[:50]))
    return zeilen

def audit_spec():
    zeilen = []
    sdd = os.path.join(BASE, "spec_depots")
    if not os.path.isdir(sdd): return zeilen
    for fn in sorted(os.listdir(sdd)):
        if not fn.endswith(".json"): continue
        try: d = json.load(open(os.path.join(sdd, fn), encoding="utf-8"))
        except: continue
        t = d.get("ticker", fn.replace(".json", ""))
        cash = d.get("bargeld", 0) or 0
        shares = d.get("shares", 0) or 0
        trades = d.get("trades", []) or []
        mst = None
        if trades:
            try: mst = (now - datetime.datetime.fromisoformat(trades[-1].get("zeit", ""))).total_seconds() / 60
            except: pass
        if shares > 0:
            status = "POS"; g = f"{shares:.2f} Shares"
        elif cash > 1:
            status = "CASH OHNE POS"
            g = grund_fuer(0, "spec", ticker=t) or "KI haelt (siehe ki_log)"
        else:
            status = "LEER"; g = "kein Cash, keine Pos"
        mst_s = f"{mst:.0f}m" if mst is not None else "nie"
        zeilen.append((t, status, round(cash, 2), shares, mst_s, g[:50]))
    return zeilen

aktien = audit_aktien_etf("depot", "AKTIEN")
etf = audit_aktien_etf("etf", "ETF")
spec = audit_spec()

# ─── Markdown ────────────────────────────────────────────────────
def md_block(titel, zeilen, risk_spalte="Risk"):
    out = [f"\n### {titel}\n"]
    out.append(f"| {risk_spalte} | Status | Cash | Pos | letzter Trade | Grund |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    for z in zeilen:
        out.append(f"| {z[0]} | {z[1]} | ${z[2]} | {z[3]} | {z[4]} | {z[5]} |")
    return "\n".join(out)

n_cash_ohne = sum(1 for z in aktien + etf + spec if z[1] == "CASH OHNE POS")
n_pos = sum(1 for z in aktien + etf + spec if z[1] == "POS")
n_leer = sum(1 for z in aktien + etf + spec if z[1] == "LEER")

md = f"""# Depot-Audit {DATUM} ({ZEIT})

> Taeglicher Snapshot aller Micro-Trader Depots. Kein KI-Call — reine Datei-Analyse.
> Cash da aber keine Position? Grund = KI-Entscheidung (halten/verkauft) aus ki_log.json.

**Zusammenfassung:** {len(aktien)+len(etf)+len(spec)} Depots gesamt |
POS: {n_pos} | CASH OHNE POS: {n_cash_ohne} | LEER: {n_leer}
"""

md += md_block("AKTIEN-DEPOTS (Risk 0-95)", aktien)
md += md_block("ETF-DEPOTS (Risk 0-95)", etf)
md += md_block("SPEC-DEPOTS", spec, risk_spalte="Ticker")

md_path = os.path.join(ARCHIV, f"depot-audit_{DATUM}.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write(md)

# ─── PDF (report_pdf.py Optik) ───────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak)
from reportlab.lib.enums import TA_CENTER

FONT = "Helvetica"
aria = "C:/Windows/Fonts/arial.ttf"
if os.path.exists(aria):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("Arial", aria))
    FONT = "Arial"

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Title"], fontName=FONT, fontSize=20, textColor=colors.HexColor("#1a3c5e"), spaceAfter=4)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontName=FONT, fontSize=10, textColor=colors.HexColor("#666"), alignment=TA_CENTER, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName=FONT, fontSize=13, textColor=colors.HexColor("#1a3c5e"), spaceBefore=10, spaceAfter=4)
NORM = ParagraphStyle("NORM", parent=styles["Normal"], fontName=FONT, fontSize=9, leading=12)
CELL = ParagraphStyle("CELL", parent=styles["Normal"], fontName=FONT, fontSize=7, leading=8.5)

def farbe(status):
    return { "POS": colors.HexColor("#e6f4ea"), "CASH OHNE POS": colors.HexColor("#fff4e5"),
             "LEER": colors.HexColor("#fce8e8") }.get(status, colors.white)

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def tabelle(titel, zeilen, risk_label):
    story = [Paragraph(titel, H2)]
    data = [[risk_label, "Status", "Cash", "Pos", "letzter Trade", "Grund"]]
    for z in zeilen:
        data.append([str(z[0]), z[1], f"${z[2]}", str(z[3]), z[4], Paragraph(esc(z[5]), CELL)])
    t = Table(data, colWidths=[22, 70, 38, 20, 44, 320])
    st = [("FONTNAME", (0,0), (-1,-1), FONT), ("FONTSIZE", (0,0), (-1,-1), 7.5),
          ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1a3c5e")),
          ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
          ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#ccc")),
          ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f7fa")])]
    for i, z in enumerate(zeilen, 1):
        st.append(("BACKGROUND", (1,i), (1,i), farbe(z[1])))
    t.setStyle(TableStyle(st))
    story.append(t)
    return story

pdf_path = os.path.join(ARCHIV, f"depot-audit_{DATUM}.pdf")
doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=12*mm, rightMargin=12*mm,
                        title=f"Depot-Audit {DATUM}")
story = [
    Paragraph(f"Micro-Trader — Depot-Audit {DATUM}", H1),
    Paragraph(f"Erstellt {ZEIT} · {len(aktien)+len(etf)+len(spec)} Depots · POS: {n_pos} · Cash-ohne-Pos: {n_cash_ohne} · Leer: {n_leer} · Kein KI-Call", SUB),
    Paragraph("Cash da aber keine Position = KI entscheidet bewusst HALTEN (Volumen/Trend/Warnregeln) oder Depot wurde verkauft. Kein Systemfehler.", NORM),
]
story += tabelle("Aktien-Depots (Risk 0-95)", aktien, "Risk")
story.append(PageBreak())
story += tabelle("ETF-Depots (Risk 0-95)", etf, "Risk")
story.append(Spacer(1, 8))
story += tabelle("Spec-Depots", spec, "Ticker")
doc.build(story)

print(f"Markdown: {md_path}")
print(f"PDF:      {pdf_path}")
print(f"Depots: {len(aktien)+len(etf)+len(spec)} | POS {n_pos} | Cash-ohne-Pos {n_cash_ohne} | Leer {n_leer}")
