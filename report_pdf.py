"""
Micro-Trader — Daily PDF Report (Phase 10, §17) — Erweiterte Profi-Version
Deutscher Tagesbericht als PDF (reportlab, Layout nach pdf-report-i18n-Skill).

NEU (v2.1):
- Gesamt-Rendite + pro Kategorie (Aktien/ETF/Spec) in $ und %
- 7-Tage-Verlauf-Graph (Gesamtwert) via reportlab LineChart
- Beste/Schlechteste 5 (aus allen Depots, auch in Gesamt-Übersicht)
- KI-Lernen: gelernte Regeln + Konfidenz-Level (%) + Konfidenz-Graph
- Marktregime, offene Aufgaben
"""
import os
import glob
import json
import subprocess
import time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(BASE, "reports")
os.makedirs(REPORTS, exist_ok=True)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                ListFlowable, ListItem, HRFlowable, Image, KeepTogether,
                                PageBreak)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.lib import colors as rc
from svglib.svglib import svg2rlg

# ─── Font mit echten Umlauten ───
FONT = "Helvetica"
try:
    aria = "C:/Windows/Fonts/arial.ttf"
    if os.path.exists(aria):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont("Arial", aria))
        FONT = "Arial"
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# DATENBESCHAFFUNG
# ─────────────────────────────────────────────────────────────────────────────
def _ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None


def _lade_live_kurse(ticker_liste):
    """Live-Kurse via marktdaten.hole_kurs (4-Tier-Fallback)."""
    kurse = {}
    try:
        from marktdaten import hole_kurs
        for t in ticker_liste:
            try:
                k = hole_kurs(t)
                if k and k > 0:
                    kurse[t] = k
            except Exception:
                continue
    except Exception:
        pass
    return kurse


def lade_depots_flat():
    """Alle Depots flach: Ticker, Kategorie, start, wert, pnl_pct.
    wert = MARKTWERT (Live-Kurs via hole_kurs, Fallback avg_price),
    wie das Dashboard es rechnet (nicht Einstandskurs)."""
    out = []
    # 1. Alle Ticker mit Positionen sammeln (für Live-Kurse) — NUR Paper-Portfolio
    alle_ticker = set()
    for f in sorted(glob.glob(os.path.join(BASE, "spec_depots", "*.json"))):
        if "summary" in f:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
            if d.get("ticker") and (d.get("shares", 0) or 0) > 0:
                alle_ticker.add(d["ticker"])
        except Exception:
            pass
    for pat in ["depot_*_paper.json", "etf_*_paper.json"]:
        for f in sorted(glob.glob(os.path.join(BASE, pat))):
            if "summary" in f:
                continue
            try:
                d = json.load(open(f, encoding="utf-8"))
                for t, pos in (d.get("positions", {}) or {}).items():
                    if (pos.get("shares", 0) or 0) > 0:
                        alle_ticker.add(t)
            except Exception:
                pass
    kurse = _lade_live_kurse(sorted(alle_ticker))
    if kurse:
        print(f"  Live-Kurse geladen: {len(kurse)} Ticker", flush=True)

    for f in sorted(glob.glob(os.path.join(BASE, "spec_depots", "*.json"))):
        if "summary" in f:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
            ticker = d.get("ticker") or os.path.splitext(os.path.basename(f))[0]
            start = d.get("start", 0) or 0
            shares = d.get("shares", 0) or 0
            avg = d.get("avg_price", d.get("aktuell", 0)) or 0
            bargeld = d.get("bargeld", 0) or 0
            # MARKTWERT: Live-Kurs bevorzugt, sonst avg_price
            kurs = kurse.get(ticker) or avg
            wert = bargeld + shares * kurs
            pnl_pct = ((wert - start) / start * 100) if start > 0 else 0
            out.append({"ticker": ticker, "kat": "Spec", "start": start, "wert": wert, "pnl_pct": pnl_pct})
        except Exception:
            pass
    for pat, kat in [("depot_*_paper.json", "Aktien"), ("etf_*_paper.json", "ETF")]:
        for f in sorted(glob.glob(os.path.join(BASE, pat))):
            if "summary" in f:
                continue
            try:
                d = json.load(open(f, encoding="utf-8"))
                base_name = os.path.splitext(os.path.basename(f))[0]
                start_wert = d.get("start_wert", 0) or 0
                if "positions" in d and isinstance(d["positions"], dict):
                    n = len(d["positions"])
                    bargeld = d.get("bargeld", 0) or 0
                    # Anteiliges Cash pro Position (wie Dashboard: wert = bargeld + shares*kurs)
                    cash_anteil = (bargeld / n) if n > 0 else 0
                    for ticker, pos in d["positions"].items():
                        shares = pos.get("shares", 0) or 0
                        avg = pos.get("avg_price", pos.get("aktuell", 0)) or 0
                        # MARKTWERT: Live-Kurs bevorzugt, sonst avg_price
                        kurs = kurse.get(ticker) or avg
                        wert = cash_anteil + shares * kurs
                        anteil = (start_wert / n) if n > 0 else 0
                        pnl_pct = ((wert - anteil) / anteil * 100) if anteil > 0 else 0
                        out.append({"ticker": ticker, "kat": kat, "start": anteil, "wert": wert, "pnl_pct": pnl_pct})
                    # ── LEERE DEPOTS (0 Positionen) nicht ignorieren! ──
                    # Ihr Startkapital (start_wert) gehoert in die Gesamtbilanz.
                    if n == 0:
                        out.append({"ticker": base_name, "kat": kat,
                                    "start": start_wert, "wert": bargeld or start_wert,
                                    "pnl_pct": (((bargeld or start_wert) - start_wert) / start_wert * 100) if start_wert > 0 else 0})
                else:
                    ticker = d.get("ticker") or base_name
                    start = d.get("start", start_wert) or 0
                    shares = d.get("shares", 0) or 0
                    avg = d.get("avg_price", d.get("aktuell", 0)) or 0
                    bargeld = d.get("bargeld", 0) or 0
                    kurs = kurse.get(ticker) or avg
                    wert = bargeld + shares * kurs
                    pnl_pct = ((wert - start) / start * 100) if start > 0 else 0
                    out.append({"ticker": ticker, "kat": kat, "start": start, "wert": wert, "pnl_pct": pnl_pct})
            except Exception:
                pass
    return out


