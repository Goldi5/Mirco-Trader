#!/usr/bin/env python3
"""Dashboard - Web-Oberflaeche fuer alle 20 Depots + Charts + News + Spekulation."""
import json, os, sys, time
from datetime import datetime, timedelta, date
import yfinance as yf
from flask import Flask, send_from_directory, request, jsonify, session, redirect, url_for, make_response

# PHASE 4-6 (Server-Sicherheit): zentrale Sicherheitslogik
import security as sec
from security import (
    require_auth, require_role, require_recent_mfa, current_user,
    login_required_redirect,
)

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5200
sys.path.insert(0, BASE)

# ─── Version (für Admin-Regelstand-Anzeige) ─────────────────────
try:
    with open(os.path.join(BASE, "version.json"), encoding="utf-8") as _vf:
        version = json.load(_vf)
except Exception:
    version = {"version": "?"}

# ─── Ticker → Firmenname (aus externer JSON geladen) ──────────
TICKER_NAMES = {}
NAMES_PATH = os.path.join(BASE, "static", "ticker_names.json")
if os.path.exists(NAMES_PATH):
    with open(NAMES_PATH, encoding="utf-8") as f:
        TICKER_NAMES = json.load(f)

# ─── Ticker → Sektor ─────────────────────────────────────────
TICKER_SEKTOR = {}
SEKTOR_PATH = os.path.join(BASE, "static", "ticker_sectors.json")
if os.path.exists(SEKTOR_PATH):
    with open(SEKTOR_PATH) as f:
        TICKER_SEKTOR = json.load(f)

def name_for(ticker):
    """Liefert 'Ticker – Firmenname' oder fallback nur Ticker."""
    if ticker in TICKER_NAMES:
        n = TICKER_NAMES[ticker]
        if "–" in n:  # hat schon Beschreibung
            return n
        # Füge Sektor hinzu falls bekannt
        sektor = TICKER_SEKTOR.get(ticker, "")
        if sektor:
            return f"{n} [{sektor}]"
        return n
    sektor = TICKER_SEKTOR.get(ticker, "")
    if sektor:
        return f"{ticker} [{sektor}]"
    return f"{ticker} – unbekannt"

# ─── Börsenzeiten ───────────────────────────────────────────
BOERSEN = [
    {"name": "NYSE",   "flag": "🇺🇸", "open_et": (9, 30),  "close_et": (16, 0),  "label": "NYSE"},
    {"name": "NASDAQ", "flag": "🇺🇸", "open_et": (9, 30),  "close_et": (16, 0),  "label": "NASDAQ"},
    {"name": "Xetra",  "flag": "🇪🇺", "open_ce": (9, 0),   "close_ce": (17, 30), "label": "Xetra"},
]
BOERSEN_CACHE = None
BOERSEN_CACHE_TIME = 0

def profil_karten():
    """Phase 11 (§18): Profil-/Markt-Karten für Dashboard-Steuerzentrale.

    Zeigt: aktives Profil · aktiver Markt · aktiver Modus · freigegebener Regelstand ·
    Shadow/Live-Badge. Multi-Markt-Ausbau (US/DE/JP Shadow-Profile).
    """
    import profil_schema as ps

    karten = []
    profile = [
        ("us_shadow", "US"),
        ("de_shadow", "DE"),
        ("jp_shadow", "JP"),
    ]
    for name, markt in profile:
        p, fehler, warn = ps.lade_profil(name)
        if not p:
            karten.append({
                "markt": markt,
                "name": name,
                "status": "fehler",
                "modus": "shadow",
                "depotarten": [],
                "warnung": fehler,
            })
            continue
        karten.append({
            "markt": markt,
            "name": p.get("name", name),
            "status": "shadow" if p.get("modus") == "shadow" else "live",
            "modus": p.get("modus", "shadow"),
            "depotarten": p.get("depotarten", []),
            "maerkte": p.get("märkte", []),
            "base_currency": p.get("base_currency", "USD"),
            "regelstand_ref": p.get("regelstand_ref", "unbekannt"),
            "warnung": warn or "",
        })
    return karten


def market_status():
    """Gibt Status pro Börse + Gesamtübersicht zurück."""
    global BOERSEN_CACHE, BOERSEN_CACHE_TIME
    now = time.time()
    if BOERSEN_CACHE and (now - BOERSEN_CACHE_TIME) < 30:
        return BOERSEN_CACHE

    try:
        import pytz
    except:
        pytz = None

    results = []
    overall_open = False
    for b in BOERSEN:
        if "open_et" in b:
            # US-Börse (Eastern Time)
            if pytz:
                tz = pytz.timezone("US/Eastern")
                now_local = datetime.now(tz)
            else:
                utc = datetime.utcnow()
                is_dst = (datetime.now().month in [3,4,5,6,7,8,9,10])  # ≈ März-Okt
                off = 4 if is_dst else 5
                now_local = utc - timedelta(hours=off)
            oh, om = b["open_et"]
            ch, cm = b["close_et"]
            open_t = now_local.replace(hour=oh, minute=om, second=0, microsecond=0)
            close_t = now_local.replace(hour=ch, minute=cm, second=0, microsecond=0)
            # Format times
            if pytz:
                cet = pytz.timezone("CET")
                open_mez = open_t.astimezone(cet).strftime("%H:%M")
                close_mez = close_t.astimezone(cet).strftime("%H:%M")
            else:
                open_mez = f"{oh+6:02d}:{om:02d}"  # grob ET→MEZ +6h
                close_mez = f"{ch+6:02d}:{cm:02d}"
            open_local = f"{oh:02d}:{om:02d}"
            close_local = f"{ch:02d}:{cm:02d}"
        else:
            # Xetra (Europe/Berlin)
            tz_name = "Europe/Berlin"
            if pytz:
                tz = pytz.timezone(tz_name)
                now_local = datetime.now(tz)
            else:
                now_local = datetime.now()
            oh, om = b["open_ce"]
            ch, cm = b["close_ce"]
            open_t = now_local.replace(hour=oh, minute=om, second=0, microsecond=0)
            close_t = now_local.replace(hour=ch, minute=cm, second=0, microsecond=0)
            open_local = f"{oh:02d}:{om:02d}"
            close_local = f"{ch:02d}:{cm:02d}"
            open_mez = open_local
            close_mez = close_local

        # Status ermitteln
        if now_local.weekday() >= 5:
            status = "closed"
            label = "Geschlossen (WE)"
        elif now_local < open_t:
            status = "pre"
            min_bis = (open_t - now_local).seconds // 60
            label = f"Öffnet {open_local} ({min_bis} Min)"
        elif now_local < close_t:
            status = "open"
            min_bis_schluss = (close_t - now_local).seconds // 60
            label = f"Offen bis {close_local} ({min_bis_schluss} Min)"
        else:
            status = "closed"
            morgen = now_local.replace(hour=oh, minute=om, second=0, microsecond=0)
            morgen += timedelta(days=1)
            if morgen.weekday() >= 5:
                morgen += timedelta(days=7 - morgen.weekday())
            label = f"Schließt {close_local}"

        # Nächste Öffnung berechnen (für "Wieder offen am ...")
        next_open = now_local.replace(hour=oh, minute=om, second=0, microsecond=0)
        if status == "open" or status == "pre":
            next_open = next_open  # heute schon offen/vor Öffnung
        else:
            next_open += timedelta(days=1)
            if next_open.weekday() >= 5:
                next_open += timedelta(days=7 - next_open.weekday())
        next_open_str = next_open.strftime("%a %d.%m. %H:%M")

        if status == "open":
            overall_open = True

        results.append({
            "name": b["name"],
            "flag": b["flag"],
            "status": status,
            "open": open_mez,
            "close": close_mez,
            "open_local": open_local,
            "close_local": close_local,
            "label": label,
            "next_open": next_open_str,
        })

    # Gesamt-Status
    any_open = any(r["status"] == "open" for r in results)
    any_pre = any(r["status"] == "pre" for r in results)
    # Nächste Öffnung (früheste aller Börsen)
    next_open_overall = None
    for r in results:
        if r["status"] != "open":
            try:
                from datetime import datetime as _dt
                no = _dt.strptime(r["next_open"], "%a %d.%m. %H:%M")
                if next_open_overall is None or no < next_open_overall:
                    next_open_overall = no
            except Exception:
                pass
    next_open_str = next_open_overall.strftime("%a %d.%m. %H:%M") if next_open_overall else "?"

    if any_open:
        ges_status = "open"
        ges_label = "🟢 Börsen geöffnet"
    elif any_pre:
        ges_status = "pre"
        ges_label = "🟡 Voröffnung"
    else:
        ges_status = "closed"
        ges_label = f"🔴 Geschlossen · nächste Öffnung: {next_open_str}"

    out = (ges_status, ges_label, results)
    BOERSEN_CACHE = out
    BOERSEN_CACHE_TIME = time.time()
    return out


