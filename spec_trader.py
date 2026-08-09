#!/usr/bin/env python3
"""Spec-Trader – KI-gestütztes Trading aller Spekulations-Instrumente.

Nutzt ki_decisions.py (LLM) für jede Trade-Entscheidung.
Jedes Instrument bekommt ein Depot mit 100$.
Daten kommen aus yfinance.
"""

import sys, os, json, time, math
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from spec_watch import WATCHLIST
from ki_decisions import entscheide_spec_batch

# Settings: max_spec_depots (begrenzt Anzahl aktiver Spec-Depots)
try:
    from settings_loader import depot_struktur
    _MAX_SPEC = int(depot_struktur("max_spec_depots", 60))
except Exception:
    _MAX_SPEC = 48

QUIET = "--quiet" in sys.argv

DEPOT_DIR = os.path.join(BASE, "spec_depots")
os.makedirs(DEPOT_DIR, exist_ok=True)


class SpecDepot:
    """Ein Depot für ein Spekulations-Instrument ($100 Start)."""
    def __init__(self, ticker, name="", kategorie=""):
        self.ticker = ticker
        self.name = name
        self.kategorie = kategorie
        self.bargeld = 100.0
        self.shares = 0.0
        self.avg_price = 0.0
        self.start = 100.0
        self.historie = []
        self.trades = []
        self.ki_letzte = None  # letzte KI-Entscheidung
        self.laden()

    def pfad(self):
        return os.path.join(DEPOT_DIR, "%s.json" % self.ticker.replace("/", "_").replace("^", ""))

    def laden(self):
        p = self.pfad()
        if os.path.exists(p):
            with open(p) as f:
                d = json.load(f)
            self.bargeld = d.get("bargeld", 100.0)
            self.shares = d.get("shares", 0.0)
            self.avg_price = d.get("avg_price", 0.0)
            self.start = d.get("start", 100.0)
            self.historie = d.get("historie", [])
            self.trades = d.get("trades", [])
            self.ki_letzte = d.get("ki_letzte")
            self.exchange = d.get("exchange")

    def speichern(self):
        p = self.pfad()
        with open(p, "w") as f:
            json.dump({
                "ticker": self.ticker,
                "name": self.name,
                "kategorie": self.kategorie,
                "bargeld": round(self.bargeld, 2),
                "shares": round(self.shares, 6),
                "avg_price": round(self.avg_price, 4),
                "start": self.start,
                "exchange": getattr(self, "exchange", None),
                "historie": self.historie[-100:],
                "trades": self.trades[-50:],
                "ki_letzte": self.ki_letzte,
                "tenant_id": int(getattr(self, "tenant_id", 1) or 1),  # PHASE 3 §2.3
            }, f, indent=2, ensure_ascii=False)

    def wert(self, force_price=None):
        if force_price is not None and self.shares > 0:
            return self.bargeld + self.shares * force_price
        return self.bargeld