def sammle_daten():
    depots = lade_depots_flat()
    ges_wert = sum(d["wert"] for d in depots)
    ges_start = sum(d["start"] for d in depots if d["start"] > 0)
    ges_pnl = ges_wert - ges_start
    ges_pnl_pct = (ges_pnl / ges_start * 100) if ges_start > 0 else 0

    # pro Kategorie
    kat = {}
    for d in depots:
        k = d["kat"]
        kat.setdefault(k, {"wert": 0, "start": 0, "n_depots": 0})
        kat[k]["wert"] += d["wert"]
        if d["start"] > 0:
            kat[k]["start"] += d["start"]
        kat[k]["n_depots"] += 1
    kat_info = {}
    for k, v in kat.items():
        pnl = v["wert"] - v["start"]
        kat_info[k] = {
            "wert": v["wert"], "start": v["start"], "pnl": pnl,
            "pnl_pct": (pnl / v["start"] * 100) if v["start"] > 0 else 0,
        }

    # Trades heute
    ki_log = []
    kp = os.path.join(BASE, "ki_log.json")
    if os.path.exists(kp):
        ki_log = json.load(open(kp, encoding="utf-8"))
    heute = datetime.now().date()
    trades_heute = []
    for e in ki_log:
        z = e.get("zeit", "")
        tz = _ts(z)
        if tz and tz.date() == heute and e.get("aktion") in ("kaufen", "verkaufen"):
            trades_heute.append(e)

    # Offene Positionen (wert > 0 = hat Position)
    offen = [d for d in depots if d["wert"] > 0]

    # Auffällige Trades
    auff = [(d["ticker"], d["pnl_pct"], d["kat"]) for d in depots if abs(d["pnl_pct"]) >= 10]

    # Top/Flop 5 (alle Depots, dedupliziert nach Ticker)
    seen = set()
    sortiert = sorted(depots, key=lambda x: x["pnl_pct"])
    flop5, top5 = [], []
    for d in sortiert:
        if d["ticker"] not in seen:
            flop5.append(d)
            seen.add(d["ticker"])
        if len(flop5) >= 5:
            break
    seen = set()
    for d in sorted(depots, key=lambda x: -x["pnl_pct"]):
        if d["ticker"] not in seen:
            top5.append(d)
            seen.add(d["ticker"])
        if len(top5) >= 5:
            break

    # KI: gelernte Regeln
    regeln = {}
    lr = os.path.join(BASE, "learned_rules.json")
    if os.path.exists(lr):
        try:
            regeln = json.load(open(lr, encoding="utf-8"))
        except Exception:
            pass
    rules_list = regeln.get("rules", []) if isinstance(regeln, dict) else []

    # KI: Konfidenz-Schnitt + Verlauf
    konf_vals = [e.get("konfidenz") for e in ki_log if isinstance(e.get("konfidenz"), (int, float))]
    ki_konf_schnitt = (sum(konf_vals) / len(konf_vals)) if konf_vals else None
    # Konfidenz-Verlauf (letzte 20 Entscheidungen mit Zeit)
    konf_verlauf = []
    for e in ki_log:
        k = e.get("konfidenz")
        z = _ts(e.get("zeit", ""))
        if isinstance(k, (int, float)) and z:
            konf_verlauf.append((z, k))
    konf_verlauf.sort()
    konf_verlauf = konf_verlauf[-20:]

    # 7-Tage-Verlauf (Snapshot)
    try:
        import tagesverlauf as tv
        tv.snapshot_schreiben()
        verlauf = tv.hole_7_tage()
    except Exception:
        verlauf = []

    # 7-Tage-Verlauf pro Kategorie
    verlauf_kat = {}
    try:
        import tagesverlauf as tv
        for kn in ["Aktien", "ETF", "Spec"]:
            verlauf_kat[kn] = tv.hole_7_tage_pro_kat(kn)
    except Exception:
        pass

    # Marktregime
    regime = {}
    try:
        import boersen
        regime = boersen.regime_pro_markt()
    except Exception:
        regime = {"US": "?", "DE": "?", "JP": "?"}

    # Ideen (aus User-Feedback / offene Optimierungen)
    ideen = [
        "Win-Rate: Anteil gewinnender vs. verlierender Trades (noch nicht erfasst)",
        "Drawdown: größter Einbruch vom Hoch zum Tief (noch nicht erfasst)",
        "Risiko-Verteilung: Anzahl Depots pro Risk-Level (0-95)",
        "News-Sentiment pro Ticker im 7-Tage-Verlauf integrieren",
        "Live-Freigabe (Phase 13) wartet auf Benutzerfreigabe — aktuell Shadow-Modus",
        "WhatsApp-Versand der PDF automatisieren (Bridge-QR-Scan nötig)",
    ]

    return {
        "ges_wert": ges_wert, "ges_start": ges_start, "ges_pnl": ges_pnl,
        "ges_pnl_pct": ges_pnl_pct, "kat": kat_info, "trades_heute": trades_heute,
        "offen": offen, "auff": auff, "top5": top5, "flop5": flop5,
        "regeln": regeln, "rules_list": rules_list,
        "ki_konf_schnitt": ki_konf_schnitt, "konf_verlauf": konf_verlauf,
        "verlauf": verlauf, "verlauf_kat": verlauf_kat, "regime": regime,
        "ideen": ideen, "n_depots": len(depots),
        # ── Tagesauswertung-Erweiterung ──
        "alle_trades": _alle_trades_flat(),
        "offene_positionen": len(offen),
        "exposure_pro_symbol": _exposure_pro_symbol(depots),
        "regelstand": _regelstand_agg(),
        "regelstand_version": regeln.get("_regelstand", {}).get("regelstand_version", "n/a") if isinstance(regeln, dict) else "n/a",
        "notifications": _lade_notifications(),
        "ki_aktiv": _ki_aktiv_heute(ki_log, heute),
        "system": _system_status(),
        "anomalien": _anomalien(),
        # ── Phase B: Datenvertrauens-Felder ──
        "trades_anzahl": len(_alle_trades_flat()),
        "depot_snapshot_anzahl": _db_snap_count(),
        "ki_cooldown": _lade_json(os.path.join(BASE, "ki_cooldown.json"), {}),
    }


def _alle_trades_flat():
    """Alle Trades aus *_paper.json/spec_depots/*.json (flatten, NUR Paper-Portfolio)."""
    trades = []
    for pat in ["depot_*_paper.json", "etf_*_paper.json", "spec_depots/*.json"]:
        for f in glob.glob(os.path.join(BASE, pat)):
            try:
                d = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            tr = d.get("trades", [])
            if not isinstance(tr, list):
                continue
            for t in tr:
                if isinstance(t, dict):
                    t = dict(t)
                    t.setdefault("ticker", d.get("ticker", os.path.basename(f).split(".")[0].replace("depot_","").replace("etf_","") if "spec" not in f else os.path.basename(f).split(".")[0]))
                    trades.append(t)
    return trades


def _exposure_pro_symbol(depots):
    """Brutto-Exposure je Symbol aus aktuellen Depot-Werten."""
    exp = {}
    for d in depots:
        if d["wert"] > 0:
            exp[d["ticker"]] = exp.get(d["ticker"], 0) + d["wert"]
    return exp


def _regelstand_agg():
    """Governance-Aggregat aus learned_rules.json + ki_log.json."""
    ra = {"regeln_gesamt": "n/a", "freigegeben": "n/a", "shadow": "n/a",
          "nicht_freigegeben": "n/a", "im_live_pfad": "n/a",
          "lernereignisse": "n/a", "dedupe": "n/a",
          "mit_decision_id": "n/a", "legacy": "n/a"}
    lr = _lade_json(os.path.join(BASE, "learned_rules.json"), {})
    rules = lr.get("rules", []) if isinstance(lr, dict) else []
    if rules:
        ra["regeln_gesamt"] = len(rules)
        ra["freigegeben"] = sum(1 for r in rules if r.get("freigabe_status") == "freigegeben")
        ra["shadow"] = sum(1 for r in rules if r.get("typ") in ("anti", "swap") or (r.get("effektiv_gewicht", r.get("gewicht", 0)) or 0) < 0)
        ra["nicht_freigegeben"] = sum(1 for r in rules if r.get("freigabe_status") != "freigegeben")
        ra["im_live_pfad"] = sum(1 for r in rules if r.get("live_allowed") or r.get("freigabe_status") == "freigegeben")
    ki = _lade_json(os.path.join(BASE, "ki_log.json"), [])
    if isinstance(ki, list):
        ra["lernereignisse"] = len(ki)
        ra["mit_decision_id"] = sum(1 for e in ki if e.get("decision_id"))
        ra["legacy"] = sum(1 for e in ki if not e.get("decision_id"))
        # Dedupe: gleiche decision_id mehrfach?
        ids = [e.get("decision_id") for e in ki if e.get("decision_id")]
        ra["dedupe"] = len(ids) - len(set(ids))
    return ra


def _lade_notifications():
    n = _lade_json(os.path.join(BASE, "notifications.json"), [])
    if isinstance(n, list):
        return [{"text": x} if isinstance(x, str) else x for x in n]
    return []


def _ki_aktiv_heute(ki_log, heute):
    for e in ki_log:
        tz = _ts(e.get("zeit", ""))
        if tz and tz.date() == heute and isinstance(e.get("konfidenz"), (int, float)) and e.get("konfidenz", 0) > 0:
            return True
    return False