def portfolio_verlauf(tage=7):
    """Aggregiert depot_*/etf_*/spec_depots historie zu 4 Serien (gesamt/aktien/etf/spec).

    Forward-fill: jedes Depot traegt seinen letzten bekannten Wert <= Zeitpunkt bei,
    damit die Summe pro Zeitpunkt alle Depots enthaelt (keine Luecken durch
    unterschiedliche Speicher-Intervalle). Rendite gegen Startkapital (start_wert/start).
    """
    cutoff = datetime.now() - timedelta(days=tage)

    # Pro Kategorie: liste von (zeit, wert) pro Depot
    kategorien = {"aktien": [], "etf": [], "spec": []}

    def _depot_historie(f, kat, wert_feld="wert"):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            return
        pts = []
        for h in d.get("historie", []):
            try:
                z = datetime.fromisoformat(h["zeit"])
            except Exception:
                continue
            if z < cutoff:
                continue
            w = float(h.get(wert_feld, 0) or 0)
            pts.append((z, w))
        if pts:
            kategorien[kat].append(pts)

    for risk in RISK_STUFEN:
        _depot_historie(depot_pfad(risk), "aktien")
    for risk in range(0, 100, 5):
        _depot_historie(os.path.join(BASE, f"etf_{risk:03d}.json"), "etf")
    sdd = os.path.join(BASE, "spec_depots")
    if os.path.isdir(sdd):
        for fn in os.listdir(sdd):
            if fn.endswith(".json"):
                _depot_historie(os.path.join(sdd, fn), "spec")

    # Alle Zeitpunkte (minutengenau) ueber alle Depots
    alle = set()
    for kat in kategorien.values():
        for pts in kat:
            for z, _w in pts:
                alle.add(z.replace(second=0, microsecond=0))
    alle = sorted(alle)

    def _serie(kat_pts):
        # forward-fill: pro Zeitpunkt summiere letzten bekannten Wert jedes Depots
        idx = [0] * len(kat_pts)
        out = []
        for z in alle:
            ssum = 0.0
            for i, pts in enumerate(kat_pts):
                while idx[i] + 1 < len(pts) and pts[idx[i] + 1][0] <= z:
                    idx[i] += 1
                if pts[idx[i]][0] <= z:
                    ssum += pts[idx[i]][1]
            out.append({"zeit": z.strftime("%Y-%m-%d %H:%M"), "wert": round(ssum, 2)})
        return out

    serien = {
        "aktien": _serie(kategorien["aktien"]),
        "etf": _serie(kategorien["etf"]),
        "spec": _serie(kategorien["spec"]),
    }
    # Gesamt = summe der 3 Serien pro Zeitpunkt
    ges = []
    for i, z in enumerate(alle):
        w = (serien["aktien"][i]["wert"] if i < len(serien["aktien"]) else 0) + \
            (serien["etf"][i]["wert"] if i < len(serien["etf"]) else 0) + \
            (serien["spec"][i]["wert"] if i < len(serien["spec"]) else 0)
        ges.append({"zeit": z.strftime("%Y-%m-%d %H:%M"), "wert": round(w, 2)})

    # Startkapital
    def _start_summe(kat):
        total = 0.0
        try:
            if kat == "aktien":
                for risk in RISK_STUFEN:
                    fp = depot_pfad(risk)
                    if os.path.exists(fp):
                        with open(fp, encoding="utf-8") as fh:
                            d = json.load(fh)
                            total += float(d.get("start_wert") or d.get("start") or 0)
            elif kat == "etf":
                for risk in range(0, 100, 5):
                    fp = os.path.join(BASE, f"etf_{risk:03d}.json")
                    if os.path.exists(fp):
                        with open(fp, encoding="utf-8") as fh:
                            d = json.load(fh)
                            total += float(d.get("start_wert") or d.get("start") or 0)
            elif kat == "spec":
                sdd = os.path.join(BASE, "spec_depots")
                if os.path.isdir(sdd):
                    for fn in os.listdir(sdd):
                        if fn.endswith(".json"):
                            with open(os.path.join(sdd, fn), encoding="utf-8") as fh:
                                total += float(json.load(fh).get("start") or 0)
        except Exception:
            pass
        return total

    starts = {"gesamt": 0, "aktien": 0, "etf": 0, "spec": 0}
    starts["aktien"] = _start_summe("aktien")
    starts["etf"] = _start_summe("etf")
    starts["spec"] = _start_summe("spec")
    starts["gesamt"] = starts["aktien"] + starts["etf"] + starts["spec"]

    def _mit_rendite(pts, basis):
        for pt in pts:
            pt["rendite"] = round((pt["wert"] / basis - 1) * 100, 2) if basis else 0.0
        return pts

    return {
        "gesamt": _mit_rendite(ges, starts["gesamt"]),
        "aktien": _mit_rendite(serien["aktien"], starts["aktien"]),
        "etf": _mit_rendite(serien["etf"], starts["etf"]),
        "spec": _mit_rendite(serien["spec"], starts["spec"]),
        "start_gesamt": round(starts["gesamt"], 2),
        "start_aktien": round(starts["aktien"], 2),
        "start_etf": round(starts["etf"], 2),
        "start_spec": round(starts["spec"], 2),
    }



def kategorie_trade_historie(kat, limit=50):
    """Sammelt alle Trades einer Kategorie (aktien/etf/spec) aus den Depot-JSONs.

    Liefert Liste von {zeit, depot_label, typ, ticker, menge, preis, grund}
    sortiert nach Zeit absteigend (neueste zuerst).
    """
    trades = []
    try:
        if kat == "aktien":
            for risk in RISK_STUFEN:
                fp = depot_pfad(risk)
                if not os.path.exists(fp):
                    continue
                with open(fp, encoding="utf-8") as fh:
                    d = json.load(fh)
                label = f"Risk {risk}"
                for t in d.get("trades", []):
                    t2 = dict(t)
                    t2["depot_label"] = label
                    t2["kategorie"] = "aktien"
                    trades.append(t2)
        elif kat == "etf":
            for risk in range(0, 100, 5):
                fp = os.path.join(BASE, f"etf_{risk:03d}.json")
                if not os.path.exists(fp):
                    continue
                with open(fp, encoding="utf-8") as fh:
                    d = json.load(fh)
                stufe = d.get("stufe") or f"Risk {risk}"
                for t in d.get("trades", []):
                    t2 = dict(t)
                    t2["depot_label"] = stufe
                    t2["kategorie"] = "etf"
                    trades.append(t2)
        elif kat == "spec":
            sdd = os.path.join(BASE, "spec_depots")
            if os.path.isdir(sdd):
                for fn in os.listdir(sdd):
                    if not fn.endswith(".json"):
                        continue
                    with open(os.path.join(sdd, fn), encoding="utf-8") as fh:
                        d = json.load(fh)
                    for t in d.get("trades", []):
                        t2 = dict(t)
                        t2["depot_label"] = d.get("ticker", fn.replace(".json", ""))
                        t2["kategorie"] = "spec"
                        # Spec nutzt 'aktion' statt 'typ'
                        t2.setdefault("typ", t2.get("aktion"))
                        trades.append(t2)
    except Exception:
        pass
    # Neueste zuerst sortieren (Zeit als String vergleichbar bei ISO)
    trades.sort(key=lambda t: str(t.get("zeit", "")), reverse=True)
    return trades[:limit]


def boersen_chips():
    """Sammelt die BÖRSEN, DIE IM PORTFOLIO WIRKLICH VORKOMMEN + Wert-Anteil.

    Nutzt die 'exchanges'-Felder der Depots (von engine.py geschrieben) bzw.
    berechnet die Börse aus dem Ticker-Suffix via boersen.boerse_fuer_ticker.
    Zeigt NUR Börsen mit echten Positionen → kein Chip, wenn kein Titel dort.
    Crypto (kein klass. Handelsplatz) → '24/7' als eigener Chip.
    """
    from boersen import boerse_fuer_ticker, BOERSEN, ist_offen, status_mit_next_open

    # 1) Alle gehaltenen Ticker + ihre Börsen + ihre Werte sammeln
    boersen_werte = {}   # boerse -> summe werte
    gesamt = 0.0

    def _add(ticker, wert):
        nonlocal gesamt
        if wert <= 0:
            return
        gesamt += wert
        # Crypto? (aus spec_watch kategorie)
        b = boerse_fuer_ticker(ticker)
        # Crypto erkennen wir an bekannten Suffixen/Symbolen
        if ticker in ("BTC", "ETH", "SOL", "DOGE", "ADA", "XRP", "LTC", "BNB", "AVAX", "MATIC", "DOT", "LINK", "UNI", "ATOM"):
            b = "CRYPTO"
        boersen_werte[b] = boersen_werte.get(b, 0.0) + wert

    # Aktien-Depots ( haben 'exchanges'-Feld, sonst Ticker-Suffix )
    for risk in RISK_STUFEN:
        dp = depot_pfad(risk)
        if os.path.exists(dp):
            with open(dp) as f:
                d = json.load(f)
            ex = d.get("exchanges", {})
            for t, pos in d.get("positions", {}).items():
                shares = pos.get("shares", 0)
                if shares > 0:
                    kurs = pos.get("avg_price", 0)
                    w = shares * kurs
                    b = ex.get(t) or boerse_fuer_ticker(t)
                    if b == "US":
                        b = "NYSE/NASDAQ"
                    _add(t, w)

    # ETF-Depots
    for risk in range(0, 100, 5):
        ep = os.path.join(BASE, f"etf_{risk:03d}.json")
        if os.path.exists(ep):
            with open(ep) as f:
                d = json.load(f)
            for t, pos in d.get("positions", {}).items():
                shares = pos.get("shares", 0)
                if shares > 0:
                    kurs = pos.get("avg_price", 0)
                    _add(t, shares * kurs)

    # Spec-Depots
    sdd = os.path.join(BASE, "spec_depots")
    if os.path.isdir(sdd):
        for fn in os.listdir(sdd):
            if fn.endswith(".json"):
                with open(os.path.join(sdd, fn)) as f:
                    d = json.load(f)
                if d.get("shares", 0) > 0:
                    _add(d.get("ticker", ""), d.get("shares", 0) * d.get("avg_price", 0))

    # 2) Chips bauen (nur Börsen mit Wert > 0)
    chips = []
    for b, wert in sorted(boersen_werte.items(), key=lambda x: -x[1]):
        if wert <= 0:
            continue
        anteil = round(wert / gesamt * 100) if gesamt > 0 else 0
        if b == "CRYPTO":
            chips.append({"boerse": "CRYPTO", "label": "🪙 Crypto", "anteil": anteil,
                          "status": "open", "offen_text": "24/7", "next_open": "-"})
        else:
            offen = ist_offen(b) if b in BOERSEN else False
            label = BOERSEN.get(b, {}).get("label", b)
            kurz = label.split(" ", 1)[-1] if " " in label else label
            # Naechste Oeffnung aus boersen.status_mit_next_open()
            next_open_str = "-"
            try:
                for st in status_mit_next_open():
                    if st["boerse"] == b:
                        next_open_str = st["next_open"]
                        break
            except Exception:
                pass
            chips.append({"boerse": b, "label": kurz, "anteil": anteil,
                          "status": "open" if offen else "closed",
                          "offen_text": "geöffnet" if offen else "geschlossen",
                          "next_open": next_open_str})
    return chips

# ─── SPX Benchmark ───────────────────────────────────────────
SPX_CACHE = None
SPX_CACHE_TIME = 0

