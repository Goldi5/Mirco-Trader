#!/usr/bin/env python3
"""Spec-Watchlist-Builder – 60+ spekulative Ticker automatisch scannen & bewerten."""
import json, os, sys, time
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "spec_watch.json")

# ─── Kuratierte Watchlist: Ticker → {kategorie, name, hebel} ─────
# Kategorien: index, crypto, lev-bull, lev-bear, inverse, volatility,
#             commodity, meme, ai, ev, biotech, space
WATCHLIST = {
    # 📊 Indizes / Makro
    "SPY":  {"kategorie": "index", "name": "SPDR S&P 500 ETF", "hebel": 0},
    "QQQ":  {"kategorie": "index", "name": "Invesco QQQ Trust (Nasdaq)", "hebel": 0},
    "IWM":  {"kategorie": "index", "name": "Russell 2000 ETF", "hebel": 0},
    "DIA":  {"kategorie": "index", "name": "Dow Jones Industrial Average ETF", "hebel": 0},
    "VTI":  {"kategorie": "index", "name": "Vanguard Total Stock Market", "hebel": 0},
    "VGK":  {"kategorie": "index", "name": "Vanguard FTSE Europe", "hebel": 0},
    "EEM":  {"kategorie": "index", "name": "iShares MSCI Emerging Markets", "hebel": 0},
    "TLT":  {"kategorie": "index", "name": "iShares 20+ Year Treasury Bond", "hebel": 0},
    # 3x Bull
    "SPXL": {"kategorie": "lev-bull", "name": "Direxion S&P500 Bull 3x", "hebel": 3},
    "TQQQ": {"kategorie": "lev-bull", "name": "ProShares UltraPro QQQ (3x)", "hebel": 3},
    "UDOW": {"kategorie": "lev-bull", "name": "ProShares UltraPro Dow30 (3x)", "hebel": 3},
    "URTY": {"kategorie": "lev-bull", "name": "ProShares UltraPro Russell2000 (3x)", "hebel": 3},
    "FAS":  {"kategorie": "lev-bull", "name": "Direxion Financial Bull 3x", "hebel": 3},
    "LABU": {"kategorie": "lev-bull", "name": "Direxion Biotech Bull 3x", "hebel": 3},
    "SOXL": {"kategorie": "lev-bull", "name": "Direxion Semiconductor Bull 3x", "hebel": 3},
    "TECL": {"kategorie": "lev-bull", "name": "Direxion Technology Bull 3x", "hebel": 3},
    "CURE": {"kategorie": "lev-bull", "name": "Direxion Healthcare Bull 3x", "hebel": 3},
    "RETL": {"kategorie": "lev-bull", "name": "Direxion Retail Bull 3x", "hebel": 3},
    # 3x Bear
    "SPXS": {"kategorie": "lev-bear", "name": "Direxion S&P500 Bear 3x", "hebel": -3},
    "SQQQ": {"kategorie": "lev-bear", "name": "ProShares UltraPro Short QQQ (3x)", "hebel": -3},
    "SDOW": {"kategorie": "lev-bear", "name": "ProShares UltraPro Short Dow30 (3x)", "hebel": -3},
    "SRTY": {"kategorie": "lev-bear", "name": "ProShares UltraPro Short Russell2000 (3x)", "hebel": -3},
    "FAZ":  {"kategorie": "lev-bear", "name": "Direxion Financial Bear 3x", "hebel": -3},
    "LABD": {"kategorie": "lev-bear", "name": "Direxion Biotech Bear 3x", "hebel": -3},
    "SOXS": {"kategorie": "lev-bear", "name": "Direxion Semiconductor Bear 3x", "hebel": -3},
    # Inverse
    "SH":   {"kategorie": "inverse", "name": "ProShares Short S&P500 (-1x)", "hebel": -1},
    "PSQ":  {"kategorie": "inverse", "name": "ProShares Short QQQ (-1x)", "hebel": -1},
    # 🌪️ Volatility
    "UVXY": {"kategorie": "volatility", "name": "ProShares Ultra VIX Short-Term", "hebel": 1.5},
    "VXX":  {"kategorie": "volatility", "name": "iPath Series B S&P500 VIX Short-Term", "hebel": 1},
    "SVXY": {"kategorie": "volatility", "name": "ProShares Short VIX Short-Term", "hebel": -0.5},
    "VIXY": {"kategorie": "volatility", "name": "ProShares VIX Mid-Term", "hebel": 1},
    # ₿ Crypto
    "IBIT":  {"kategorie": "crypto", "name": "iShares Bitcoin Trust", "hebel": 0},
    "FBTC":  {"kategorie": "crypto", "name": "Fidelity Wise Origin Bitcoin", "hebel": 0},
    "BITX":  {"kategorie": "crypto", "name": "2x Bitcoin Strategy ETF", "hebel": 2},
    "ETHA":  {"kategorie": "crypto", "name": "Ethereum Strategy ETF", "hebel": 0},
    "MSTR":  {"kategorie": "crypto", "name": "MicroStrategy (BTC-Treasury)", "hebel": 0},
    "COIN":  {"kategorie": "crypto", "name": "Coinbase Global", "hebel": 0},
    # 🛢️ Commodity
    "USO":  {"kategorie": "commodity", "name": "United States Oil Fund", "hebel": 0},
    "UNG":  {"kategorie": "commodity", "name": "United States Natural Gas", "hebel": 0},
    "GLD":  {"kategorie": "commodity", "name": "SPDR Gold Trust", "hebel": 0},
    "SLV":  {"kategorie": "commodity", "name": "iShares Silver Trust", "hebel": 0},
    "DBC":  {"kategorie": "commodity", "name": "Invesco DB Commodity Index", "hebel": 0},
    "COPX": {"kategorie": "commodity", "name": "Global X Copper Miners", "hebel": 0},
    "URA":  {"kategorie": "commodity", "name": "Global X Uranium ETF", "hebel": 0},
    # 🤖 AI
    "NVDA": {"kategorie": "ai", "name": "NVIDIA Corporation", "hebel": 0},
    "AMD":  {"kategorie": "ai", "name": "Advanced Micro Devices", "hebel": 0},
    "SMCI": {"kategorie": "ai", "name": "Super Micro Computer", "hebel": 0},
    "PLTR": {"kategorie": "ai", "name": "Palantir Technologies", "hebel": 0},
    "AI":   {"kategorie": "ai", "name": "C3.ai Inc.", "hebel": 0},
    "BOTZ": {"kategorie": "ai", "name": "Global X Robotics & AI ETF", "hebel": 0},
    # 🚗 EV
    "TSLA": {"kategorie": "ev", "name": "Tesla Inc.", "hebel": 0},
    "RIVN": {"kategorie": "ev", "name": "Rivian Automotive", "hebel": 0},
    "LCID": {"kategorie": "ev", "name": "Lucid Group", "hebel": 0},
    "NIO":  {"kategorie": "ev", "name": "NIO Inc.", "hebel": 0},
    # 🧬 Biotech
    "XBI":  {"kategorie": "biotech", "name": "SPDR S&P Biotech ETF", "hebel": 0},
    "IBB":  {"kategorie": "biotech", "name": "iShares Biotechnology ETF", "hebel": 0},
    # 🚀 Space
    "ARKX": {"kategorie": "space", "name": "ARK Space Exploration ETF", "hebel": 0},
    "RKLB": {"kategorie": "space", "name": "Rocket Lab USA", "hebel": 0},
    "LUNR": {"kategorie": "space", "name": "Intuitive Machines (Lunar)", "hebel": 0},
}