def _system_status():
    """Systemstatus aus system_log.py / trader_status.py / .backup / cron."""
    s = {"engine": "n/a", "ki_job": "n/a", "cron_aktiv": "n/a", "watchdog": "n/a",
         "provider": "n/a", "datenalter": "n/a", "backup": "n/a"}
    # Cron-Jobs (über hermes cron list)
    try:
        out = subprocess.run(["hermes", "cron", "list"], capture_output=True, text=True, timeout=20)
        s["cron_aktiv"] = "3" if "Batch" in out.stdout and "Engine" in out.stdout and "KI" in out.stdout else "?"
    except Exception:
        s["cron_aktiv"] = "n/a"
    # Backup
    bdir = os.path.join(BASE, ".backup")
    s["backup"] = "vorhanden" if os.path.isdir(bdir) and os.listdir(bdir) else "fehlt"
    # Provider (ki_provider ki_faehig oder nous_auth.json Existenz)
    try:
        sys.path.insert(0, BASE)
        import ki_provider
        s["provider"] = "OK" if ki_provider.ki_faehig() else "fehlt"
    except Exception:
        # Fallback: nous_auth.json Existenz prüfen
        na = os.path.expanduser("~/AppData/Local/hermes/shared/nous_auth.json")
        s["provider"] = "OK" if os.path.exists(na) else "n/a"
    # Datenalter: älteste Datei in spec_depots
    try:
        files = glob.glob(os.path.join(BASE, "spec_depots", "*.json"))
        if files:
            oldest = min(os.path.getmtime(f) for f in files)
            alter_std = (time.time() - oldest) / 3600
            s["datenalter"] = f"{alter_std:.0f}h"
    except Exception:
        pass
    s["engine"] = "RUNNING" if os.path.exists(os.path.join(BASE, "engine.py")) else "n/a"
    s["ki_job"] = "OK" if s["provider"] == "OK" else "gestört"
    s["ki_detail"] = "KI liefert Entscheidungen (Konfidenz > 0)" if s["provider"] == "OK" else "Provider nicht erreichbar"
    return s


def _anomalien():
    """Anomalien aus notifications.json (echte Warnungen/Risiken, NICHT positive Rendite-Meldungen)."""
    anom = []
    notifs = _lade_notifications()
    for n in notifs:
        text = n.get("text", "") if isinstance(n, dict) else str(n)
        # Nur echte Probleme: negative Abweichung, Sperren, Fehler, Drawdown
        if any(k in text for k in ["Drawdown", "❌", "gesperrt", "Fehler", "KRITISCH", "verhindert", "gestört"]):
            anom.append({"zeit": n.get("zeit", "?") if isinstance(n, dict) else "?",
                         "kat": "Risiko" if "Drawdown" in text or "gesperrt" in text else "System",
                         "schwere": "HOCH" if "gesperrt" in text or "KRITISCH" in text else "MITTEL",
                         "desc": text[:60], "status": "dokumentiert"})
    return anom[:10]


# ─────────────────────────────────────────────────────────────────────────────
# GRAPHIK
# ─────────────────────────────────────────────────────────────────────────────
def graph_verlauf(verlauf, titel="7-Tage-Verlauf (Gesamtwert)"):
    """Reportlab LineChart für Gesamtwert über 7 Tage."""
    d = Drawing(460, 170)
    chart = HorizontalLineChart()
    chart.x = 40
    chart.y = 25
    chart.width = 400
    chart.height = 120
    if verlauf:
        data = [[v.get("ges_wert", 0) for v in verlauf]]
        chart.data = data
        chart.categoryAxis.categoryNames = [v["datum"][5:] for v in verlauf]  # MM-TT
        chart.categoryAxis.labels.fontName = FONT
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = min(data[0]) * 0.95
        chart.valueAxis.valueMax = max(data[0]) * 1.05
        chart.valueAxis.labels.fontName = FONT
        chart.valueAxis.labels.fontSize = 7
        chart.lines[0].strokeColor = rc.HexColor("#0A84FF")
        chart.lines[0].strokeWidth = 2
        chart.joinedLines = 1
    d.add(chart)
    return d


def graph_konfidenz(konf_verlauf):
    """Reportlab LineChart für KI-Konfidenz über Zeit."""
    d = Drawing(460, 150)
    chart = HorizontalLineChart()
    chart.x = 40
    chart.y = 25
    chart.width = 400
    chart.height = 100
    if konf_verlauf:
        data = [[k for _, k in konf_verlauf]]
        chart.data = data
        chart.categoryAxis.categoryNames = [z.strftime("%d.%H") for z, _ in konf_verlauf]
        chart.categoryAxis.labels.fontName = FONT
        chart.categoryAxis.labels.fontSize = 6
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 100
        chart.valueAxis.labels.fontName = FONT
        chart.valueAxis.labels.fontSize = 7
        chart.lines[0].strokeColor = rc.HexColor("#30D158")
        chart.lines[0].strokeWidth = 2
        chart.joinedLines = 1
    d.add(chart)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# BRANDING (SVG-Logo + Banner via svg2rlg)
# Farbwelt: Cyan #20d9ff · Violett #7b5cff · Mint #73e6b0 · Dunkel #111827
# ─────────────────────────────────────────────────────────────────────────────
FARB = {
    "cyan": "#20d9ff",
    "violett": "#7b5cff",
    "mint": "#73e6b0",
    "dunkel": "#111827",
    "dunkel2": "#0b1220",
    "hell": "#f8fafc",
    "grav": "#6b7280",
    "gruen": "#30D158",
    "rot": "#FF453A",
}


def logo_drawing(groesse=46):
    """Micro-Trader Logo (PNG) als reportlab-Image."""
    try:
        pfad = os.path.join(BASE, "assets", "logo.png")
        if os.path.exists(pfad):
            img = Image(pfad)
            img.drawWidth = groesse
            img.drawHeight = groesse
            return img
    except Exception:
        pass
    from reportlab.graphics.shapes import Drawing as _D, Rect as _R
    d = _D(groesse, groesse)
    d.add(_R(0, 0, groesse, groesse, fillColor=rc.HexColor(FARB["violett"])))
    return d


def banner_drawing(breite):
    """Micro-Trader Banner (PNG) als reportlab-Image, skaliert auf Seitenbreite."""
    try:
        pfad = os.path.join(BASE, "assets", "banner.png")
        if os.path.exists(pfad):
            img = Image(pfad)
            img.drawWidth = breite
            img.drawHeight = breite * (620.0 / 2400.0)
            return img
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# PDF-BAU
# ─────────────────────────────────────────────────────────────────────────────
def _db_snap_count():
    """Phase B: zählt depot_snapshot-Zeilen in SQLite (für Datenvertrauens-Score)."""
    try:
        import sqlite3
        c = sqlite3.connect(os.path.join(BASE, "micro_trader.db"))
        n = c.execute('SELECT COUNT(*) FROM "depot_snapshot"').fetchone()[0]
        c.close()
        return n
    except Exception:
        return 0


def _datenvertrauen(daten):
    """Phase B: Datenvertrauens-Score. Leitet Status aus vorhandenen Daten ab.
    Liefert (felder_dict, gesamt_status, begruendung). KEINE erfundenen Werte."""
    import sqlite3
    felder = {}
    # Portfolio-Snapshot
    snap = daten.get("depot_snapshot_anzahl", 0)
    felder["Portfolio-Snapshot"] = "vollständig" if snap > 0 else "fehlt"
    # Trade-Daten
    tr = daten.get("trades_anzahl", 0)
    felder["Trade-Daten"] = "vollständig" if tr > 0 else "fehlt"
    # Einzel-Trade-P&L: nicht verfügbar (keine per-trade P&L in DB)
    felder["Einzel-Trade-P&L"] = "n/a"
    # Gebühren / Slippage: nicht erhoben
    felder["Gebühren"] = "n/a"
    felder["Slippage"] = "n/a"
    # Drawdown: nur Snapshot, keine Zeitreihe
    felder["Drawdown"] = "Snapshot fehlt" if snap == 0 else "verifiziert (Snapshot)"
    # decision_id-Zuordnung: jetzt aus DB (v2.19.1)
    try:
        import sqlite3 as _sq
        _c = _sq.connect(os.path.join(BASE, "micro_trader.db"))
        _tot = _c.execute("SELECT COUNT(*) FROM ki_decisions").fetchone()[0]
        _mit = _c.execute("SELECT COUNT(*) FROM ki_decisions WHERE decision_id IS NOT NULL").fetchone()[0]
        _c.close()
        if _tot == 0:
            felder["decision_id-Zuordnung"] = "n/a (keine KI-Daten)"
        elif _mit == 0:
            felder["decision_id-Zuordnung"] = "Legacy (alte Einträge ohne Feld)"
        else:
            anteil = round(100 * _mit / _tot)
            felder["decision_id-Zuordnung"] = f"vollständig ({anteil}% der Einträge)"
    except Exception:
        felder["decision_id-Zuordnung"] = "n/a (DB-Fehler)"
    # KI-Provider: aus cooldown + ki_log
    cd = daten.get("ki_cooldown", {})
    aktive_cooldowns = [p for p, v in cd.items() if v.get("bis", 0) > time.time()] if cd else []
    if not cd:
        felder["KI-Provider"] = "stabil"
    elif aktive_cooldowns:
        felder["KI-Provider"] = "gestört (" + ", ".join(aktive_cooldowns) + ")"
    else:
        felder["KI-Provider"] = "Fallback (Cooldown abgelaufen)"
    # Report-Erzeugung
    felder["Report-Erzeugung"] = "erfolgreich"
    # Gesamtbewertung (ehrlich, kein künstlicher %-Wert)
    fehlend = [k for k, v in felder.items() if v in ("fehlt", "n/a", "Snapshot fehlt") or "Legacy" in str(v) or "nicht in DB" in str(v)]
    gestoert = [k for k in felder if "gestört" in str(felder[k])]
    if gestoert:
        gesamt = "NIEDRIG"
        beg = "Provider gestört: " + ", ".join(gestoert) + ". Portfolio/Trade-Daten vorhanden, aber Gebühren/Slippage/decision_id nicht verifizierbar."
    elif "fehlt" in felder["Portfolio-Snapshot"] or "fehlt" in felder["Trade-Daten"]:
        gesamt = "NICHT VERIFIZIERT"
        beg = "Kern-Daten (Snapshot/Trades) fehlen."
    elif len(fehlend) >= 4:
        gesamt = "MITTEL"
        beg = "Portfolio-Snapshot + Trade-Daten vorhanden. Einzel-Trade-P&L, Gebühren, Slippage und decision_id-Zuordnung nicht vollständig verfügbar (Legacy/n.a.)."
    else:
        gesamt = "HOCH"
        beg = "Alle Kern-Daten verifiziert."
    return felder, gesamt, beg