def get_spx_data():
    """Holt SPX Schlusskurse der letzten 60 Tage."""
    global SPX_CACHE, SPX_CACHE_TIME
    now = time.time()
    if SPX_CACHE and (now - SPX_CACHE_TIME) < 3600:
        return SPX_CACHE
    try:
        spx = yf.download("^GSPC", period="2mo", interval="1d", progress=False, auto_adjust=True)
        if spx.empty:
            spx = yf.download("SPY", period="2mo", interval="1d", progress=False, auto_adjust=True)
            if spx.empty:
                return []
        # Handle MultiIndex columns
        if hasattr(spx.columns, 'nlevels') and spx.columns.nlevels > 1:
            close = spx['Close'].iloc[:, 0]  # erste (einzige) Spalte unter Close
        elif 'Close' in spx:
            close = spx['Close']
        else:
            return []
        close = close.dropna()
        data = []
        for d, v in close.items():
            # d kann Datum oder Tupel sein (MultiIndex row)
            if isinstance(d, tuple):
                d = d[0]
            iso = d.isoformat() if hasattr(d, 'isoformat') else str(d)
            data.append({"zeit": iso, "wert": round(float(v), 2)})
        SPX_CACHE = data
        SPX_CACHE_TIME = now
        return data
    except Exception as e:
        return []

# ─── Notifications ───────────────────────────────────────────
NOTIF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notifications.json")

def check_notifications(depots):
    """Prüft Alarme: Drawdown, Top-Performer, etc. Schreibt in JSON."""
    notifs = []
    for dep in depots:
        if dep.get("max_dd", 0) > 15:
            notifs.append({
                "typ": "warn",
                "text": f"Risk {dep['risk']}: MaxDD {dep['max_dd']}%",
                "zeit": datetime.now().isoformat(),
            })
        if dep.get("rendite", 0) > 5:
            notifs.append({
                "typ": "good",
                "text": f"Risk {dep['risk']}: +{dep['rendite']}% Rendite",
                "zeit": datetime.now().isoformat(),
            })
    # Gesamt-Drawdown check
    ges_wert = sum(d["wert"] for d in depots)
    ges_start = sum(d["start"] for d in depots)
    ges_rendite = round((ges_wert / ges_start - 1) * 100, 2) if ges_start > 0 else 0.0

    # Also compute inside check_notifications for backwards compat
    if ges_wert < ges_start * 0.85:
        notifs.append({
            "typ": "alert",
            "text": f"Gesamt-Wert -{((1-ges_wert/ges_start)*100):.1f}% unter 85%",
            "zeit": datetime.now().isoformat(),
        })
    # Nur letzte 50 halten
    if os.path.exists(NOTIF_FILE):
        try:
            with open(NOTIF_FILE) as f:
                old = json.load(f)
            notifs = old[-40:] + notifs
        except:
            pass
    notifs = notifs[-50:]
    with open(NOTIF_FILE, "w") as f:
        json.dump(notifs, f, indent=2)
    return notifs[-10:]

app = Flask(__name__, static_folder=os.path.join(BASE, "assets"), static_url_path="/assets")

# Explizite Asset-Route (robust, vor allen anderen)
@app.route("/assets/<path:dateiname>")
def serve_assets(dateiname):
    pfad = os.path.join(BASE, "assets", dateiname)
    if os.path.exists(pfad):
        from flask import send_file
        return send_file(pfad)
    return ("Not Found", 404)

from risk_profile import RISK_STUFEN, get_params
def depot_pfad(risk):
    return os.path.join(BASE, "depot_%03d.json" % risk)


def regelstand_aggregat(ki_regeln):
    """Block 6: Aggregiert den Regelstand für Dashboard-Anzeige.

    Liefert: anzahl_gesamt, freigegeben, shadow, archiviert, aktiv,
    letzter_sync (regelstand_version der neuesten Regel), oos_bestätigt.
    """
    ges = len(ki_regeln)
    freigegeben = sum(1 for r in ki_regeln
                      if str(r.get("freigabe_status", "")) == "freigegeben")
    shadow = sum(1 for r in ki_regeln if r.get("shadow"))
    archiviert = sum(1 for r in ki_regeln if r.get("archiviert"))
    aktiv = sum(1 for r in ki_regeln if str(r.get("status", "")).lower()
                not in ("veraltet", "expired", "inaktiv"))
    oos = sum(1 for r in ki_regeln if r.get("oos_confirmed"))
    # letzter Sync: neueste last_validated_version / created_at
    letzter = ""
    for r in ki_regeln:
        lv = str(r.get("last_validated_version") or r.get("updated_at")
                 or r.get("created_at") or "")
        if lv > letzter:
            letzter = lv
    return {
        "anzahl_gesamt": ges,
        "freigegeben": freigegeben,
        "shadow": shadow,
        "archiviert": archiviert,
        "aktiv": aktiv,
        "oos_bestätigt": oos,
        "letzter_sync": letzter[:19].replace("T", " ") if letzter else "—",
    }


@app.route("/dashboard")
def index():
    return send_from_directory(BASE, "dashboard.html")