def fetch_analyse():
    """Holt Kursdaten + Indikatoren fuer alle Instrumente.
    v2.16.10: Super-Mix-Fallback — wenn yfinance im Batch einen Ticker
    auslaesst (Flakiness), einzeln via marktdaten.hole_kurs() nachholen.
    """
    tickers = list(WATCHLIST.keys())
    # Settings: max_spec_depots begrenzen (aber nie weniger als WATCHLIST-Laenge)
    _limit = max(_MAX_SPEC, len(tickers))
    if len(tickers) > _limit:
        tickers = tickers[:_limit]

    # Import fuer Super-Mix-Fallback
    try:
        from marktdaten import hole_kurs as _mix_kurs
        _has_mix = True
    except Exception:
        _has_mix = False

    # Batch-Download via yfinance
    try:
        daten = yf.download(tickers, period="3mo", interval="1d", progress=False, auto_adjust=True, timeout=60)
    except Exception:
        daten = pd.DataFrame()
    # Wenn Batch komplett leer/fehlgeschlagen -> direkt zu marktdaten-Fallback
    if daten is None or daten.empty:
        try:
            from marktdaten import hole_kurs as _mix_kurs
            _mix_ok = True
        except Exception:
            _mix_ok = False
        if _mix_ok:
            print("  ⚡ yfinance Batch fehlgeschlagen -> marktdaten-Fallback für alle", flush=True)
            ergebnis = {}
            for ticker in tickers:
                p = _mix_kurs(ticker)
                if p and p > 0:
                    ergebnis[ticker] = p
            # ergebnis enthaelt nur Kurse; fetch_analyse baut daraus Indikatoren
            if ergebnis:
                return _aus_kursen_aufbauen(ergebnis, tickers)
    ist_multi = isinstance(daten.columns, pd.MultiIndex) if not daten.empty else False
    ergebnis = {}

    # v2.16.10: Fehlende Ticker nach Batch-Download explizit nachholen
    gefunden = set()
    if ist_multi and 'Close' in daten.columns:
        gefunden = set(daten['Close'].columns)
    elif not ist_multi and 'Close' in daten.columns:
        gefunden = set(tickers)  # single-column: alle da
    fehlende = [t for t in tickers if t not in gefunden]

    for ticker in tickers:
        try:
            if ist_multi:
                close = daten['Close'][ticker].dropna() if 'Close' in daten and ticker in daten['Close'] else None
            else:
                close = daten['Close'].dropna() if 'Close' in daten.columns else None

            # Fallback: yfinance single-download wenn Batch fehlschlaegt
            if close is None or len(close) < 50:
                # Single-Download Fallback (yfinance)
                try:
                    sd = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True, timeout=30)
                    if 'Close' in sd.columns:
                        close = sd['Close'].dropna()
                except Exception:
                    close = None

            # Fallback: marktdaten.hole_kurs() (4-Tier) fuer aktuellen Kurs
            if (close is None or len(close) < 50) and _has_mix:
                preis = _mix_kurs(ticker)
                if preis and preis > 0:
                    # Minimal-Daten aus aktuellem Kurs + sma20/50 Schaetzung
                    close = pd.Series([preis] * 60)
                    print(f"  ⚡ {ticker}: Super-Mix-Fallback (Kurs ${preis:.2f})", flush=True)

            if close is None or len(close) < 50:
                continue

            # ATR (14) + Volume-Ratio aus den vorhandenen Daten
            atr_pct = None
            vol_ratio = None
            try:
                if ist_multi:
                    high = daten['High'][ticker].dropna() if 'High' in daten and ticker in daten['High'] else None
                    low = daten['Low'][ticker].dropna() if 'Low' in daten and ticker in daten['Low'] else None
                    vol = daten['Volume'][ticker].dropna() if 'Volume' in daten and ticker in daten['Volume'] else None
                else:
                    high = daten['High'].dropna() if 'High' in daten else None
                    low = daten['Low'].dropna() if 'Low' in daten else None
                    vol = daten['Volume'].dropna() if 'Volume' in daten else None
                if high is not None and low is not None and len(high) > 14:
                    tr = pd.concat([high - low, (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
                    atr = float(tr.tail(14).mean())
                    aktuell_f = float(close.iloc[-1])
                    atr_pct = round(atr / aktuell_f * 100, 2) if aktuell_f else None
                if vol is not None and len(vol) > 20:
                    vol_avg = float(vol.tail(20).mean())
                    vol_ratio = round(float(vol.iloc[-1]) / vol_avg, 2) if vol_avg > 0 else None
            except Exception:
                pass

            aktuell = float(close.iloc[-1])
            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1])

            # RSI (robust gegen NaN/Edge-Cases, v2.16.10)
            try:
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi_val = (100 - (100 / (1 + rs))).iloc[-1]
                rsi = float(rsi_val) if not pd.isna(rsi_val) else 50.0
            except Exception:
                rsi = 50.0

            # Trend
            if aktuell > sma20 > sma50:
                uptrend = 1
            elif aktuell < sma20 < sma50:
                uptrend = 0
            else:
                uptrend = 0.5

            ergebnis[ticker] = {
                "aktuell": round(aktuell, 2),
                "sma20": round(sma20, 2),
                "sma50": round(sma50, 2),
                "uptrend": uptrend,
                "rsi": round(rsi, 1),
                "atr_pct": atr_pct,
                "vol_ratio": vol_ratio,
                "name": WATCHLIST[ticker]["name"],
                "kat": WATCHLIST[ticker]["kat"],
            }
        except Exception as e:
            if not QUIET:
                print(f"  ⚠ {ticker}: {e}", flush=True)
    return ergebnis


def _aus_kursen_aufbauen(kurse, tickers):
    """Minimal-Fallback: aus {ticker: preis} ein ergebnis-Dict bauen.
    yfinance ist komplett ausgefallen -> marktdaten.hole_kurs() liefert
    nur aktuelle Kurse, keine Historie. sma20/sma50 = Kurs (flat),
    uptrend=0.5, rsi=50 (neutral). Besser als gar keine Daten.
    """
    ergebnis = {}
    for ticker in tickers:
        preis = kurse.get(ticker)
        if not preis or preis <= 0:
            continue
        info = WATCHLIST.get(ticker, {})
        ergebnis[ticker] = {
            "aktuell": round(float(preis), 2),
            "sma20": round(float(preis), 2),
            "sma50": round(float(preis), 2),
            "uptrend": 0.5,
            "rsi": 50.0,
            "atr_pct": None,
            "vol_ratio": None,
            "name": info.get("name", ticker),
            "kat": info.get("kat", ""),
        }
    print(f"  ⚡ marktdaten-Fallback lieferte {len(ergebnis)} Kurse", flush=True)
    return ergebnis


# ─── KI-Ausführung ──────────────────────────────────────────
def ausführen(depot, kurs, ki_entscheidung):
    """Führt die KI-Entscheidung aus."""
    if not ki_entscheidung:
        return
    
    aktion = ki_entscheidung.get("aktion", "halten")
    konfidenz = ki_entscheidung.get("konfidenz", 50)
    grund = ki_entscheidung.get("grund", "")
    
    if konfidenz < 40:
        if not QUIET:
            print(f"   [{depot.ticker}] ⚪ KI unsicher (K:{konfidenz}) – halte", flush=True)
        return
    
    if aktion == "kaufen" and depot.bargeld > 1.0 and kurs > 0:
        menge_faktor = {"voll": 1.0, "teil": 0.5, "minimal": 0.2}
        menge = ki_entscheidung.get("menge", "voll")
        faktor = menge_faktor.get(menge, 0.5)
        
        invest = depot.bargeld * faktor
        shares = invest / kurs
        
        # Penny-Stock-Filter (ausser für Hebelticker)
        if kurs < 1.0 and "3x" not in depot.name and "2x" not in depot.name:
            if not QUIET:
                print(f"   [{depot.ticker}] ⚠ Penny-Stock übersprungen (${kurs:.2f})", flush=True)
            return
        
        depot.shares += shares
        depot.avg_price = ((depot.avg_price * (depot.shares - shares)) + (shares * kurs)) / depot.shares if depot.shares > 0 else kurs
        depot.bargeld -= shares * kurs
        
        depot.trades.append({
            "zeit": datetime.now().isoformat(),
            "aktion": "kaufen", "menge": round(shares, 6),
            "preis": round(kurs, 4), "grund": grund,
            "ki_konfidenz": konfidenz,
        })
        # Börse als Metadatum (für Marktzeiten-Skipping)
        try:
            from boersen import boerse_fuer_ticker
            depot.exchange = boerse_fuer_ticker(depot.ticker)
        except Exception:
            depot.exchange = None
        if not QUIET:
            print(f"   [{depot.ticker}] 🟢 KI-Kauf {shares:.4f}st @${kurs:.2f} – {grund[:50]} (K:{konfidenz})", flush=True)
    
    elif aktion == "verkaufen" and depot.shares > 0:
        menge_faktor = {"voll": 1.0, "teil": 0.5, "minimal": 0.2}
        menge = ki_entscheidung.get("menge", "voll")
        faktor = menge_faktor.get(menge, 1.0)
        
        shares_verkauf = depot.shares * faktor
        erlös = shares_verkauf * kurs
        depot.bargeld += erlös
        depot.shares -= shares_verkauf
        
        if depot.shares < 0.000001:
            depot.shares = 0
            depot.avg_price = 0
        
        depot.trades.append({
            "zeit": datetime.now().isoformat(),
            "aktion": "verkaufen", "menge": round(shares_verkauf, 6),
            "preis": round(kurs, 4), "grund": grund,
            "ki_konfidenz": konfidenz,
        })
        if not QUIET:
            print(f"   [{depot.ticker}] 🔴 KI-Verkauf {shares_verkauf:.4f}st @${kurs:.2f} – {grund[:50]} (K:{konfidenz})", flush=True)
    
    # Historie aktualisieren
    wert = depot.wert(force_price=kurs)
    depot.historie.append({"zeit": datetime.now().isoformat(), "wert": round(wert, 2)})


def main():
    if not QUIET:
        print(" 🔥 Spekulation-Trader (KI-gestützt) – %d Instrumente" % len(WATCHLIST), flush=True)
    
    daten = fetch_analyse()
    if not QUIET:
        print("   Daten: %d Instrumente" % len(daten), flush=True)
    
    # KI-Daten pro Ticker sammeln
    ticker_data = []
    try:
        from boersen import ist_offen, boerse_fuer_ticker
        def ticker_markt_status(t):
            b = boerse_fuer_ticker(t)
            return "open" if ist_offen(b) else "closed"
    except Exception:
        def ticker_markt_status(t):
            return "open"
    for ticker, info in sorted(daten.items()):
        depot = SpecDepot(ticker, info["name"], info.get("kat", ""))
        ticker_data.append({
            "ticker": ticker,
            "name": info["name"],
            "kurs": info["aktuell"],
            "sma20": info["sma20"],
            "sma50": info["sma50"],
            "rsi": info["rsi"],
            "shares": depot.shares,
            "avg_price": depot.avg_price,
            "bargeld": depot.bargeld,
            "start": depot.start,
            "markt": ticker_markt_status(ticker),
            "sektor": info.get("kat", ""),
            "atr_pct": info.get("atr_pct"),
            "vol_ratio": info.get("vol_ratio"),
        })

    # ── WELLEN-MODUS: Slice der Ticker (Rate-Limit-Schonung) ──
    # --welle N (0..3): verarbeite nur Ticker[N*13:(N+1)*13] -> ~13 Calls/Lauf
    # statt 49 auf einmal. Über 4 Wellen (Scheduler 30min-Takt) alle abgedeckt.
    if "--welle" in sys.argv:
        try:
            welle = int(sys.argv[sys.argv.index("--welle") + 1])
        except Exception:
            welle = 0
        slice_size = 13
        start = welle * slice_size
        ende = start + slice_size
        ticker_data = ticker_data[start:ende]
        if not QUIET:
            print("   🌊 Welle %d: Ticker %d-%d von %d" % (welle, start, ende, len(daten)), flush=True)

    # KI-Entscheidungen einholen (parallel)
    if not QUIET:
        print("   🤖 KI analysiert %d Ticker..." % len(ticker_data), flush=True)
    ki_ergebnisse = entscheide_spec_batch(ticker_data, max_workers=8)
    if not QUIET:
        anzahl = sum(1 for e in ki_ergebnisse if e.get("aktion") != "halten")
        print("   KI: %d Entscheidungen (davon %d non-Hold)" % (len(ki_ergebnisse), anzahl), flush=True)
    
    # Entscheidungen ausführen
    ergebnisse = []
    for i, ticker_info in enumerate(ticker_data):
        ticker = ticker_info["ticker"]
        info = daten[ticker]
        depot = SpecDepot(ticker, info["name"], info.get("kat", ""))
        depot.ki_letzte = ki_ergebnisse[i]
        
        if ki_ergebnisse[i]:
            ausführen(depot, info["aktuell"], ki_ergebnisse[i])
        
        depot.speichern()
        
        wert = depot.wert(force_price=info["aktuell"])
        rendite = (wert / depot.start - 1) * 100
        ergebnisse.append((ticker, wert, rendite, depot.shares, len(depot.trades)))
    
    if not QUIET:
        print("\n   Ergebnisse:")
        for ticker, wert, rendite, shares, trades in ergebnisse:
            farbe = "🟢" if rendite > 0 else ("🔴" if rendite < -0.5 else "⚪")
            kat = WATCHLIST[ticker]["kat"] if ticker in WATCHLIST else ""
            print(" %s %-5s $%6.2f %+7.2f%% %5.2f %5d %s" % (farbe, ticker, wert, rendite, shares, trades, kat), flush=True)

    # Status speichern
    try:
        from trader_status import update_status
        ki_anzahl = 0
        for t in os.listdir(os.path.join(BASE, "spec_depots")):
            if t.endswith(".json"):
                try:
                    with open(os.path.join(BASE, "spec_depots", t), encoding="utf-8") as f:
                        d = json.load(f)
                    if d.get("start", 0) > 0:
                        ki_anzahl += 1
                except Exception:
                    pass
        update_status("spec_trader", {"depots": ki_anzahl})
    except Exception as e:
        if not QUIET:
            print(f"⚠ Status-Fehler: {e}", file=sys.stderr)

    # System-Log
    try:
        from system_log import log_eintrag
        log_eintrag("spec", f"Spec-Lauf: {ki_anzahl} Depots analysiert", "ok")
    except Exception:
        pass


if __name__ == "__main__":
    main()