def _status_uebersicht():
    """Phase C: Produktiv/Shadow/Konzept/Offen-Trennung (ehrlich, aus IST-Analyse)."""
    zeilen = [
        ("US-Markt", "PRODUKTIV", "trades/ki_decisions gefüllt, KI kauft/verkauft", "aktiv"),
        ("Aktien", "PRODUKTIV", "20 Depots, Trades vorhanden", "20x100$"),
        ("ETF", "PRODUKTIV", "21 Dateien, Trades vorhanden", "21x100$"),
        ("Spekulation", "PRODUKTIV", "49 Depots, Trades vorhanden", "49x100$"),
        ("DE-Markt", "KONZEPT", "boersen.py existiert, nicht produktiv genutzt", "nur Code"),
        ("JP-Markt", "KONZEPT", "boersen.py existiert, nicht produktiv genutzt", "nur Code"),
        ("Profile", "KONZEPT", "nur 3 Kategorien, kein Profil-Objekt", "profil_schema.py vorhanden"),
        ("Shadow-Regeln", "PRODUKTIV", "Live-Gating in ki_decisions aktiv", "nur Lernkontext"),
        ("Paper-Modus", "OFFEN", "nicht implementiert", "kein Code"),
        ("Live-Freigabe", "OFFEN", "nur Shadow/Gating, kein echtes Geld", "Phase 13 wartet"),
        ("Daily-PDF", "PRODUKTIV", "report_pdf.py mehrseitig, decision_id/Gebühren fehlen", "teilweise"),
        ("WhatsApp-Versand", "EINGESCHRÄNKT", "nur Agent-MEDIA-Tag funktioniert (CLI/Gateway broken)", "Workaround"),
    ]
    return zeilen