@app.route("/data")
def data():
    # ── Cache: nur alle 60s neu berechnen (yfinance entlasten) ──
    now = time.time()
    if hasattr(data, "_cache") and data._cache and (now - data._cache_ts) < 60:
        return data._cache

    depots = []
    ALLE_TICKER = set()
    depot_raw = {}
    for risk in RISK_STUFEN:
        dp = depot_pfad(risk)
        if os.path.exists(dp):
            with open(dp) as f:
                d = json.load(f)
            depot_raw[risk] = d
            for s, pos_obj in d.get("positions", {}).items():
                if pos_obj.get("shares", 0) > 0:
                    ALLE_TICKER.add(s)
    # Auch ETF- und Spekulation-Positionen einsammeln (nur offene: shares > 0)
    for risk in range(0, 100, 5):
        ep = os.path.join(BASE, f"etf_{risk:03d}.json")
        if os.path.exists(ep):
            with open(ep) as f:
                d = json.load(f)
            for s, pos_obj in d.get("positions", {}).items():
                if pos_obj.get("shares", 0) > 0:
                    ALLE_TICKER.add(s)
    sdd = os.path.join(BASE, "spec_depots")
    if os.path.isdir(sdd):
        for fn in os.listdir(sdd):
            if fn.endswith(".json"):
                with open(os.path.join(sdd, fn)) as f:
                    sd = json.load(f)
                # spec_depots haben ticker + shares auf root-level
                if sd.get("ticker") and sd.get("shares", 0) > 0:
                    ALLE_TICKER.add(sd["ticker"])

    # yfinance NUR wenn es offene Positionen gibt (sonst überspringen = schnell)
    kurse = {}
    if ALLE_TICKER:
        try:
            _data = yf.download(list(ALLE_TICKER), period="1d", progress=False, auto_adjust=True, timeout=10)
            if not _data.empty:
                if 'Close' in _data:
                    close = _data['Close']
                    for col in close.columns:
                        vals = close[col].dropna()
                        if len(vals) > 0:
                            kurse[str(col)] = float(vals.iloc[-1])
        except Exception:
            pass  # Netz-Probleme -> avg_price aus Depot nutzen

    for risk in RISK_STUFEN:
        d = depot_raw.get(risk)
        if d is None:
            continue
        p = get_params(risk)
        wert = d.get("bargeld", 0)
        for s, pos_obj in d.get("positions", {}).items():
            aktuell = kurse.get(s)
            if aktuell is None or aktuell <= 0:
                aktuell = pos_obj.get("avg_price", 0)
            wert += pos_obj["shares"] * aktuell
        rendite = (wert / d.get("start_wert", 100) - 1) * 100 if d.get("start_wert", 0) > 0 else 0

        # Stats aus Historie
        hist = d.get("historie", [])
        max_dd = 0
        if hist:
            peak = hist[0]["wert"]
            for h in hist:
                if h["wert"] > peak:
                    peak = h["wert"]
                dd = (peak - h["wert"]) / peak * 100
                if dd > max_dd:
                    max_dd = dd

        depots.append({
            "risk": risk,
            "wert": round(wert, 2),
            "cash": round(d.get("bargeld", 0), 2),
            "start": d.get("start_wert") or 100,
            "rendite": round(rendite, 2),
            "positionen": len(d.get("positions", {})),
            "trades": len(d.get("trades", [])),
            "historie": hist,
            "max_dd": round(max_dd, 1),
            "gesperrt": d.get("gesperrt", False),
            "peak_wert": d.get("peak_wert", d.get("start_wert", 100)),
            "positions": [{"ticker": t, "name": name_for(t), **v} for t, v in d.get("positions", {}).items()],
            "ki_letzte": d.get("ki_letzte"),
            "params": {"position_size": p["position_size"], "stop_loss": p["stop_loss"],
                       "take_profit": p["take_profit"], "min_score": p["min_score"],
                       "max_positions": p["max_positions"]},
        })

    # News
    news = []
    np = os.path.join(BASE, "news_cache.json")
    if os.path.exists(np):
        with open(np) as f:
            nc = json.load(f)
            news = nc.get("headlines", [])

    # ── KI-Log aus ki_log.json laden ──
    KI_LOG = []
    kip = os.path.join(BASE, "ki_log.json")
    if os.path.exists(kip):
        try:
            with open(kip, encoding="utf-8") as f:
                KI_LOG = json.load(f)
            if not isinstance(KI_LOG, list):
                KI_LOG = []
        except:
            KI_LOG = []

    # ── Trader-Status laden ──
    trader_status = {}
    tsp = os.path.join(BASE, "trader_status.json")
    if os.path.exists(tsp):
        try:
            with open(tsp, encoding="utf-8") as f:
                trader_status = json.load(f)
            if not isinstance(trader_status, dict):
                trader_status = {}
        except Exception:
            trader_status = {}

    # ── System-Log laden (neueste zuerst) ──
    SYSTEM_LOG = []
    slp = os.path.join(BASE, "system_log.json")
    if os.path.exists(slp):
        try:
            with open(slp, encoding="utf-8") as f:
                sl = json.load(f)
            if isinstance(sl, list):
                SYSTEM_LOG = sl[-200:][::-1]
        except Exception:
            SYSTEM_LOG = []

    # ── KI-Lern-Statistik + Regeln ──
    ki_statistik = {"anzahl": 0, "trefferquote": None, "lerneffekt_avg": None,
                    "bestaetigt": 0, "widerlegt": 0, "neutral": 0}
    ki_regeln = []
    ki_regel_familien = []
    regel_history = []
    regel_konflikte = []
    konfidenz_cap = None
    try:
        from ki_learning import statistik, lade_regeln, regel_familien_statistik, konfidenz_cap_aktuell
        ki_statistik = statistik()
        ki_regeln = lade_regeln()
        ki_regel_familien = regel_familien_statistik()
        konfidenz_cap = konfidenz_cap_aktuell()
        # P5: Regel-Evolution laden
        hp = os.path.join(BASE, "regel_history.json")
        if os.path.exists(hp):
            with open(hp, encoding="utf-8") as hf:
                regel_history = json.load(hf)
        # Prio 2: Lebenszyklus + Konflikte
        try:
            from learned_rules import regeln_mit_status
            ki_regeln, regel_konflikte = regeln_mit_status(ki_regeln)
        except Exception:
            pass
    except Exception:
        pass

    # Fallback: Regelwerk wenn keine Datei da
    if 'KI_LOG' not in dir() or not isinstance(KI_LOG, list):
        KI_LOG = []
    if not KI_LOG and news:
        for n in news:
            score = 50
            if n.get("date"):
                try:
                    parsed = datetime.strptime(n["date"].replace("GMT","").strip(), "%a, %d %b %Y %H:%M:%S ")
                    alter = (now - parsed).total_seconds() / 3600
                    if alter < 2:       score += 30
                    elif alter < 6:     score += 20
                    elif alter < 24:    score += 10
                except:
                    pass
            topics = n.get("topics", [])
            weight = {"market":15, "earnings":15, "tech":12, "interest rate":12, "inflation":10,
                      "energy":8, "merger":8, "regulation":6, "geopolitics":6, "crypto":6, "":0}
            for t in topics:
                score += weight.get(t.lower(), 4)
            score = min(score, 100)
            stars = "⭐⭐⭐" if score >= 70 else "⭐⭐" if score >= 45 else "⭐" if score >= 20 else ""
            KI_LOG.append({
                "zeit": now.isoformat(),
                "title": n.get("title",""),
                "score": score,
                "stars": stars,
                "topics": topics,
                "tickers": [],
                "reason": "Regelwerk (keine KI)",
                "link": n.get("link",""),
            })


    # ── Market Status ──

    # KI-Log speichern (nur wenn Fallback berechnet wurde)
    if KI_LOG and not os.path.exists(kip):
        KI_LOG = KI_LOG[-200:]
        with open(kip, "w", encoding="utf-8") as f:
            json.dump(KI_LOG, f, indent=2, ensure_ascii=False)

    # Zusammenfassung
    summary = {}
    sp = os.path.join(BASE, "batch_summary.json")
    if os.path.exists(sp):
        with open(sp) as f:
            summary = json.load(f)

    # Spekulation-Watch
    spec_watch = {}
    swp = os.path.join(BASE, "spec_watch.json")
    if os.path.exists(swp):
        with open(swp) as f:
            spec_watch = json.load(f)

    # Spekulation-Depots
    spec_depots = []
    sdd = os.path.join(BASE, "spec_depots")
    if os.path.isdir(sdd):
        for fn in sorted(os.listdir(sdd)):
            if fn.endswith(".json"):
                with open(os.path.join(sdd, fn)) as f:
                    sd = json.load(f)
                # Nur echte Depots (gestartet/gehandelt) zählen – Platzhalter ohne
                # Startkapital gehören in die Watchlist, nicht ins Portfolio
                if not (sd.get("start") or sd.get("shares") or sd.get("trades")):
                    continue
                spec_depots.append({
                    "ticker": sd.get("ticker", fn.replace(".json","")),
                    "name": sd.get("name", ""),
                    "kategorie": sd.get("kategorie", ""),
                    "wert": sd.get("bargeld", 0) + sd.get("shares", 0) * sd.get("avg_price", 0),
                    "bargeld": sd.get("bargeld", 0),
                    "shares": sd.get("shares", 0),
                    "avg_price": sd.get("avg_price", 0),
                    "start": sd.get("start") or 0,
                    "trades": len(sd.get("trades", [])),
                    "historie": sd.get("historie", []),
                    "ki_letzte": sd.get("ki_letzte"),
                })
    
    # ETF-Depots
    etf_depots = []
    for risk in range(0, 100, 5):
        ep = os.path.join(BASE, f"etf_{risk:03d}.json")
        if os.path.exists(ep):
            with open(ep) as f:
                d = json.load(f)
            wert = d.get("bargeld", 0)
            for s, pos_obj in d.get("positions", {}).items():
                aktuell = kurse.get(s)
                if aktuell is None or aktuell <= 0:
                    aktuell = pos_obj.get("avg_price", 0)
                wert += pos_obj["shares"] * aktuell
            rendite = (wert / d.get("start_wert", 100) - 1) * 100 if d.get("start_wert", 0) > 0 else 0
            hist = d.get("historie", [])
            max_dd = 0
            if hist:
                peak = hist[0]["wert"]
                for h in hist:
                    if h["wert"] > peak: peak = h["wert"]
                    dd = (peak - h["wert"]) / peak * 100
                    if dd > max_dd: max_dd = dd
            etf_depots.append({
                "risk": risk,
                "wert": round(wert, 2),
                "cash": round(d.get("bargeld", 0), 2),
                "start": d.get("start_wert") or 100,
                "rendite": round(rendite, 2),
                "positionen": len(d.get("positions", {})),
                "trades": len(d.get("trades", [])),
                "historie": hist[-50:],
                "max_dd": round(max_dd, 1),
                "gesperrt": d.get("gesperrt", False),
                "positions": [{"ticker": t, **v} for t, v in d.get("positions", {}).items()],
            })

    # ETF-Summary
    etf_summary = {}
    esp = os.path.join(BASE, "etf_summary.json")
    if os.path.exists(esp):
        with open(esp) as f:
            etf_summary = json.load(f)

    akt = "-"
    if depots and len(depots) > 1:
        h = depots[-1].get("historie", [])
        if h:
            akt = h[-1].get("zeit", "-")

    # Ranking (sortiert nach Rendite absteigend)
    ranking = sorted(depots, key=lambda d: d["rendite"], reverse=True)
    ranking_mit_platz = [
        {"platz": i+1, **r} for i, r in enumerate(ranking)
    ]

    # Marktstatus
    mk_status, mk_label, boersen = market_status()

    # SPX Benchmark
    spx = get_spx_data()

    # Notifications
    notifs = check_notifications(depots)

    # Letzte Aktualisierung als lesbares Datum
    akt_dt = akt if akt != "-" else datetime.now().strftime("%H:%M") if depots else "-"

    # Gesamt-Wert und Rendite
    ges_wert = sum(d["wert"] for d in depots)
    ges_start = sum(d["start"] for d in depots)
    ges_rendite = round((ges_wert / ges_start - 1) * 100, 2) if ges_start > 0 else 0.0

    # ── Live-Summen aller Kategorien (fuer Verlaufs-Graph-Sync) ──
    akt_wert = ges_wert; akt_start = ges_start; akt_rendite = ges_rendite
    etf_wert = sum(e["wert"] for e in etf_depots); etf_start = sum(e["start"] for e in etf_depots)
    etf_rendite = round((etf_wert / etf_start - 1) * 100, 2) if etf_start > 0 else 0.0
    spec_wert = sum(sd["wert"] for sd in spec_depots); spec_start = sum(sd["start"] for sd in spec_depots)
    spec_rendite = round((spec_wert / spec_start - 1) * 100, 2) if spec_start > 0 else 0.0
    total_wert = akt_wert + etf_wert + spec_wert
    total_start = akt_start + etf_start + spec_start
    total_rendite = round((total_wert / total_start - 1) * 100, 2) if total_start > 0 else 0.0
    # Verlauf berechnen und letzten Punkt jeder Serie mit Live-Werten syncen
    verlauf = portfolio_verlauf(tage=7)
    jetzt_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if verlauf.get("gesamt"):
        verlauf["gesamt"][-1] = {"zeit": jetzt_str, "wert": round(total_wert, 2), "rendite": total_rendite}
    if verlauf.get("aktien"):
        verlauf["aktien"][-1] = {"zeit": jetzt_str, "wert": round(akt_wert, 2), "rendite": akt_rendite}
    if verlauf.get("etf"):
        verlauf["etf"][-1] = {"zeit": jetzt_str, "wert": round(etf_wert, 2), "rendite": etf_rendite}
    if verlauf.get("spec"):
        verlauf["spec"][-1] = {"zeit": jetzt_str, "wert": round(spec_wert, 2), "rendite": spec_rendite}

    # ── News-Score pro Ticker (für A: News-Impact) ──
    # Nutze bewertete News aus KI_LOG (typ=news) wo echte Scores vorhanden sind
    # Nachfilter: News mit Score < NEWS_MIN_SCORE (aus Settings) werden als irrelevant ausgeblendet
    try:
        from settings_loader import news_opt
        NEWS_MIN_SCORE = int(news_opt("news_min_score", 20))
    except Exception:
        NEWS_MIN_SCORE = 20
    news_by_ticker = {}
    for e in KI_LOG:
        if e.get("typ") == "news":
            sc = e.get("score", 0)
            if sc < NEWS_MIN_SCORE:
                continue  # irrelevante News raus
            for t in (e.get("tickers") or []):
                t = t.upper()
                if t not in news_by_ticker or sc > news_by_ticker[t][0]:
                    news_by_ticker[t] = (sc, e.get("stars", ""), e.get("topics", []))
    # Fallback: falls KI_LOG keine News hat, nimm news_cache Headlines (Score 0)
    if not news_by_ticker:
        for n in news:
            for t in (n.get("tickers") or []):
                t = t.upper()
                if t not in news_by_ticker:
                    news_by_ticker[t] = (0, "", n.get("topics", []))

    # ── KI-Konfidenz-Verlauf (für C) ──
    ki_konfidenz_history = []
    for e in KI_LOG:
        if e.get("typ") == "decision" and e.get("konfidenz") is not None and e.get("zeit"):
            try:
                ki_konfidenz_history.append({
                    "zeit": e["zeit"],
                    "konfidenz": int(e["konfidenz"]),
                    "aktion": e.get("aktion", ""),
                })
            except Exception:
                pass
    ki_konfidenz_history = sorted(ki_konfidenz_history, key=lambda x: x["zeit"])[-20:]

    # ── KI-Lern-Notizen (letzter Lernlauf) ──
    ki_lern_notizen = []
    try:
        from ki_learning import lade_lern_notizen
        ki_lern_notizen = lade_lern_notizen(max_age_stunden=72)
    except Exception:
        pass

    # ── Pending Rules (noch nicht bestätigt = wackelig/veraltet in ki_regeln) ──
    pending_rules = [r for r in ki_regeln if r.get("status") in ("wackelig", "veraltet")]

    result = {
            'depots': depots,
            'ranking': ranking_mit_platz,
            'ges_rendite': ges_rendite,
            'ges_wert': ges_wert,
            'spec_depots': spec_depots,
            'etf_depots': etf_depots,
            'etf_summary': etf_summary,
            'news': news[:20],
            'news_by_ticker': news_by_ticker,
            'summary': summary,
            'spec_watch': spec_watch,
            'aktualisiert': akt_dt,
            'markt_status': mk_status,
            'markt_label': mk_label,
            'boersen': boersen,
            'boersen_chips': boersen_chips(),
            'portfolio_verlauf': verlauf,
            'trade_hist_aktien': kategorie_trade_historie("aktien", 60),
            'trade_hist_etf': kategorie_trade_historie("etf", 60),
            'trade_hist_spec': kategorie_trade_historie("spec", 60),
            'ki_log': KI_LOG,
            'ki_konfidenz_history': ki_konfidenz_history,
            'system_log': SYSTEM_LOG,
            'ki_statistik': ki_statistik,
            'ki_regeln': ki_regeln,
            'ki_regel_familien': ki_regel_familien,
            'regelstand': regelstand_aggregat(ki_regeln),
            'regel_history': regel_history,
            'regel_konflikte': regel_konflikte,
            'konfidenz_cap': konfidenz_cap,
            'ki_lern_notizen': ki_lern_notizen,
            'pending_rules': pending_rules,
            'trader_status': trader_status,
            'spx_historie': spx,
            'notifications': notifs,
            'health': _health_status(),
            'paused': _ist_pausiert(),
            'profil': _profil_info(),
            'verfuegbare_profile': _profile_liste(),
        }
    # Cache aktualisieren
    data._cache = result
    data._cache_ts = time.time()
    return result