CACHE_FILE = os.path.join(BASE, ".spec_scan_cache.json")
CACHE_DURATION = 3600  # 1h Cache

def scan_spec_ticker(ticker):
    """Scannt einen Ticker und gibt strukturierte Daten zurück."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d", auto_adjust=True)
        if hist.empty or len(hist) < 2:
            # Fallback: längerer Zeitraum
            hist = t.history(period="1mo", interval="1d", auto_adjust=True)
        if hist.empty:
            return None

        close = hist["Close"].dropna()
        aktuell = float(close.iloc[-1])

        # 24h change
        if len(close) >= 2:
            tagesrendite = (aktuell / float(close.iloc[-2]) - 1) * 100
        else:
            tagesrendite = 0

        # 5-Tage change
        if len(close) >= 5:
            woche = (aktuell / float(close.iloc[-5]) - 1) * 100
        elif len(close) >= 2:
            woche = (aktuell / float(close.iloc[0]) - 1) * 100
        else:
            woche = 0

        # Volatilität (annualisiert, tägliche Returns)
        if len(close) > 5:
            daily_ret = close.pct_change().dropna()
            volatilitaet = float(daily_ret.std() * np.sqrt(252) * 100)
        else:
            volatilitaet = 0

        return {
            "aktuell": round(aktuell, 2),
            "tagesrendite": round(tagesrendite, 2),
            "woche": round(woche, 2),
            "volatilitaet": round(volatilitaet, 1),
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return None

def build_watchlist(force=False):
    """Baut die vollständige Watchlist mit Live-Daten."""
    cache = {}
    if os.path.exists(CACHE_FILE) and not force:
        try:
            age = time.time() - os.path.getmtime(CACHE_FILE)
            if age < CACHE_DURATION:
                with open(CACHE_FILE) as f:
                    cache = json.load(f)
        except:
            pass

    result = {}
    tickers = list(WATCHLIST.keys())
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        meta = WATCHLIST[ticker]
        # Check Cache
        if ticker in cache:
            data = cache[ticker]
        else:
            data = scan_spec_ticker(ticker)
            if data:
                cache[ticker] = data

        if not data:
            continue

        result[ticker] = {
            "name": meta["name"],
            "kategorie": meta["kategorie"],
            "hebel": meta["hebel"],
            **data,
        }

    # Cache speichern
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=1)

    # Ausgabe
    with open(OUT, "w") as f:
        json.dump(result, f, indent=2)

    print(f"✅ Spec-Watchlist: {len(result)}/{total} Ticker gescannt")
    print(f"   Kategorien: {set(v['kategorie'] for v in result.values())}")
    return result

# ─── Alte spek_depots basierend auf Watchlist befüllen ────────────
def init_spec_depots():
    """Erstellt initiale spec_depots/ aus der Watchlist (falls nicht vorhanden)."""
    sdd = os.path.join(BASE, "spec_depots")
    os.makedirs(sdd, exist_ok=True)

    # Nur Ticker ohne bestehendes Depot initialisieren
    tickers = list(WATCHLIST.keys())
    for ticker in tickers:
        pfad = os.path.join(sdd, f"{ticker}.json")
        if os.path.exists(pfad):
            continue
        meta = WATCHLIST[ticker]
        data = {
            "ticker": ticker,
            "name": meta["name"],
            "kategorie": meta["kategorie"],
            "hebel": meta["hebel"],
            "start": 100.0,
            "bargeld": 100.0,
            "shares": 0,
            "avg_price": 0,
            "trades": [],
            "historie": [],
            "erstellt": datetime.now().isoformat(),
        }
        with open(pfad, "w") as f:
            json.dump(data, f, indent=2)
    print(f"✅ Spec Depots initialisiert ({len(tickers)} Ticker)")

if __name__ == "__main__":
    force = "--force" in sys.argv
    init_spec_depots()
    build_watchlist(force=force)