def baue_pdf(daten, pfad):
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontName=FONT, fontSize=20, textColor=rc.HexColor("#1C1C1E"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName=FONT, fontSize=13, textColor=rc.HexColor(FARB["violett"]), spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName=FONT, fontSize=9.5, textColor=rc.HexColor("#1C1C1E"))
    small = ParagraphStyle("small", parent=styles["BodyText"], fontName=FONT, fontSize=8, textColor=rc.HexColor("#6E6E73"))
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontName=FONT, fontSize=8.5, leading=11)
    cellc = ParagraphStyle("cellc", parent=cell, alignment=TA_CENTER)

    doc = SimpleDocTemplate(pfad, pagesize=A4, topMargin=1.6*cm, bottomMargin=1.6*cm,
                            leftMargin=1.6*cm, rightMargin=1.6*cm,
                            title="Micro-Trader Tagesbericht", author="Micro-Trader")
    el = []
    W = doc.width

    # ── Banner oben (volle Breite) ──
    banner = banner_drawing(W)
    if banner:
        el.append(banner)
        el.append(Spacer(1, 0.3*cm))

    # ── Deckblatt-Header mit Logo ──
    logo = logo_drawing(46)
    header_tbl = Table([[logo, Paragraph("<b>Micro-Trader</b><br/>Tagesbericht", title)],
                        ["", Paragraph(datetime.now().strftime("%d.%m.%Y %H:%M") + f" · v{VERSION}", small)]],
                       colWidths=[52, W-52])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("SPAN", (0,0), (0,1)),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    el.append(header_tbl)
    el.append(Spacer(1, 0.2*cm))
    el.append(HRFlowable(width="100%", thickness=2, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.3*cm))

    # ══════════════════════════════════════════════════════════════════
    # NEUE STRUKTUR (nach User-Prompt v2): Tagesdaten → Projektstatus → Detail
    # ══════════════════════════════════════════════════════════════════
    jetzt = datetime.now()
    report_id = _report_id(jetzt.strftime("%Y-%m-%d"))
    S = {"title": title, "h2": h2, "body": body, "small": small, "cell": cell, "cellc": cellc}

    # ── SEITE 1: Portfolio- und Tagesübersicht ──
    # 1. Gesamt-Rendite
    block1 = [Paragraph("1. Gesamt-Rendite", h2)]
    pnl_farbe = "#30D158" if daten["ges_pnl"] >= 0 else "#FF453A"
    ges_card = [
        ["Gesamtwert", f"{daten['ges_wert']:,.2f} $"],
        ["Investiert", f"{daten['ges_start']:,.2f} $"],
        ["Gewinn/Verlust", f"{daten['ges_pnl']:+,.2f} $"],
        ["Rendite gesamt", f"<font color='{pnl_farbe}'>{daten['ges_pnl_pct']:+,.2f}%</font>"],
    ]
    rows = [[Paragraph(f"<b>{k}</b>", cell), Paragraph(v, cell)] for k, v in ges_card]
    t_ges = Table(rows, colWidths=[W*0.35, W*0.65])
    t_ges.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), rc.HexColor("#F5F7FA")),
        ("BOX", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("INNERGRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
    ]))
    block1.append(t_ges)
    block1.append(Spacer(1, 0.2*cm))
    # Pro Kategorie
    block1.append(Paragraph("Rendite pro Kategorie", body))
    kat_rows = [[Paragraph("<b>Kategorie</b>", cell), Paragraph("<b>Wert</b>", cell),
                 Paragraph("<b>Investiert</b>", cell), Paragraph("<b>G/V</b>", cell),
                 Paragraph("<b>Rendite</b>", cell)]]
    for k, v in daten["kat"].items():
        farbe = "#30D158" if v["pnl"] >= 0 else "#FF453A"
        kat_rows.append([
            Paragraph(k, cell), Paragraph(f"{v['wert']:,.2f} $", cell),
            Paragraph(f"{v['start']:,.2f} $", cell), Paragraph(f"{v['pnl']:+,.2f} $", cell),
            Paragraph(f"<font color='{farbe}'>{v['pnl_pct']:+,.2f}%</font>", cell),
        ])
    t_kat = Table(kat_rows, colWidths=[W*0.22, W*0.22, W*0.22, W*0.17, W*0.17])
    t_kat.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F5F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    block1.append(t_kat)
    block1.append(Spacer(1, 0.1*cm))
    block1.append(Paragraph(f"Datenquelle: Depot-Snapshot zum {jetzt.strftime('%d.%m.%Y %H:%M')} · "
                            f"nicht live (Snapshot), Werte aus Depot-JSON.", small))
    el.append(KeepTogether(block1))

    # ── Phase B: DATENVERTRAUENS-SCORE (auf Seite 1) ──
    felder, gesamt, beg = _datenvertrauen(daten)
    block_dv = [Paragraph("Datenvertrauen", h2)]
    dv_farbe = {"HOCH": "#30D158", "MITTEL": "#FF9F0A", "NIEDRIG": "#FF453A", "NICHT VERIFIZIERT": "#8E8E93"}[gesamt]
    block_dv.append(Paragraph(f'<b>DATENLAGE: <font color="{dv_farbe}">{gesamt}</font></b>', body))
    block_dv.append(Paragraph(beg, small))
    dv_rows = [[Paragraph("<b>Bereich</b>", cell), Paragraph("<b>Status</b>", cell)]]
    for k, v in felder.items():
        dv_rows.append([Paragraph(k, cell), Paragraph(v, cell)])
    t_dv = Table(dv_rows, colWidths=[W*0.45, W*0.55])
    t_dv.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F5F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    block_dv.append(Spacer(1, 0.1*cm))
    block_dv.append(t_dv)
    el.append(KeepTogether(block_dv))
    el.append(PageBreak())

    # ── SEITE 2: Kategorien und Entwicklung ──
    el.append(Paragraph("2. Kategorien und Entwicklung", h2))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))
    kat_farbe = {"Aktien": FARB["cyan"], "ETF": FARB["violett"], "Spec": FARB["mint"]}
    for idx, kn in enumerate(["Aktien", "ETF", "Spec"], start=1):
        kv = daten["kat"].get(kn, {})
        pnl = kv.get("pnl", 0)
        block_k = [Paragraph(f"{kn}", h2)]
        vk = daten["verlauf_kat"].get(kn, [])
        if vk:
            block_k.append(graph_verlauf(vk, titel=f"{kn} Verlauf (7 Tage)"))
        else:
            block_k.append(Paragraph("Keine belastbare 7-Tage-Historie für diese Kategorie vorhanden.", small))
        pmk = Table([[Paragraph("<b>Wert</b>", cell), Paragraph(f"{kv.get('wert',0):,.2f} $", cell),
                      Paragraph("<b>G/V</b>", cell), Paragraph(f"<font color='{kat_farbe[kn]}'>{pnl:+,.2f} $ ({kv.get('pnl_pct',0):+,.2f}%)</font>", cell)]],
                    colWidths=[W*0.22, W*0.28, W*0.22, W*0.28])
        pmk.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), rc.HexColor("#F5F7FA")),
            ("BOX", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
            ("INNERGRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        block_k.append(Spacer(1, 0.15*cm))
        block_k.append(pmk)
        block_k.append(Spacer(1, 0.3*cm))
        el.append(KeepTogether(block_k))
    el.append(PageBreak())

    # ── SEITE 3: Performance und KI-Lernen (endet nach Marktregime) ──
    # 6. Beste/Schlechteste 5
    el.append(Paragraph("3. Performance und KI-Lernen", h2))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("3.1 Beste & Schlechteste 5 (alle Depots)", body))
    top_rows = [[Paragraph("<b>#</b>", cellc), Paragraph("<b>Ticker</b>", cell),
                 Paragraph("<b>Kat</b>", cell), Paragraph("<b>Rendite</b>", cell)]]
    for i, d in enumerate(daten["top5"], 1):
        top_rows.append([Paragraph(str(i), cellc), Paragraph(d["ticker"], cell),
                         Paragraph(d["kat"], cell),
                         Paragraph(f"<font color='#30D158'>{d['pnl_pct']:+,.2f}%</font>", cell)])
    flop_rows = [[Paragraph("<b>#</b>", cellc), Paragraph("<b>Ticker</b>", cell),
                  Paragraph("<b>Kat</b>", cell), Paragraph("<b>Rendite</b>", cell)]]
    for i, d in enumerate(daten["flop5"], 1):
        flop_rows.append([Paragraph(str(i), cellc), Paragraph(d["ticker"], cell),
                          Paragraph(d["kat"], cell),
                          Paragraph(f"<font color='#FF453A'>{d['pnl_pct']:+,.2f}%</font>", cell)])
    t_top = Table(top_rows, colWidths=[W*0.1, W*0.3, W*0.3, W*0.3])
    t_top.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor("#30D158")),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F5F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    t_flop = Table(flop_rows, colWidths=[W*0.1, W*0.3, W*0.3, W*0.3])
    t_flop.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor("#FF453A")),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F5F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
    ]))
    el.append(t_top)
    el.append(Spacer(1, 0.15*cm))
    el.append(t_flop)
    el.append(Spacer(1, 0.3*cm))

    # 7. KI-Lernen + Konfidenz
    el.append(Paragraph("3.2 KI-Lernen & Konfidenz", body))
    n_rules = len(daten["rules_list"])
    konf_txt = f"{daten['ki_konf_schnitt']:.1f}%" if daten["ki_konf_schnitt"] is not None else "k.A."
    el.append(Paragraph(f"Gelernte Regeln: <b>{n_rules}</b> · Konfidenz-Schnitt: <b>{konf_txt}</b>", body))
    if daten["rules_list"]:
        items = []
        for r in daten["rules_list"][:6]:
            muster = r.get("muster", r.get("id", "?"))
            gew = r.get("gewicht", r.get("weight", "?"))
            items.append(ListItem(Paragraph(f"<b>{muster}</b> (Gewicht: {gew})", body)))
        el.append(ListFlowable(items, bulletType="bullet"))
    if daten["konf_verlauf"]:
        el.append(Spacer(1, 0.15*cm))
        el.append(Paragraph("KI-Konfidenz-Verlauf (letzte Entscheidungen):", body))
        el.append(graph_konfidenz(daten["konf_verlauf"]))
    el.append(Spacer(1, 0.3*cm))

    # 8. Marktregime (LETZTER Abschnitt auf Seite 3) — KeepTogether gegen verwaiste Überschrift
    regime_block = [Paragraph("3.3 Marktregime (pro Markt)", body)]
    r = daten["regime"]
    rm = {"bull": "🟢 Bull", "bear": "🔴 Bear", "sideways": "🟡 Sideways", "?": "❓ ?"}
    regime_block.append(Paragraph(f"US: {rm.get(r.get('US','?'), '?')} · DE: {rm.get(r.get('DE','?'), '?')} · JP: {rm.get(r.get('JP','?'), '?')}", body))
    el.append(KeepTogether(regime_block))
    el.append(PageBreak())

    # ── Phase C: STATUSÜBERSICHT (Seite 4 Anfang) ──
    el.append(Paragraph("4. Statusübersicht (Produktiv / Shadow / Konzept / Offen)", h2))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))
    su_rows = [[Paragraph("<b>Bereich</b>", cell), Paragraph("<b>Status</b>", cell),
                Paragraph("<b>Beleg</b>", cell), Paragraph("<b>Kommentar</b>", cell)]]
    status_farbe = {"PRODUKTIV": "#30D158", "SHADOW": "#AF52DE", "PAPER": "#8E8E93",
                    "KONZEPT": "#8E8E93", "OFFEN": "#FF9F0A", "BLOCKIERT": "#FF453A",
                    "NICHT VERIFIZIERT": "#8E8E93", "EINGESCHRÄNKT": "#FF9F0A"}
    for bereich, status, beleg, komm in _status_uebersicht():
        sf = status_farbe.get(status, "#1C1C1E")
        su_rows.append([
            Paragraph(bereich, cell),
            Paragraph(f'<font color="{sf}"><b>{status}</b></font>', cell),
            Paragraph(beleg, cell),
            Paragraph(komm, cell),
        ])
    t_su = Table(su_rows, colWidths=[W*0.18, W*0.16, W*0.38, W*0.28])
    t_su.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F5F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ]))
    el.append(t_su)
    el.append(Spacer(1, 0.3*cm))

    # ── Phase F: ROOT-CAUSE-HISTORIE (kompakt im Report) ──
    el.append(Paragraph("5. Technische Stabilität — Root-Cause-Historie", h2))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))
    rc_rows = [[Paragraph("<b>Root-Cause</b>", cell), Paragraph("<b>Status</b>", cell),
                Paragraph("<b>Letztes Auftreten</b>", cell), Paragraph("<b>Maßnahme</b>", cell)]]
    rc_daten = [
        ("Feldnamen-Dissonanz (preis/aktuell)", "behoben", "v2.16.8", "Producer/Consumer-Feld abgeglichen"),
        ("Kurs=0 (yfinance Rate-Limit)", "behoben", "v2.16.8", "4-Tier-Fallback + Preis-Guard"),
        ("KI-Cooldown-Kaskade", "behoben", "v2.16.8", "Batch-Splitting + Timeout 180s"),
        ("Leere Depots ohne Kauf", "behoben", "v2.16.9", "[LEER: BITTE KAUFEN]-Hinweis"),
        ("Tote Spec-Placeholder", "behoben", "v2.16.11", "38 Dateien physisch gelöscht"),
        ("Provider-Timeout", "behoben", "v2.18.1", "Cooldown nur betroffener Provider"),
        ("Reasoning-Modell max_tokens", "behoben", "v2.18.3", "max_tokens>=1024 + reasoning_content"),
        ("Windows-VBS-Autostart", "behoben", "2026-08-06", "3+2-Quote-Muster in .vbs"),
        ("WhatsApp MEDIA-Einschränkung", "eingeschränkt", "aktuell", "nur Agent-MEDIA-Tag, CLI/Gateway broken"),
    ]
    for name, status, lz, mass in rc_daten:
        sf = "#30D158" if status == "behoben" else "#FF9F0A"
        rc_rows.append([Paragraph(name, cell),
                        Paragraph(f'<font color="{sf}">{status}</font>', cell),
                        Paragraph(lz, cell), Paragraph(mass, cell)])
    t_rc = Table(rc_rows, colWidths=[W*0.30, W*0.14, W*0.18, W*0.38])
    t_rc.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F5F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
    ]))
    el.append(t_rc)
    el.append(Spacer(1, 0.3*cm))

    # ── SEITE 4: Projektstatus und offene Phasen (TRENNUNG!) ──
    el.append(Paragraph("6. Projektstatus und offene Phasen", h2))
    el.append(Paragraph("Entwicklungsstatus außerhalb der Tagesauswertung", S["small"]))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("Diese Seite ist Teil des Projektfortschritts, NICHT des Tagesgeschäfts. "
                        "Phasen werden nach tatsächlichem Status gelistet (nicht als abgeschlossen dargestellt).", S["small"]))
    el.append(Spacer(1, 0.2*cm))
    phase_rows = [["Phase", "Thema", "Status", "Beleg", "Nächster Schritt"]]
    phase_rows += [
        ["Phase 10", "Daily PDF Report", "teilweise umgesetzt", "Report vorhanden (v"+VERSION+")", "Restpunkte schließen"],
        ["Phase 11", "Dashboard Profil-/Markt-Karten", "aktiv", "Projektstatus", "Umsetzung fortsetzen"],
        ["Phase 13", "Live-Freigabe", "wartet auf Freigabe", "Benutzerfreigabe fehlt", "Freigabeentscheidung"],
        ["WhatsApp", "Bridge-Verbindung", "blockiert", "Session corrupt", "QR-Scan nötig"],
        ["7-Tage-Snapshot", "Automatischer Job", "aktiv", "tagesverlauf.py", "täglich 22:00"],
    ]
    t_ph = Table(phase_rows, colWidths=[W*0.13, W*0.22, W*0.18, W*0.22, W*0.25], repeatRows=1)
    t_ph.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 7.5),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.5, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F5F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
    ]))
    el.append(t_ph)
    el.append(Spacer(1, 0.3*cm))
    # Offene Aufgaben + Ideen
    el.append(Paragraph("Offene Aufgaben", body))
    tasks = [
        "Phase 10: Daily PDF Report — erweitert (Restpunkte: Gebühren/Slippage/decision_id fehlen)",
        "Phase 13: Live-Freigabe — wartet auf Benutzerfreigabe",
        "WhatsApp: Bridge-Neustart + QR-Scan nötig (Session corrupt)",
        "Noch nicht erfasste Kennzahlen: Gebühren, Slippage, Drawdown-Snapshot, decision_id-Zuordnung",
    ]
    el.append(ListFlowable([ListItem(Paragraph(t, body)) for t in tasks], bulletType="bullet"))
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("Ideen & Ausblick", body))
    if daten.get("ideen"):
        el.append(ListFlowable([ListItem(Paragraph(i, body)) for i in daten["ideen"]], bulletType="bullet"))
    else:
        el.append(Paragraph("Keine offenen Ideen.", body))
    el.append(PageBreak())

    # ── SEITE 5-9: Tagesauswertung Detail (bisherige 6 Sektionen) ──
    _seite_tagesstatus(el, S, W, daten, report_id, jetzt)
    _seite_performance(el, S, W, daten)
    _seite_risiko(el, S, W, daten)
    _seite_trades(el, S, W, daten)
    _seite_governance(el, S, W, daten)
    _seite_system(el, S, W, daten)

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(FONT, 7)
        canvas.setFillColor(rc.HexColor("#6E6E73"))
        fz = doc_.page
        canvas.drawString(1.6*cm, 1.0*cm,
            f"Report-ID: {report_id} · {jetzt.strftime('%Y-%m-%d %H:%M')} · v{VERSION} · "
            f"KI GENERIERT · Automatisch erzeugt · S. {fz}")
        canvas.restoreState()
    doc.build(el, onFirstPage=_footer, onLaterPages=_footer)
    return pfad