def _health_status():
    """Sammelt operativen Gesundheitsstatus für die Dashboard-Health-Karte (v2.15.9)."""
    import glob as _glob
    h = {"gateway": False, "dashboard": True, "letzter_batch": None,
         "offene_boersen": [], "pipeline_aktiv": False, "fehler_24h": 0}

    # Gateway-State (Hermes WhatsApp/Node-Bridge)
    try:
        gsp = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                          "hermes", "gateway_state.json")
        if os.path.exists(gsp):
            with open(gsp) as f:
                gs = json.load(f)
            # connected wenn whatsapp.state == 'connected' ODER gateway 'running'
            pl = gs.get("platforms", {}).get("whatsapp", {})
            h["gateway"] = pl.get("state") == "connected" or gs.get("status") == "running"
    except Exception:
        pass

    # Letzter batch_trader-Lauf aus cron_pipeline.log
    try:
        logp = os.path.join(BASE, "cron_pipeline.log")
        if os.path.exists(logp):
            with open(logp, errors="ignore") as f:
                lines = f.readlines()
            for ln in reversed(lines[-400:]):
                if "batch_trader.py" in ln:
                    if "OK" in ln:
                        h["letzter_batch"] = ln.strip() + " ✅"
                    elif "FEHLER" in ln or "TIMEOUT" in ln:
                        h["letzter_batch"] = ln.strip() + " ❌"
                        h["fehler_24h"] += 1
                    else:
                        h["letzter_batch"] = ln.strip()
                    break
    except Exception:
        pass

    # Offene Börsen (nutzt boersen.ist_offen)
    try:
        from boersen import BOERSEN, ist_offen
        for name, b in BOERSEN.items():
            if ist_offen(name):
                h["offene_boersen"].append(b.get("label", name))
    except Exception:
        pass

    # Naechster Scheduler-Lauf (alle 15min: Minute 0,15,30,45)
    try:
        from datetime import datetime
        now = datetime.now()
        minute = now.minute
        # naechste 15min-Grenze
        if minute < 15: nxt = 15 - minute
        elif minute < 30: nxt = 30 - minute
        elif minute < 45: nxt = 45 - minute
        else: nxt = 60 - minute
        h["naechster_lauf_min"] = nxt
    except Exception:
        h["naechster_lauf_min"] = None

    # Pipeline aktiv? (subprocess pruefen)
    try:
        import subprocess as _sp
        out = _sp.run(["tasklist", "/FI", "IMAGENAME eq pythonw.exe", "/NH"],
                      capture_output=True, text=True, timeout=5)
        h["pipeline_aktiv"] = "micro-trader-pipeline" in out.stdout
    except Exception:
        pass

    return h




@app.route("/api/pause_trading")
def pause_trading():
    """Setzt oder liest das Pause-Flag (v2.16.2)."""
    pf = os.path.join(BASE, "pause_flag.json")
    state = request.args.get("state", "").lower()
    if state in ("on", "off", "1", "0"):
        paused = state in ("on", "1")
        grund = request.args.get("grund", "manuell")
        try:
            with open(pf, "w") as f:
                json.dump({"paused": paused, "grund": grund,
                           "zeit": time.strftime("%Y-%m-%d %H:%M")}, f)
            return {"ok": True, "paused": paused, "grund": grund}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    # GET ohne state -> Status
    if os.path.exists(pf):
        try:
            with open(pf) as f:
                return {"ok": True, **json.load(f)}
        except Exception:
            pass
    return {"ok": True, "paused": False}



def _ist_pausiert():
    """Liest das Pause-Flag (v2.16.2)."""
    pf = os.path.join(BASE, "pause_flag.json")
    if os.path.exists(pf):
        try:
            with open(pf) as f:
                d = json.load(f)
            return {"paused": bool(d.get("paused")), "grund": d.get("grund", ""),
                    "zeit": d.get("zeit", "")}
        except Exception:
            pass
    return {"paused": False, "grund": "", "zeit": ""}




@app.route("/api/profil_karten")
def api_profil_karten():
    """Phase 11 (§18): Profil-/Markt-Karten für Dashboard-Steuerzentrale.
    Nutzt profil_schema (neu, §29.A). Multi-Markt-Ausbau US/DE/JP."""
    try:
        from profil_schema import lade_profil
        karten = []
        for name, markt in [("us_shadow", "US"), ("de_shadow", "DE"), ("jp_shadow", "JP")]:
            p, fehler, warn = lade_profil(name)
            if not p:
                karten.append({"markt": markt, "name": name, "status": "fehler",
                               "modus": "shadow", "depotarten": [], "warnung": fehler})
                continue
            karten.append({
                "markt": markt,
                "name": p.get("name", name),
                "status": "shadow" if p.get("modus") == "shadow" else "live",
                "modus": p.get("modus", "shadow"),
                "depotarten": p.get("depotarten", []),
                "maerkte": p.get("märkte", []),
                "base_currency": p.get("base_currency", "USD"),
                "regelstand_ref": p.get("regelstand_ref", "unbekannt"),
                "warnung": warn or "",
            })
        return {"ok": True, "karten": karten}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.route("/api/profile")