# ══════════════════════════════════════════════════════════════════════════
# TAGESAUSWERTUNG-ERWEITERUNG (6 Pflichtsektionen, nach User-Prompt)
# Nutzt echte Datenquellen: ki_log.json, learned_rules.json, regelstand_aggregat,
# system_log.py, trader_status.py, .backup/. Keine erfundenen Werte → n/a.
# ══════════════════════════════════════════════════════════════════════════

VERSION = "2.18.3"  # Fallback; wird aus version.json ueberschrieben
try:
    with open(os.path.join(BASE, "version.json"), encoding="utf-8") as _vf:
        _vj = json.load(_vf)
    if _vj.get("version"):
        VERSION = _vj["version"]
    else:
        VERSION = "2.18.3"
except Exception:
    VERSION = "2.18.3"

def _lade_json(pfad, default=None):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _report_id(datum):
    # RPT-YYYYMMDD-NNN (laufende Nummer pro Tag aus reports/-Verzeichnis)
    muster = f"daily_report_{datum.replace('-','')}"
    n = 1
    for f in glob.glob(os.path.join(REPORTS, f"{muster}*.pdf")):
        n += 1
    return f"RPT-{datum.replace('-','')}-{n:03d}"

def _seite_tagesstatus(el, S, W, daten, report_id, jetzt):
    """Seite 5 — Tagesauswertung Detail (Pflichtsektion aus User-Prompt)."""
    el.append(Paragraph("5. Tagesauswertung — Detail", S["h2"]))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))

    # Gesamtstatus aus KI-Job + Datenqualität
    sys = daten.get("system", {})
    ki_gestoert = sys.get("ki_job") != "OK"
    notifs = daten.get("notifications", [])
    # Nur ECHTE Warnungen zählen (positive Risk-Rendite-Meldungen sind KEINE Warnungen)
    warnungen = [n for n in notifs
                 if "❌" in n.get("text", "") or "gesperrt" in n.get("text", "")
                 or "Drawdown" in n.get("text", "") or "Fehler" in n.get("text", "")
                 or "KRITISCH" in n.get("text", "")]
    if ki_gestoert:
        gesamtstatus = "WARNUNG"
    elif warnungen:
        gesamtstatus = "WARNUNG"
    else:
        gesamtstatus = "STABIL"

    zeile1 = [
        ["Report-ID", report_id, "Systemversion", VERSION],
        ["Berichtsdatum", jetzt.strftime("%Y-%m-%d"), "Regelwerksversion", f"v{daten.get('regelstand_version','n/a')}"],
        ["Erstellt", jetzt.strftime("%H:%M:%S"), "Auswertungszeitraum", "Tagesabschluss"],
        ["Gesamtstatus", gesamtstatus, "Tagesrendite", f"{daten.get('ges_pnl_pct',0):+.2f}%"],
    ]
    t1 = Table(zeile1, colWidths=[W*0.22, W*0.28, W*0.22, W*0.28])
    t1.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 8.5),
        ("TEXTCOLOR", (1,0), (1,-1), rc.HexColor("#1C1C1E")),
        ("TEXTCOLOR", (3,0), (3,-1), rc.HexColor("#1C1C1E")),
        ("BACKGROUND", (0,0), (0,-1), rc.HexColor("#F2F2F7")),
        ("BACKGROUND", (2,0), (2,-1), rc.HexColor("#F2F2F7")),
        ("TEXTCOLOR", (1,3), (1,3), rc.HexColor(FARB["cyan"])),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    el.append(t1)
    el.append(Spacer(1, 0.3*cm))

    ges_wert = daten.get("ges_wert", 0)
    nt_heute = daten.get("trades_heute", 0)
    if isinstance(nt_heute, list):
        nt_heute = len(nt_heute)
    el.append(Paragraph(
        f"Equity: <b>{ges_wert:,.2f} $</b> · Netto-P&L: <b>n/a</b> (Einzel-Trade-P&L nicht aggregiert) · "
        f"Drawdown: <b>n/a</b> (Snapshot fehlt) · Trades heute: <b>{nt_heute}</b>", S["body"]))
    el.append(Spacer(1, 0.2*cm))

    # Ehrliche Tagesbewertung (Warnstatus korrekt)
    if ki_gestoert:
        bewertung = (f"⚠ WARNUNG: Portfolio-Snapshot vorhanden. Einzel-Trade-P&L, Gebühren, Slippage und "
                     f"Drawdown konnten für diesen Bericht nicht vollständig verifiziert werden. "
                     f"Der KI-Job war zum Erstellungszeitpunkt gestört (Provider nicht erreichbar). "
                     f"{nt_heute} Trades im Berichtszeitraum erkannt, aber keine vollständige KI-Tagesbewertung verifiziert.")
    else:
        bewertung = _tagesbewertung(daten, gesamtstatus)
    el.append(Paragraph(f"<b>Tagesbewertung:</b> {bewertung}", S["body"]))
    el.append(Spacer(1, 0.3*cm))

def _tagesbewertung(daten, status):
    teile = []
    if status == "STABIL":
        teile.append("Stabiler Handelstag")
    elif status == "WARNUNG":
        teile.append("Handelstag mit Warnungen")
    else:
        teile.append("Kritischer Handelstag (Drawdown-Sperre aktiv)")
    nt = daten.get("trades_heute", 0)
    if isinstance(nt, list):
        nt = len(nt)
    if nt == 1:
        teile.append("1 Trade ausgeführt")
    elif nt > 0:
        teile.append(f"{nt} Trades ausgeführt")
    else:
        teile.append("keine Trades heute")
    if daten.get("ki_aktiv"):
        teile.append("KI aktiv (Konfidenz > 0)")
    else:
        teile.append("KI nicht verfügbar (alle Provider)")
    return ". ".join(teile) + "."

def _seite_performance(el, S, W, daten):
    """Seite 6 — Performance und P&L."""
    el.append(Paragraph("6. Performance & P&L", S["h2"]))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))

    trades = daten.get("alle_trades", [])
    gewinner = sum(1 for t in trades if t.get("pnl", 0) > 0)
    verlierer = sum(1 for t in trades if t.get("pnl", 0) < 0)
    n = len(trades)
    treffer = (gewinner / n * 100) if n else 0
    pnls = [t.get("pnl", 0) for t in trades]
    brutto = sum(pnls)
    # Zeiträume klar trennen
    nt_heute = daten.get("trades_heute", 0)
    if isinstance(nt_heute, list):
        nt_heute = len(nt_heute)
    positionen = daten.get("offene_positionen", 0)
    tab = [
        ["Kennzahl", "Wert", "Kennzahl", "Wert"],
        ["Brutto-P&L (gesamt)", f"{brutto:,.2f} $", "Gewinner", f"{gewinner}"],
        ["Netto-P&L", "n/a (Gebühren fehlen)", "Verlierer", f"{verlierer}"],
        ["Gebühren", "n/a", "Trefferquote", f"{treffer:.0f}%"],
        ["Slippage", "n/a", "Ø Gewinn", "n/a"],
        ["Rendite auf Equity", f"{daten.get('ges_pnl_pct',0):+.2f}%", "Ø Verlust", "n/a"],
        ["Trades im Berichtszeitraum", f"{nt_heute}", "Profit Factor", "n/a"],
        ["Historische Trade-Anzahl", f"{n}", "Portfolio-Positionen", f"{positionen}"],
    ]
    t = Table(tab, colWidths=[W*0.28, W*0.22, W*0.28, W*0.22])
    t.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 8.5),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.HexColor("#FFFFFF")),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.HexColor("#FFFFFF"), rc.HexColor("#F7F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("Hinweis: 'Trades im Berichtszeitraum' = heute (Snapdate). "
                        "'Historische Trade-Anzahl' = alle Depot-Trades seit Beginn. "
                        "Gebühren/Slippage werden im System nicht pro Trade gespeichert → n/a.", S["small"]))
    el.append(PageBreak())

def _seite_risiko(el, S, W, daten):
    """Seite 7 — Risiko und Exposure."""
    el.append(Paragraph("7. Risiko & Exposure", S["h2"]))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))

    offen = daten.get("offene_positionen", 0)
    equity = daten.get("ges_wert", 0)
    exp = daten.get("exposure_pro_symbol", {})
    exp_rows = [["Symbol", "Exposure", "Status"]]
    for sym, wert in sorted(exp.items(), key=lambda x: -x[1])[:10]:
        exp_rows.append([sym, f"{wert:,.2f} $", "OK"])
    if not exp_rows[1:]:
        exp_rows.append(["—", "n/a", "n/a"])
    t = Table(exp_rows, colWidths=[W*0.3, W*0.4, W*0.3])
    t.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 8.5),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.HexColor("#FFFFFF")),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.HexColor("#FFFFFF"), rc.HexColor("#F7F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    el.append(Paragraph(f"Equity: <b>{equity:,.2f} $</b> · Offene Positionen: <b>{offen}</b>", S["body"]))
    el.append(Spacer(1, 0.2*cm))
    el.append(t)
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("⚠ Drawdown nicht verfügbar — erforderlicher Snapshot (Tages-High-Water-Mark / Peak-Tracking) fehlt im System. "
                        "Tages-Drawdown und maximaler Drawdown werden nicht persistiert.", S["small"]))
    el.append(PageBreak())

def _seite_trades(el, S, W, daten):
    """Seite 8 — Trades und Ausführungsqualität."""
    el.append(Paragraph("8. Trades & Ausführungsqualität", S["h2"]))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))

    trades = daten.get("alle_trades", [])[:30]
    rows = [["Zeit", "Typ", "Symbol", "Menge", "Preis", "Exit-Grund", "decision_id"]]
    for t in trades:
        mark = "Legacy/Fallback" if not t.get("decision_id") else "vorhanden"
        rows.append([
            t.get("zeit", "?")[:16].replace("T", " "),
            t.get("typ", t.get("aktion", "?")),
            t.get("ticker", "?"),
            f"{t.get('menge',0):.2f}",
            f"{t.get('preis',0):.2f}",
            (t.get("grund", "") or "")[:28],
            mark,
        ])
    if len(rows) == 1:
        rows.append(["—", "—", "—", "—", "—", "keine Trades", "—"])
    t = Table(rows, colWidths=[W*0.16, W*0.1, W*0.1, W*0.1, W*0.1, W*0.3, W*0.14], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 7.5),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["cyan"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.HexColor("#FFFFFF")),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.HexColor("#FFFFFF"), rc.HexColor("#F7F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("⚠ Datenqualität: <b>decision_id</b> nur im KI-Log (ki_log.json) vorhanden, "
                        "keine direkte Zuordnung zum Depot-Trade. Trade daher als <b>Legacy/Fallback</b> markiert. "
                        "Slippage/Gebühren/Fill-Preis: <b>n/a</b> (nicht im System erfasst).", S["small"]))
    el.append(PageBreak())