def api_profile():
    """Liefert/setzt das aktive Profil (Phase 2)."""
    set_name = request.args.get("set", "").strip()
    if set_name:
        try:
            from profile_schema import setze_aktives_profil, lade_aktives_profil
            if setze_aktives_profil(set_name):
                # Cache invalidieren, damit /data sofort das neue Profil liefert
                if hasattr(data, "_cache"):
                    data._cache = None
                p = lade_aktives_profil()
                return {"ok": True, "gewechselt_zu": p.name, **p.to_dict()}
            return {"ok": False, "error": f"Profil {set_name} nicht gefunden"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    try:
        from profile_schema import lade_aktives_profil, liste_profile, aktives_profil_name
        p = lade_aktives_profil()
        return {"ok": True, "aktiv": aktives_profil_name(),
                "verfuegbar": liste_profile(), **p.to_dict()}
    except Exception as e:
        return {"ok": False, "error": str(e)}



def _profil_info():
    """Liefert Profil-Metadaten für Dashboard (Phase 2)."""
    try:
        from profile_schema import lade_aktives_profil, MODUS_ICON
        p = lade_aktives_profil()
        return {
            "name": p.name,
            "modus": p.modus,
            "modus_icon": MODUS_ICON.get(p.modus, "👁️"),
            "märkte": p.märkte(),
            "depotarten": p.depotarten(),
            "base_currency": p.base_currency,
            "version": p.get("version", ""),
        }
    except Exception:
        return None




def _profile_liste():
    """Liste aller verfügbaren Profile für Wechsel-Dropdown (Phase 2)."""
    try:
        from profile_schema import liste_profile
        return liste_profile()
    except Exception:
        return []


@app.route("/search_ticker")
def search_ticker():
    """Sucht einen Ticker über alle Depots."""
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return {"results": []}
    results = []
    for risk in RISK_STUFEN:
        dp = depot_pfad(risk)
        if not os.path.exists(dp):
            continue
        with open(dp) as f:
            d = json.load(f)
        for t, pos in d.get("positions", {}).items():
            if t.upper() == ticker or ticker in t.upper():
                wert = pos["shares"] * pos.get("avg_price", 0)
                results.append({
                    "risk": risk,
                    "ticker": t,
                    "name": name_for(t),
                    "shares": pos["shares"],
                    "avg_price": pos.get("avg_price", 0),
                    "wert": round(wert, 2),
                })
    # Auch Spekulation-Depots durchsuchen
    sdd = os.path.join(BASE, "spec_depots")
    if os.path.isdir(sdd):
        for fn in sorted(os.listdir(sdd)):
            if fn.endswith(".json"):
                t = fn.replace(".json", "")
                if t.upper() == ticker or ticker in t.upper():
                    with open(os.path.join(sdd, fn)) as f:
                        sd = json.load(f)
                    results.append({
                        "risk": "🔥",
                        "ticker": t,
                        "name": sd.get("name", t),
                        "shares": sd.get("shares", 0),
                        "avg_price": sd.get("avg_price", 0),
                        "wert": sd.get("bargeld", 0) + sd.get("shares", 0) * sd.get("avg_price", 0),
                    })
    return {"results": results}


@app.route("/api/clear_cache")
def clear_cache():
    if hasattr(data, '_cache'):
        delattr(data, '_cache')
    if hasattr(data, '_cache_ts'):
        delattr(data, '_cache_ts')
    return {"ok": True}

@app.route("/api/ki_log")
def api_ki_log():
    kip = os.path.join(BASE, "ki_log.json")
    if os.path.exists(kip):
        with open(kip, encoding='utf-8') as f:
            return json.load(f)
    return []


@app.route("/api/db_query")
def api_db_query():
    try:
        from db import MTDB
        db = MTDB()
        mode = request.args.get("mode", "trades")
        typ = request.args.get("typ", "")
        ticker = request.args.get("ticker", "")
        aktion = request.args.get("aktion", "")
        tage = request.args.get("tage", type=int, default=30)
        order = request.args.get("order", "DESC")
        limit = request.args.get("limit", type=int, default=500)
        provider = request.args.get("provider", "")
        regel_id = request.args.get("regel_id", "")
        fallback = request.args.get("fallback", "")
        if mode == "ki":
            rows = db.query_ki(ticker=ticker, limit=limit, provider=provider or None,
                               regel_id=regel_id or None,
                               fallback=(fallback == "true") if fallback else None)
        else:
            rows = db.query_trades(typ=typ, ticker=ticker, aktion=aktion, tage=tage, order=order, limit=limit)
        db.close()
        return {"error": None, "count": len(rows), "rows": rows}
    except Exception as e:
        return {"error": str(e), "count": 0, "rows": []}


@app.route("/api/db_karten")
def api_db_karten():
    try:
        from db import MTDB
        db = MTDB()
        tage = request.args.get("tage", type=int, default=30)
        karten = db.analyse_karten(tage=tage)
        db.close()
        return {"error": None, "karten": karten}
    except Exception as e:
        return {"error": str(e), "karten": {}}


@app.route("/depot_json")
def depot_json():
    risk = request.args.get("risk", type=int)
    if risk is None:
        return {"error": "risk parameter required"}
    dp = depot_pfad(risk)
    if not os.path.exists(dp):
        return {"error": "not found"}
    with open(dp) as f:
        return json.load(f)

@app.route("/spec_depot_json")
def spec_depot_json():
    ticker = request.args.get("ticker", "")
    if not ticker:
        return {"error": "ticker parameter required"}
    dp = os.path.join(BASE, "spec_depots", "%s.json" % ticker)
    if not os.path.exists(dp):
        return {"error": "not found"}
    with open(dp) as f:
        return json.load(f)


@app.route("/etf_depot_json")
def etf_depot_json():
    """Liefert das vollständige ETF-Depot-JSON für die Detailseite.
    Kompatibel mit showDepot(): enthält positions, trades, historie, ki_letzte."""
    risk = request.args.get("risk", type=int)
    if risk is None:
        return {"error": "risk parameter required"}
    ep = os.path.join(BASE, "etf_%03d.json" % risk)
    if not os.path.exists(ep):
        return {"error": "not found"}
    with open(ep) as f:
        d = json.load(f)
    # stufe fuer Anzeige ergaenzen (falls fehlt)
    if "stufe" not in d:
        try:
            stufen = ["Sehr konservativ", "Konservativ", "Ausgewogen",
                      "Wachstum", "Aggressiv", "Sehr aggressiv"]
            d["stufe"] = stufen[min(5, risk // 20)]
        except Exception:
            d["stufe"] = "Risk %d" % risk
    return d

@app.route("/ticker_chart")
def ticker_chart():
    """6-Monats-Kursverlauf für einen Ticker (JSON für Chart.js)."""
    import yfinance as yf
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return {"error": "ticker parameter required", "data": [], "dates": []}
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo", interval="1d")
        if hist.empty:
            return {"ticker": ticker, "dates": [], "data": [], "error": "keine Daten"}
        close = hist["Close"]
        return {
            "ticker": ticker,
            "name": name_for(ticker),
            "dates": [str(d.date()) for d in close.index],
            "data": [round(float(v), 2) for v in close.values],
        }
    except Exception as e:
        return {"ticker": ticker, "dates": [], "data": [], "error": str(e)}

@app.route("/api/analysis")
def api_analysis():
    cache_path = os.path.join(BASE, "analysis_cache.json")
    # Cache nur nutzen, wenn valide (Race-Condition-sicher)
    if os.path.exists(cache_path) and time.time() - os.path.getmtime(cache_path) < 300:
        try:
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError, OSError):
            pass  # korrupter Cache -> neu berechnen
    from analysis import run_all
    try:
        result = run_all()
    except Exception:
        return jsonify({"zeit": "", "aktien": {}, "etf": {}, "spekulation": {},
                         "risiko_aktien": {}, "risiko_etf": {}, "risiko_spekulation": {}})
    # Atomar schreiben: temp-file + rename (verhindert truncated cache bei Concurrent-Writes)
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    os.replace(tmp, cache_path)
    return result

# ─── Settings API (KI + Lernen + Bremsen + News) ─────────────
@app.route("/api/version")
def api_version():
    """Liefert version.json (Changelog/Version-Log)."""
    try:
        with open(os.path.join(BASE, "version.json"), encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({"version": "?", "released_at": "?", "codename": "", "changes": []})

@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    from settings_loader import lade_settings, LIMITS, BOOLS, LABELS
    return jsonify({
        "settings": lade_settings(),
        "limits": {k: {"min": v[0], "max": v[1], "emp_min": v[2], "emp_max": v[3],
                        "einheit": v[4], "warn_unter": v[5], "warn_ueber": v[6]}
                    for k, v in LIMITS.items() if k not in BOOLS},
        "bools": BOOLS,
        "labels": {k: {"name": v[0], "desc": v[1]} for k, v in LABELS.items()},
    })

@app.route("/api/settings", methods=["POST"])
@app.route("/api/report_pdf")
def api_report_pdf():
    """Phase 10 (§17): Manueller PDF-Report-Trigger (neben 22:00-Cron)."""
    try:
        import subprocess, os
        from datetime import datetime
        # report_pdf.py im gleichen Verzeichnis ausführen
        subprocess.run(
            [sys.executable, os.path.join(BASE, "report_pdf.py")],
            capture_output=True, timeout=120
        )
        heute = datetime.now().strftime("%Y-%m-%d")
        pfad = os.path.join(BASE, "reports", f"micro_trader_{heute}.pdf")
        if os.path.exists(pfad):
            return {"ok": True, "pfad": pfad,
                    "url": f"/reports/micro_trader_{heute}.pdf"}
        return {"ok": False, "error": "PDF nicht erstellt"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.route("/api/report_list")
def api_report_list():
    """Liste aller archivierten PDFs (reports/)."""
    try:
        import glob, os
        files = sorted(glob.glob(os.path.join(BASE, "reports", "*.pdf")),
                       key=os.path.getmtime, reverse=True)
        return {"ok": True, "reports": [
            {"name": os.path.basename(f),
             "url": f"/reports/{os.path.basename(f)}",
             "size": os.path.getsize(f),
             "datum": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")}
            for f in files[:30]
        ]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.route("/reports/<path:name>")
def serve_report(name):
    """PDF direkt ausliefern (Download/Anzeige)."""
    from flask import send_from_directory
    return send_from_directory(os.path.join(BASE, "reports"), name)


def api_settings_post():
    from settings_loader import speichere_settings, validiere_und_risiko
    payload = request.get_json(force=True, silent=True) or {}
    neue = payload.get("settings", {})
    bestaetigt = payload.get("bestaetigt", False)
    ok, meldung, warnungen = speichere_settings(neue, bestaetigt=bestaetigt)
    if not ok and warnungen and not bestaetigt:
        # Risikowarnung → Frontend muss erneut mit bestaetigt=true senden
        return jsonify({"ok": False, "warnung": True, "meldung": meldung,
                        "warnungen": warnungen}), 200
    return jsonify({"ok": ok, "meldung": meldung, "warnungen": warnungen}), 200

# ─── PHASE 4-6: Security-Hooks (serverseitige Routenprüfung + Header) ───────
import functools

@ app.after_request
def _security_headers(resp):
    """Setzt OWASP-konforme Security-Header (Phase 5)."""
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'; base-uri 'self'")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@ app.before_request
def _route_access_control():
    """PHASE 6: serverseitige Zugriffskontrolle für ALLE Routen.
    Frontend-Ausblendung ist KEINE Berechtigung (Auftrag Regel 5)."""
    rule = request.path
    cls = sec.route_class(rule)
    if cls == "PUBLIC":
        return
    # JSON-Routen (API/JS-Fetch) bekommen bei fehlendem Auth IMMER 401/403 JSON,
    # nie einen HTML-Redirect (sonst parse-Fehler "Unexpected token '<'" im Frontend).
    json_routes = ("/api/", "/search_ticker", "/ticker_chart", "/data",
                   "/depot_json", "/spec_depot_json", "/etf_depot_json", "/reports/")
    wants_json = request.path.startswith(json_routes) or \
        "application/json" in (request.headers.get("Accept", "") or "")
    u = sec.current_user()
    if cls == "AUTHENTICATED":
        if not u or not sec.access_level_met(u["role"], "AUTHENTICATED"):
            if wants_json:
                return jsonify({"error": "unauthorized"}), 401
            return redirect("/login?next=" + rule)
        sec.touch_session(u["username"], sec._current_sid())
        return
    # ANALYST / OPERATOR / ADMIN / SUPERADMIN
    if not u:
        if wants_json:
            return jsonify({"error": "unauthorized"}), 401
        return redirect("/login?next=" + rule)
    if not sec.access_level_met(u["role"], cls):
        if wants_json:
            return jsonify({"error": "forbidden"}), 403
        return jsonify({"error": "forbidden"}), 403
    sec.touch_session(u["username"], sec._current_sid())


# ─── PHASE 4: Auth-Routen (Login/Logout/MFA) ────────────────────────────────
@ app.route("/login", methods=["GET", "POST"])
def login():
    """Login (Phase 4). Setzt sichere Session-Cookies."""
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        if sec.verify_password(uname, pw):
            sid = sec.create_session(uname, request.remote_addr or "")
            # Session-Rotation nach Login (Phase 5)
            sid = sec.rotate_session(uname, sid) or sid
            resp = make_response(redirect(request.args.get("next") or "/dashboard"))
            resp.set_cookie("username", uname, httponly=True, samesite="Lax",
                            secure=False)  # secure=True erst bei HTTPS/Funnel
            resp.set_cookie("sid", sid, httponly=True, samesite="Lax",
                            secure=False)
            u = sec.get_user(uname)
            u["last_login"] = datetime.utcnow().isoformat() + "Z"
            sec.audit_log("login", uname)
            return resp
        sec.audit_log("login_failed", uname)
        return make_response("<h1>Login fehlgeschlagen</h1><a href='/login'>neu</a>"), 401
    return make_response(
        "<form method='POST'>Benutzer:<input name='username'><br>"
        "Passwort:<input name='password' type='password'><br>"
        "<input type='submit' value='Login'></form>")


@ app.route("/logout")
def logout():
    uname = request.cookies.get("username")
    sid = request.cookies.get("sid")
    if uname and sid:
        sec.revoke_session(uname, sid)
    resp = make_response(redirect("/login"))
    resp.delete_cookie("username")
    resp.delete_cookie("sid")
    return resp


@ app.route("/mfa", methods=["GET", "POST"])
def mfa_verify():
    """MFA-Verifizierung (Phase 4). Erforderlich für admin/superadmin."""
    uname = request.cookies.get("username")
    sid = request.cookies.get("sid")
    if not uname or not sid or not sec.session_valid(uname, sid):
        return redirect("/login")
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        u = sec.get_user(uname)
        if u and sec.verify_mfa(u.get("mfa_secret", ""), code):
            sec.mark_mfa_verified(uname, sid)
            sec.audit_log("mfa_verify", uname)
            return redirect("/admin")
        return make_response("<h1>MFA falsch</h1><a href='/mfa'>neu</a>"), 401
    return make_response(
        "<form method='POST'>MFA-Code:<input name='code'><br>"
        "<input type='submit' value='OK'></form>")


@ app.route("/setup_mfa", methods=["GET", "POST"])
@ sec.require_role("admin")
def setup_mfa():
    """MFA für aktuellen User einrichten (Provisioning)."""
    uname = request.cookies.get("username")
    u = sec.get_user(uname)
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if sec.enable_mfa(uname, code):
            return redirect("/data")
        return make_response("<h1>Code falsch</h1><a href='/setup_mfa'>neu</a>")
    pending = sec.generate_mfa_secret()
    u["mfa_pending_secret"] = pending
    sec._save_users({x["username"]: x for x in sec.list_users()})
    uri = sec.mfa_provisioning_uri(pending, uname)
    return make_response(
        f"<h1>MFA einrichten</h1><p>Secret: {pending}</p>"
        f"<p><a href='{uri}'>otpauth-Link</a></p>"
        f"<form method='POST'>Code:<input name='code'><br>"
        f"<input type='submit' value='Aktivieren'></form>")


# ─── Öffentliche Landingpage (nur allgemeine Infos, kein internes JSON) ──
@app.route("/", methods=["GET", "POST"])
@app.route("/landing", methods=["GET", "POST"])
def landing():
    """Öffentliche Landingpage (PUBLIC).
    Darf NUR: Projektname, Kurzbeschreibung, Paper-/Shadow-Hinweis,
    Betriebsstatus OHNE interne Details, Login-Formular direkt auf der Seite.
    Lädt KEINE internen JSON-Daten (Depot/KI/Regeln/Provider/Logs)."""
    status = "Paper-/Shadow-Trading-System (kein Echtgeld)"
    fehler = ""
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        if sec.verify_password(uname, pw):
            sid = sec.create_session(uname, request.remote_addr or "")
            sid = sec.rotate_session(uname, sid) or sid
            resp = make_response(redirect("/dashboard"))
            resp.set_cookie("username", uname, httponly=True, samesite="Lax", secure=False)
            resp.set_cookie("sid", sid, httponly=True, samesite="Lax", secure=False)
            u = sec.get_user(uname)
            u["last_login"] = datetime.utcnow().isoformat() + "Z"
            sec.audit_log("login", uname)
            return resp
        sec.audit_log("login_failed", uname)
        fehler = "<div style='margin:10px 0 0;color:#b91c1c;background:#fee2e2;border:1px solid #fecaca;border-radius:8px;padding:8px 12px;font-size:13px'>Anmeldung fehlgeschlagen – Benutzername oder Passwort falsch.</div>"
    return make_response(f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Micro-Trader – Anmeldung</title>
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;margin:0;padding:0;background:linear-gradient(160deg,#eef2ff,#fdf4ff);background-image:radial-gradient(ellipse at 15% 0%,rgba(67,97,238,.10) 0%,transparent 55%),radial-gradient(ellipse at 85% 0%,rgba(16,185,129,.07) 0%,transparent 50%);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box}}
.card{{max-width:560px;width:100%;background:rgba(255,255,255,.72);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.85);border-radius:22px;box-shadow:0 24px 60px rgba(80,110,255,.16);overflow:hidden}}
.banner{{width:100%;height:110px;display:block;object-fit:contain;object-position:center;background:#0b1220;border-bottom:1px solid rgba(15,23,42,.07)}}
.inner{{padding:26px 30px 30px}}
.head{{display:flex;align-items:center;gap:12px;margin-bottom:6px}}
.logo{{width:44px;height:44px;border-radius:10px}}
h1{{font-size:26px;margin:0;color:#1a1a2e}}
.badge{{display:inline-block;background:#e8f5e9;color:#1b5e20;border-radius:999px;padding:4px 12px;font-size:12.5px;font-weight:600;margin-bottom:12px}}
p{{line-height:1.6;color:#444;margin:8px 0}}
.status{{color:#777;font-size:13px}}
label{{display:block;margin-top:14px;font-size:13.5px;font-weight:600;color:#333}}
input{{display:block;width:100%;box-sizing:border-box;margin-top:6px;padding:12px 14px;font-size:15px;border:1px solid #cfdceb;border-radius:10px;background:#fff;font-family:inherit;transition:border-color .15s,box-shadow .15s}}
input:focus{{outline:none;border-color:#4361ee;box-shadow:0 0 0 3px rgba(67,97,238,.15)}}
button{{margin-top:18px;width:100%;background:#4361ee;color:#fff;border:none;padding:13px 0;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer;transition:background .15s,transform .05s}}
button:hover{{background:#3a55d8}}
button:active{{transform:translateY(1px)}}
.hint{{margin-top:14px;font-size:12px;color:#888;text-align:center}}
</style></head><body>
<div class='card'>
<img class='banner' src='/assets/banner.png' alt='Micro Trader System'>
<div class='inner'>
<div class='head'><img class='logo' src='/assets/logo.png' alt='Logo'><h1>Micro-Trader</h1></div>
<span class='badge'>{status}</span>
<p>Automatisierter Paper-/Shadow-Trading-Assistent für Aktien, ETF und Spekulation.
Alle Handelsentscheidungen erfolgen ausschließlich in simulierten Depots — <b>kein Echtgeldeinsatz</b>.</p>
<p class='status'>Systemstatus: aktiv · NYSE-Handelszeiten Mo–Fr 15:30–22:00 MEZ · Mehrbenutzer-Zugang mit Rollenrechten.</p>
<form method='POST' action='/'>
<label for='login-user'>Benutzername</label>
<input id='login-user' name='username' autocomplete='username' required autofocus>
<label for='login-pass'>Passwort</label>
<input id='login-pass' name='password' type='password' autocomplete='current-password' required>
<button type='submit'>Anmelden</button>
{fehler}
</form>
<p class='hint'>Zugriff nur für berechtigte Benutzer · Paper-/Shadow-System (kein Echtgeld)</p>
</div></div></body></html>""")


# ─── PHASE 8: Admin-Bereich (nur ADMIN/SUPERADMIN via before_request) ──────────
@app.route("/admin")
@ sec.require_role("admin")
def admin_overview():
    """Admin-Übersicht: Systemstatus + Schnellzugriff."""
    u = sec.current_user()
    return make_response(f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Admin – Micro-Trader</title>
<style>body{{font-family:system-ui,sans-serif;max-width:820px;margin:5vh auto;padding:0 20px;color:#1a1a2e}}
nav a{{margin-right:14px;color:#4361ee;text-decoration:none;font-weight:600}}
.card{{background:#fafbff;border:1px solid #e2e8ff;border-radius:14px;padding:20px;margin:14px 0}}
h1{{font-size:24px}}h2{{font-size:18px;color:#334}}code{{background:#eef;padding:2px 6px;border-radius:5px}}</style>
</head><body>
<h1>🔧 Admin-Bereich</h1>
<nav><a href='/admin'>Übersicht</a><a href='/admin/users'>Benutzer</a>
<a href='/admin/system'>Systemstatus</a><a href='/admin/rules'>Regeln</a>
<a href='/admin/audit'>Audit</a><a href='/admin/backups'>Backups</a>
<a href='/logout'>Logout</a></nav>
<div class='card'><h2>Angemeldet als</h2><p><code>{u['username']}</code> · Rolle: <code>{u['role']}</code>
· MFA: <code>{'aktiv' if u.get('mfa_secret') else 'nicht eingerichtet'}</code></p>
<p>Alle Admin-Aktionen werden im Audit-Log protokolliert. Kritische Änderungen
benötigen zusätzlich eine kürzlich verifizierte MFA.</p></div>
</body></html>""")


@app.route("/admin/system")
@ sec.require_role("admin")
def admin_system():
    """Systemstatus (Phase 8 Bereich 1)."""
    import os, json as _json
    pause = _json.load(open("pause_flag.json")) if os.path.exists("pause_flag.json") else {}
    return make_response(f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Systemstatus – Micro-Trader</title>
<style>body{{font-family:system-ui;max-width:820px;margin:5vh auto;padding:0 20px;color:#1a1a2e}}
nav a{{margin-right:14px;color:#4361ee;text-decoration:none;font-weight:600}}
.card{{background:#fafbff;border:1px solid #e2e8ff;border-radius:14px;padding:20px;margin:14px 0}}
code{{background:#eef;padding:2px 6px;border-radius:5px}}</style></head><body>
<nav><a href='/admin'>Übersicht</a><a href='/admin/users'>Benutzer</a>
<a href='/admin/system'>Systemstatus</a><a href='/admin/rules'>Regeln</a>
<a href='/admin/audit'>Audit</a><a href='/admin/backups'>Backups</a></nav>
<div class='card'><h2>Systemstatus</h2>
<p>Trading-Pause: <code>{'AKTIV (' + str(pause.get('grund','')) + ')' if pause.get('state')=='on' else 'nein'}</code></p>
<p>Paper-/Shadow-Modus: <code>aktiv (kein Echtgeld)</code></p>
<p>Engine/Board: s. Cronjobs (Mo–Fr 15–22 MEZ).</p></div></body></html>""")


@app.route("/admin/users")
@ sec.require_role("admin")
def admin_users():
    """Benutzerverwaltung (Phase 8 Bereich 4) – Liste."""
    u = sec.current_user()
    rows = ""
    for name in sec.list_users():
        usr = sec.get_user(name)
        rows += f"<tr><td>{name}</td><td>{usr.get('role')}</td><td>{'ja' if usr.get('mfa_secret') else 'nein'}</td><td>{usr.get('last_login','–')}</td></tr>"
    return make_response(f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Benutzer – Micro-Trader</title>
<style>body{{font-family:system-ui;max-width:900px;margin:5vh auto;padding:0 20px;color:#1a1a2e}}
nav a{{margin-right:14px;color:#4361ee;text-decoration:none;font-weight:600}}
table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:8px;border-bottom:1px solid #eee}}
.card{{background:#fafbff;border:1px solid #e2e8ff;border-radius:14px;padding:20px;margin:14px 0}}</style></head><body>
<nav><a href='/admin'>Übersicht</a><a href='/admin/users'>Benutzer</a>
<a href='/admin/system'>Systemstatus</a><a href='/admin/rules'>Regeln</a>
<a href='/admin/audit'>Audit</a><a href='/admin/backups'>Backups</a>
<a href='/logout'>Logout</a></nav>
<div class='card'><h2>Benutzer ({len(sec.list_users())})</h2>
<p><a href='/admin/users/create'>+ Neuer Benutzer</a> · <a href='/setup_mfa'>MFA einrichten</a></p>
<table><tr><th>Name</th><th>Rolle</th><th>MFA</th><th>Letzter Login</th></tr>{rows}</table>
<p style='color:#888;font-size:12px'>Hinweis: Passwörter/MFA-Secrets werden niemals angezeigt.</p></div></body></html>""")


@app.route("/admin/users/create", methods=["GET", "POST"])
@ sec.require_role("admin")
def admin_users_create():
    """Benutzer anlegen (Phase 8 Bereich 4)."""
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        role = request.form.get("role", "user")
        if not uname or not pw:
            return make_response("<h1>Fehler</h1>Benutzer/Passwort fehlt.<a href='/admin/users/create'>zurück</a>"), 400
        ok, err = sec.create_user(uname, pw, role)
        if not ok:
            return make_response(f"<h1>Fehler</h1>{err}<a href='/admin/users/create'>zurück</a>"), 400
        sec.audit_log("user_create", sec.current_user()["username"], f"{uname} role={role}")
        return redirect("/admin/users")
    return make_response("""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Neuer Benutzer – Micro-Trader</title>
<style>body{font-family:system-ui;max-width:520px;margin:6vh auto;padding:0 20px;color:#1a1a2e}
input,select{padding:9px;width:100%;margin:6px 0;border:1px solid #ccd;border-radius:8px}
.btn{background:#4361ee;color:#fff;border:0;padding:11px 20px;border-radius:9px;font-weight:600;cursor:pointer}
nav a{margin-right:14px;color:#4361ee;text-decoration:none;font-weight:600}</style></head><body>
<nav><a href='/admin/users'>← Benutzer</a></nav>
<h1>Neuer Benutzer</h1>
<form method='POST'>Benutzername:<input name='username'>
Passwort:<input name='password' type='password'>
Rolle:<select name='role'><option>user</option><option>analyst</option>
<option>operator</option><option>admin</option><option>superadmin</option></select>
<button class='btn' type='submit'>Anlegen</button></form></body></html>""")


@app.route("/admin/rules", methods=["GET", "POST"])
@ sec.require_role("admin")
def admin_rules():
    """Regelverwaltung (Phase 8 Bereich 3) – Freigabe/Rollback mit Audit."""
    u = sec.current_user()
    if request.method == "POST":
        action = request.form.get("action", "")
        detail = request.form.get("detail", "")
        sec.audit_log(f"rules_{action}", u["username"], detail)
        return redirect("/admin/rules")
    return make_response(f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Regeln – Micro-Trader</title>
<style>body{{font-family:system-ui;max-width:820px;margin:5vh auto;padding:0 20px;color:#1a1a2e}}
nav a{{margin-right:14px;color:#4361ee;text-decoration:none;font-weight:600}}
.card{{background:#fafbff;border:1px solid #e2e8ff;border-radius:14px;padding:20px;margin:14px 0}}
form{{display:inline-block;margin-right:10px}}button{{padding:8px 16px;border:0;border-radius:8px;cursor:pointer;font-weight:600}}
.btn-release{{background:#2e7d32;color:#fff}} .btn-rollback{{background:#c62828;color:#fff}}</style></head><body>
<nav><a href='/admin'>Übersicht</a><a href='/admin/users'>Benutzer</a>
<a href='/admin/system'>Systemstatus</a><a href='/admin/rules'>Regeln</a>
<a href='/admin/audit'>Audit</a><a href='/admin/backups'>Backups</a></nav>
<div class='card'><h2>Regelverwaltung</h2>
<p>Aktueller Regelstand: <code>v{version.get('version','?')}</code> (Paper-/Shadow).</p>
<form method='POST'><input type='hidden' name='action' value='release'>
<input name='detail' placeholder='Begründung Freigabe' style='padding:7px;width:240px'>
<button class='btn-release' type='submit'>Freigeben</button></form>
<form method='POST'><input type='hidden' name='action' value='rollback'>
<input name='detail' placeholder='Begründung Rollback' style='padding:7px;width:240px'>
<button class='btn-rollback' type='submit'>Rollback</button></form>
<p style='color:#888;font-size:12px'>Jede Aktion schreibt Admin-ID, Zeitstempel, Begründung + Audit-Eintrag.</p></div></body></html>""")


@app.route("/admin/audit")
@ sec.require_role("admin")
def admin_audit():
    """Audit-Log anzeigen (Phase 8 Bereich 5)."""
    entries = sec.read_audit(50)
    rows = "".join(f"<tr><td>{e.get('ts','')}</td><td>{e.get('action','')}</td><td>{e.get('actor','')}</td><td>{e.get('detail','')}</td></tr>" for e in entries)
    return make_response(f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Audit – Micro-Trader</title>
<style>body{{font-family:system-ui;max-width:1000px;margin:4vh auto;padding:0 20px;color:#1a1a2e}}
nav a{{margin-right:14px;color:#4361ee;text-decoration:none;font-weight:600}}
table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:7px;border-bottom:1px solid #eee;font-size:13px}}
.card{{background:#fafbff;border:1px solid #e2e8ff;border-radius:14px;padding:18px;margin:14px 0}}</style></head><body>
<nav><a href='/admin'>Übersicht</a><a href='/admin/users'>Benutzer</a>
<a href='/admin/system'>Systemstatus</a><a href='/admin/rules'>Regeln</a>
<a href='/admin/audit'>Audit</a><a href='/admin/backups'>Backups</a></nav>
<div class='card'><h2>Audit-Log (letzte 50)</h2>
<table><tr><th>Zeit</th><th>Aktion</th><th>Akteur</th><th>Detail</th></tr>{rows}</table>
<p style='color:#888;font-size:12px'>Audit-Einträge sind append-only und nicht nachträglich änderbar.</p></div></body></html>""")


@app.route("/admin/backups")
@ sec.require_role("admin")
def admin_backups():
    """Backups auflisten (Phase 8 Bereich 5 / Phase 9)."""
    import os, glob
    bdir = os.path.join(BASE, ".backup")
    items = sorted(glob.glob(os.path.join(bdir, "*")), reverse=True)[:10] if os.path.isdir(bdir) else []
    rows = "".join(f"<tr><td>{os.path.basename(i)}</td><td>{os.path.getsize(i)//1024} KB</td></tr>" for i in items)
    return make_response(f"""<!doctype html><html lang='de'><head><meta charset='utf-8'>
<title>Backups – Micro-Trader</title>
<style>body{{font-family:system-ui;max-width:820px;margin:5vh auto;padding:0 20px;color:#1a1a2e}}
nav a{{margin-right:14px;color:#4361ee;text-decoration:none;font-weight:600}}
table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:7px;border-bottom:1px solid #eee}}
.card{{background:#fafbff;border:1px solid #e2e8ff;border-radius:14px;padding:18px;margin:14px 0}}</style></head><body>
<nav><a href='/admin'>Übersicht</a><a href='/admin/users'>Benutzer</a>
<a href='/admin/system'>Systemstatus</a><a href='/admin/rules'>Regeln</a>
<a href='/admin/audit'>Audit</a><a href='/admin/backups'>Backups</a></nav>
<div class='card'><h2>Backups (zuletzt 10)</h2>
<table><tr><th>Name</th><th>Größe</th></tr>{rows or '<tr><td colspan=2>keine</td></tr>'}</table></div></body></html>""")


if __name__ == "__main__":
    print("Dashboard -> http://localhost:%d" % PORT)
    # PHASE 2 (Server-Sicherheit): nur intern binden, niemals 0.0.0.0 (Regel 4).
    # Interner Port bleibt 5300; der Reverse Proxy (Phase 3) ist der einzige
    # öffentliche Einstiegspunkt. Flask darf niemals direkt public sein.
    app.run(host="127.0.0.1", port=PORT, debug=False)