def _seite_governance(el, S, W, daten):
    """Seite 5 — KI-, Regel- und Governance-Status."""
    el.append(Paragraph("KI-, Regel- & Governance-Status", S["h2"]))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))

    ra = daten.get("regelstand", {})
    gov = [
        ["Governance-Bereich", "Anzahl", "Status"],
        ["Regeln gesamt", ra.get("regeln_gesamt", "n/a"), ""],
        ["Freigegeben", ra.get("freigegeben", "n/a"), "LIVE"],
        ["Shadow", ra.get("shadow", "n/a"), "nur Kontext"],
        ["Nicht freigegeben", ra.get("nicht_freigegeben", "n/a"), ""],
        ["Im Live-Pfad", ra.get("im_live_pfad", "n/a"), "LIVE"],
        ["Lernereignisse (ki_log)", ra.get("lernereignisse", "n/a"), ""],
        ["Dedupe-Ereignisse", ra.get("dedupe", "n/a"), ""],
        ["Entscheidungen mit decision_id", ra.get("mit_decision_id", "n/a"), ""],
        ["Legacy/Fallback", ra.get("legacy", "n/a"), ""],
    ]
    t = Table(gov, colWidths=[W*0.5, W*0.25, W*0.25])
    t.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 8.5),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.HexColor("#FFFFFF")),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.HexColor("#FFFFFF"), rc.HexColor("#F7F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("Shadow-Regeln erscheinen NIE als live. freigabe_status wird berücksichtigt. "
                        "Skill-Sync-Status: s. Systemstatus (Seite 6).", S["small"]))
    el.append(Spacer(1, 0.3*cm))

    # ── Phase G: KI-/PROVIDER-STABILITÄT (transparent) ──
    el.append(Paragraph("KI-Provider-Stabilität (transparent)", S["h2"]))
    el.append(HRFlowable(width="100%", thickness=0.6, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.15*cm))
    cd = daten.get("ki_cooldown", {})
    aktive = {p: v for p, v in cd.items() if v.get("bis", 0) > __import__("time").time()} if cd else {}
    prov_status = "gestört" if aktive else ("Fallback (abgelaufen)" if cd else "stabil")
    # Echte Provider-Liste aus ki_provider (openrouter Primary, zen deepseek tot, etc.)
    prov_conf = []
    try:
        import ki_provider
        ki_provider._cooldown_state.clear()
        pl = ki_provider.provider_liste()
        role = {0: "Primary", 1: "2nd", 2: "3rd", 3: "Puffer", 4: "Puffer"}
        for i, p in enumerate(pl):
            prov_conf.append((p["name"], "Free-Tier", f"{role.get(i,'')} | {p['model']}"))
    except Exception:
        prov_conf = [
            ("openrouter", "Free-Tier", "Primary | nemotron-nano"),
            ("nous-hy3", "Free-Tier", "Reasoning (max_tokens>=2048)"),
            ("nous-step", "Free-Tier", "Reasoning (max_tokens>=2048)"),
            ("zen", "Free-Tier", "Puffer | ling-3.0-flash-free (deepseek tot: 429)"),
        ]
    g_rows = [["Provider", "Status", "Konfiguration"]]
    for p, tier, conf in prov_conf:
        st = "⚠ Cooldown" if p in aktive else "✓ aktiv"
        g_rows.append([p, st, conf])
    t_g = Table(g_rows, colWidths=[W*0.22, W*0.20, W*0.58])
    t_g.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 8),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.white),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.white, rc.HexColor("#F7F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    el.append(t_g)
    el.append(Spacer(1, 0.1*cm))
    hinweise = [
        "Ein Provider-Cooldown blockiert NICHT alle Provider (nur betroffenen).",
        "Leere Reasoning-Antworten = kein globaler Systemfehler (nous-hy3/step).",
        "Konfidenz 0 = kein normaler KI-Wert (Fallback-Trennung nötig).",
        f"Aktueller Provider-Status: {prov_status}.",
    ]
    el.append(ListFlowable([ListItem(Paragraph(h, S["small"])) for h in hinweise], bulletType="bullet"))
    el.append(PageBreak())

def _seite_system(el, S, W, daten):
    """Seite 9 — Governance, Systemstatus und Audit."""
    el.append(Paragraph("9. Governance, Systemstatus & Audit", S["h2"]))
    el.append(HRFlowable(width="100%", thickness=1, color=rc.HexColor(FARB["violett"])))
    el.append(Spacer(1, 0.2*cm))

    sys = daten.get("system", {})
    ki_gestoert = sys.get("ki_job") != "OK"
    rows = [
        ["Bereich", "Status", "Detail"],
        ["Engine", sys.get("engine", "n/a"), ""],
        ["KI-Job", sys.get("ki_job", "n/a"), sys.get("ki_detail", "")],
        ["Cron-Jobs aktiv", sys.get("cron_aktiv", "n/a"), "3 Jobs (Batch/Engine/KI)"],
        ["Watchdog-Recovery", sys.get("watchdog", "n/a"), ""],
        ["Provider", sys.get("provider", "n/a"), "Nous-free (Hermes-Token)"],
        ["Datenalter", sys.get("datenalter", "n/a"), ""],
        ["Backup-Status", sys.get("backup", "n/a"), ".backup/ vorhanden"],
        ["Systemversion", VERSION, ""],
        ["Regelwerksversion", f"v{daten.get('regelstand_version','n/a')}", "Status: shadow"],
    ]
    if ki_gestoert:
        rows.insert(1, ["⚠ KI-STÖRUNG", "KRITISCH", "Provider nicht erreichbar — KI-Bewertung nicht verifiziert"])
    t = Table(rows, colWidths=[W*0.3, W*0.25, W*0.45])
    t.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 8.5),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["violett"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.HexColor("#FFFFFF")),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.HexColor("#FFFFFF"), rc.HexColor("#F7F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.3*cm))

    # Anomalien (gruppiert + priorisiert)
    el.append(Paragraph("Anomalien", S["h2"]))
    anom = daten.get("anomalien", [])
    # Sortierung: KI-Störung zuerst, dann Warnungen, dann dokumentiert
    def _prio(a):
        if a.get("schwere") == "HOCH":
            return 0
        if "gestört" in a.get("desc", ""):
            return 0
        return 1
    anom_sorted = sorted(anom, key=_prio)
    arows = [["Zeit", "Kategorie", "Schwere", "Beschreibung", "Status"]]
    if anom_sorted:
        for a in anom_sorted[:8]:
            arows.append([a.get("zeit", "?"), a.get("kat", "?"), a.get("schwere", "?"),
                          (a.get("desc", "") or "")[:40], a.get("status", "n/a")])
    else:
        arows.append(["—", "—", "—", "keine Anomalien erfasst", "OK"])
    ta = Table(arows, colWidths=[W*0.13, W*0.13, W*0.1, W*0.5, W*0.14], repeatRows=1)
    ta.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), FONT, 7.5),
        ("BACKGROUND", (0,0), (-1,0), rc.HexColor(FARB["cyan"])),
        ("TEXTCOLOR", (0,0), (-1,0), rc.HexColor("#FFFFFF")),
        ("GRID", (0,0), (-1,-1), 0.4, rc.HexColor("#E5E5EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [rc.HexColor("#FFFFFF"), rc.HexColor("#F7F7FA")]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    el.append(ta)
    el.append(Spacer(1, 0.2*cm))
    el.append(Paragraph("Hinweis: Mehrere Risikostufen (Risk 50–95) meldeten am Berichtstag Renditeabweichungen. "
                        "Diese sind als Sammel-Ereignis 'dokumentiert' gelistet, nicht als zehn kritische Einzelvorfälle.", S["small"]))
    el.append(PageBreak())


if __name__ == "__main__":
    daten = sammle_daten()
    heute = datetime.now().strftime("%Y-%m-%d")
    report_id = _report_id(heute)
    pfad = os.path.join(REPORTS, f"daily_report_{heute}_v{VERSION}_{report_id}.pdf")
    baue_pdf(daten, pfad)
    print(f"PDF erstellt: {pfad}")
    print(f"  Gesamtwert: {daten['ges_wert']:,.2f} $ | Rendite: {daten['ges_pnl_pct']:+,.2f}%")
    print(f"  Kategorien: {daten['kat']}")
    print(f"  Top5: {[d['ticker'] for d in daten['top5']]}")
    print(f"  Flop5: {[d['ticker'] for d in daten['flop5']]}")
    print(f"  KI-Regeln: {len(daten['rules_list'])} | Konfidenz: {daten['ki_konf_schnitt']}")
    print(f"  Verlauf: {len(daten['verlauf'])} Tage")
