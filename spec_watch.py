#!/usr/bin/env python3
"""
Spekulation-Watch – sammelt täglich Daten zu:
  - Crypto-ETFs (IBIT, ETHA, BITO)
  - Inverse ETFs (SQQQ, SPXS)
  - Volatility (UVXY, VIXY)
  - Leveraged Commodity (JNUG, BOIL, NRGU)
  
Rein passiv – kein Handel, nur Daten + Auswertung.
"""
import sys, os, json, time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import yfinance as yf
import pandas as pd
import numpy as np

# ─── Beobachtete Instrumente ─────────────────────────────────
WATCHLIST = {
    # Crypto-ETFs
    "IBIT":  {"name": "iShares Bitcoin Trust",   "kat": "crypto",     "hebel": 1},
    "ETHA":  {"name": "Ethereum Trust",           "kat": "crypto",     "hebel": 1},
    "BITO":  {"name": "ProShares Bitcoin Strat.", "kat": "crypto",     "hebel": 1},
    # Inverse (3x Bear)
    "SQQQ":  {"name": "ProShares UltraPro Short QQQ","kat": "inverse", "hebel": -3},
    "SPXS":  {"name": "Direxion S&P 500 Bear 3x","kat": "inverse",     "hebel": -3},
    # Volatility
    "UVXY":  {"name": "ProShares Ultra VIX ST Futures","kat":"volatility","hebel": 1.5},
    "VIXY":  {"name": "ProShares VIX ST Futures","kat": "volatility",  "hebel": 1},
    "VXX":   {"name": "Barclays VIX ST ETN",      "kat": "volatility", "hebel": 1},
    "SVXY":  {"name": "ProShares Short VIX ST",   "kat": "volatility", "hebel": -1},
    # Commodity Leveraged
    "JNUG":  {"name": "Direxion Gold Miners 2x",  "kat": "commodity",  "hebel": 2},
    "BOIL":  {"name": "ProShares Ultra NatGas 2x","kat": "commodity",  "hebel": 2},
    "NRGU":  {"name": "MicroSectors FANG+ 3x",    "kat": "commodity",  "hebel": 3},
    "UCO":   {"name": "ProShares Ultra Crude 2x", "kat": "commodity",  "hebel": 2},
    "SCO":   {"name": "ProShares UltraShort Crude","kat":"commodity",  "hebel": -2},
    "KOLD":  {"name": "ProShares UltraShort NatGas","kat":"commodity", "hebel": -2},
    # Leveraged Bull (3x)
    "TQQQ":  {"name": "ProShares UltraPro QQQ 3x","kat": "lev-bull",   "hebel": 3},
    "FAS":   {"name": "Direxion Financial Bull 3x","kat": "lev-bull",  "hebel": 3},
    "FNGU":  {"name": "MicroSectors FANG+ 3x",    "kat": "lev-bull",  "hebel": 3},
    "LABU":  {"name": "Direxion Biotech Bull 3x", "kat": "lev-bull",  "hebel": 3},
    "UPRO":  {"name": "ProShares S&P500 Bull 3x", "kat": "lev-bull",  "hebel": 3},
    "TNA":   {"name": "Direxion SmallCap Bull 3x","kat": "lev-bull",  "hebel": 3},
    # Leveraged Bear (inverse)
    "SPXU":  {"name": "ProShares S&P500 Bear 3x", "kat": "lev-bear",  "hebel": -3},
    "SOXS":  {"name": "Direxion Semi Bear 3x",    "kat": "lev-bear",  "hebel": -3},
    "FAZ":   {"name": "Direxion Financial Bear 3x","kat": "lev-bear", "hebel": -3},
    "JDST":  {"name": "Direxion Gold Miners Bear 2x","kat":"lev-bear","hebel": -2},
    # Meme Stocks
    "GME":   {"name": "GameStop Corp.",            "kat": "meme",      "hebel": 1},
    "AMC":   {"name": "AMC Entertainment",         "kat": "meme",      "hebel": 1},
    "BB":    {"name": "BlackBerry Ltd.",           "kat": "meme",      "hebel": 1},
    # Krypto-Exposed
    "MSTR":  {"name": "MicroStrategy Inc.",        "kat": "crypto",    "hebel": 1},
    "COIN":  {"name": "Coinbase Global",           "kat": "crypto",    "hebel": 1},
    "MARA":  {"name": "Mara Holdings",             "kat": "crypto",    "hebel": 1},
    "RIOT":  {"name": "Riot Platforms",            "kat": "crypto",    "hebel": 1},
    # AI / Tech Spekulation
    "IONQ":  {"name": "IonQ Inc.",                 "kat": "ai",        "hebel": 1},
    "RGTI":  {"name": "Rigetti Computing",         "kat": "ai",        "hebel": 1},
    "SOUN":  {"name": "SoundHound AI",             "kat": "ai",        "hebel": 1},
    "BBAI":  {"name": "BigBear.ai Holdings",       "kat": "ai",        "hebel": 1},
    "PLTR":  {"name": "Palantir Technologies",     "kat": "ai",        "hebel": 1},
    # EV / E-Mobility
    "RIVN":  {"name": "Rivian Automotive",         "kat": "ev",        "hebel": 1},
    "QS":    {"name": "QuantumScape Corp.",         "kat": "ev",        "hebel": 1},
    "JOBY":  {"name": "Joby Aviation Inc.",         "kat": "ev",        "hebel": 1},
    # Biotech
    "CRSP":  {"name": "CRISPR Therapeutics",       "kat": "biotech",   "hebel": 1},
    "MRNA":  {"name": "Moderna Inc.",              "kat": "biotech",   "hebel": 1},
    "MNMD":  {"name": "Mind Medicine Inc.",        "kat": "biotech",   "hebel": 1},
    # Crypto 2x ETFs
    "BITX":  {"name": "Volatility Bitcoin 2x",     "kat": "crypto",    "hebel": 2},
    "ETHU":  {"name": "Volatility Ether 2x",       "kat": "crypto",    "hebel": 2},
    # Space
    "RKLB":  {"name": "Rocket Lab USA",            "kat": "space",     "hebel": 1},
    "ASTS":  {"name": "AST SpaceMobile",           "kat": "space",     "hebel": 1},
    # Vergleichsindex
    "SPY":   {"name": "SPDR S&P 500 ETF",          "kat": "index",     "hebel": 1},
    "QQQ":   {"name": "Invesco QQQ Trust",         "kat": "index",     "hebel": 1},
    # ─── Erweiterung v2.19.7: mehr Masse für Spec-Diversifikation ───
    # Krypto (Einzelaktien + ETFs)
    "MSTX":  {"name": "Defiance Daily 2x MSTR",    "kat": "crypto",    "hebel": 2},
    "MSTR2": {"name": "T-Rex 2x MSTR",             "kat": "crypto",    "hebel": 2},
    "CONL":  {"name": "GraniteShares 2x COIN",     "kat": "crypto",    "hebel": 2},
    "GBTC":  {"name": "Grayscale Bitcoin",         "kat": "crypto",    "hebel": 1},
    "ETHE":  {"name": "Grayscale Ethereum",        "kat": "crypto",    "hebel": 1},
    "BITY":  {"name": "GraniteShares BTC Income",  "kat": "crypto",    "hebel": 1},
    "ARKB":  {"name": "ARK 21Shares BTC",          "kat": "crypto",    "hebel": 1},
    "CLSK":  {"name": "CleanSpark Inc.",           "kat": "crypto",    "hebel": 1},
    "HUT":   {"name": "Hut 8 Mining",              "kat": "crypto",    "hebel": 1},
    "BITF":  {"name": "Bitfarms Ltd.",             "kat": "crypto",    "hebel": 1},
    "CAN":   {"name": "Canaan Inc.",               "kat": "crypto",    "hebel": 1},
    "RIOT2":{"name": "Riot Platforms (Spec)",      "kat": "crypto",    "hebel": 1},
    "TSHA":  {"name": "Tesla Short TSLA",          "kat": "crypto",    "hebel": -1},
    # Leveraged Bull (3x) weitere Sektoren
    "SOXL":  {"name": "Direxion Semi Bull 3x",     "kat": "lev-bull",  "hebel": 3},
    "TECL":  {"name": "Direxion Tech Bull 3x",     "kat": "lev-bull",  "hebel": 3},
    "TYD":   {"name": "Direxion 10Y Treasury 3x",  "kat": "lev-bull",  "hebel": 3},
    "UDOW":  {"name": "ProShares Dow30 Bull 3x",   "kat": "lev-bull",  "hebel": 3},
    "QLD":   {"name": "ProShares QQQ Bull 2x",     "kat": "lev-bull",  "hebel": 2},
    "SSO":   {"name": "ProShares S&P Bull 2x",     "kat": "lev-bull",  "hebel": 2},
    "ROM":   {"name": "ProShares Tech Bull 2x",    "kat": "lev-bull",  "hebel": 2},
    "DDM":   {"name": "ProShares Dow Bull 2x",     "kat": "lev-bull",  "hebel": 2},
    "MVV":   {"name": "ProShares MidCap Bull 2x",  "kat": "lev-bull",  "hebel": 2},
    "UWM":   {"name": "ProShares Russell Bull 2x", "kat": "lev-bull",  "hebel": 2},
    "RXL":   {"name": "ProShares HealthCare Bull 2x","kat":"lev-bull", "hebel": 2},
    "UXI":   {"name": "ProShares Industrials 2x",  "kat": "lev-bull",  "hebel": 2},
    "UGE":   {"name": "ProShares Consumer Bull 2x","kat": "lev-bull",  "hebel": 2},
    "UPW":   {"name": "ProShares Utilities 2x",    "kat": "lev-bull",  "hebel": 2},
    # Leveraged Bear (3x) weitere Sektoren
    "SDS":   {"name": "ProShares S&P Bear 2x",     "kat": "lev-bear",  "hebel": -2},
    "QID":   {"name": "ProShares QQQ Bear 2x",     "kat": "lev-bear",  "hebel": -2},
    "SH":    {"name": "ProShares S&P Short",       "kat": "lev-bear",  "hebel": -1},
    "PSQ":   {"name": "ProShares QQQ Short",       "kat": "lev-bear",  "hebel": -1},
    "DOG":   {"name": "ProShares Dow Short",       "kat": "lev-bear",  "hebel": -1},
    "RWM":   {"name": "ProShares Russell Short",   "kat": "lev-bear",  "hebel": -1},
    "REK":   {"name": "ProShares RealEstate Short","kat": "lev-bear",  "hebel": -1},
    "SZK":   {"name": "ProShares Financial Short", "kat": "lev-bear",  "hebel": -1},
    "CCX":   {"name": "ProShares CommSvc Short",   "kat": "lev-bear",  "hebel": -1},
    "SBB":   {"name": "ProShares SmallCap Short", "kat": "lev-bear",  "hebel": -1},
    # Volatility weitere
    "VIXM":  {"name": "ProShares VIX Mid-Term",    "kat": "volatility", "hebel": 1},
    "ZIVB":  {"name": "Volatility Mid-Term",       "kat": "volatility", "hebel": 1},
    "VXZ":   {"name": "iPath VIX Mid-Term",       "kat": "volatility", "hebel": 1},
    "UVIX":  {"name": "Volatility VIX 2x",         "kat": "volatility", "hebel": 2},
    "SVIX":  {"name": "Volatility VIX Short 1x",   "kat": "volatility", "hebel": -1},
    # Commodity Leveraged weitere
    "DGP":   {"name": "DB Gold Double Long",       "kat": "commodity",  "hebel": 2},
    "UGL":   {"name": "ProShares Ultra Gold 2x",   "kat": "commodity",  "hebel": 2},
    "GLL":   {"name": "ProShares UltraShort Gold","kat":"commodity",   "hebel": -2},
    "AGQ":   {"name": "ProShares Ultra Silver 2x", "kat": "commodity", "hebel": 2},
    "ZSL":   {"name": "ProShares UltraShort Silv", "kat": "commodity", "hebel": -2},
    "CORN":  {"name": "Teucrium Corn Fund",        "kat": "commodity",  "hebel": 1},
    "SOYB":  {"name": "Teucrium Soybean Fund",     "kat": "commodity",  "hebel": 1},
    "WEAT":  {"name": "Teucrium Wheat Fund",       "kat": "commodity",  "hebel": 1},
    "UNG":   {"name": "US NatGas Fund",            "kat": "commodity",  "hebel": 1},
    "DBO":   {"name": "DB Oil Fund",               "kat": "commodity",  "hebel": 1},
    "BAL":   {"name": "iPath Cotton",              "kat": "commodity",  "hebel": 1},
    "JO":    {"name": "iPath Coffee",              "kat": "commodity",  "hebel": 1},
    "NIB":   {"name": "iPath Cocoa",               "kat": "commodity",  "hebel": 1},
    "CANE":  {"name": "Teucrium Sugar Fund",       "kat": "commodity",  "hebel": 1},
    # AI / Tech Spekulation erweitert
    "NVDA":  {"name": "NVIDIA Corp.",              "kat": "ai",        "hebel": 1},
    "AMD":   {"name": "Advanced Micro Dev.",       "kat": "ai",        "hebel": 1},
    "SMCI":  {"name": "Super Micro Computer",      "kat": "ai",        "hebel": 1},
    "SNOW":  {"name": "Snowflake Inc.",            "kat": "ai",        "hebel": 1},
    "PATH":  {"name": "UiPath Inc.",               "kat": "ai",        "hebel": 1},
    "AI":    {"name": "C3.ai Inc.",                "kat": "ai",        "hebel": 1},
    "PLUG":  {"name": "Plug Power Inc.",           "kat": "ai",        "hebel": 1},
    "C3AI":  {"name": "C3.ai (Spec)",             "kat": "ai",        "hebel": 1},
    "AVAV":  {"name": "AeroVironment Inc.",        "kat": "ai",        "hebel": 1},
    "UAVS":  {"name": "Drone Aviation",            "kat": "ai",        "hebel": 1},
    # EV / E-Mobility erweitert
    "TSLA":  {"name": "Tesla Inc.",                "kat": "ev",        "hebel": 1},
    "NIO":   {"name": "NIO Inc.",                  "kat": "ev",        "hebel": 1},
    "LCID":  {"name": "Lucid Group",               "kat": "ev",        "hebel": 1},
    "NKLA":  {"name": "Nikola Corp.",              "kat": "ev",        "hebel": 1},
    "XPEV":  {"name": "XPeng Inc.",                "kat": "ev",        "hebel": 1},
    "FSR":   {"name": "Fisker Inc.",               "kat": "ev",        "hebel": 1},
    "CHPT":  {"name": "ChargePoint Hold.",         "kat": "ev",        "hebel": 1},
    "BLNK":  {"name": "Blink Charging",            "kat": "ev",        "hebel": 1},
    "GOEV":  {"name": "Canoo Inc.",                "kat": "ev",        "hebel": 1},
    "WKHS":  {"name": "Workhorse Group",           "kat": "ev",        "hebel": 1},
    # Biotech erweitert
    "NVAX":  {"name": "Novavax Inc.",              "kat": "biotech",   "hebel": 1},
    "IBRX":  {"name": "ImmunityBio Inc.",          "kat": "biotech",   "hebel": 1},
    "VERU":  {"name": "Veru Inc.",                 "kat": "biotech",   "hebel": 1},
    "SGMO":  {"name": "Sangamo Therapy",           "kat": "biotech",   "hebel": 1},
    "VIR":   {"name": "Vir Biotechnology",         "kat": "biotech",   "hebel": 1},
    "DNA":   {"name": "Ginkgo Bioworks",           "kat": "biotech",   "hebel": 1},
    "BNTX":  {"name": "BioNTech SE",               "kat": "biotech",   "hebel": 1},
    "SAVA":  {"name": "Cassava Sciences",          "kat": "biotech",   "hebel": 1},
    # Meme / Turnaround erweitert
    "KOSS":  {"name": "Koss Corp.",                "kat": "meme",      "hebel": 1},
    "BBBY":  {"name": "Bed Bath (Spec)",           "kat": "meme",      "hebel": 1},
    "CLOV":  {"name": "Clover Health",             "kat": "meme",      "hebel": 1},
    "WISH":  {"name": "ContextLogic",              "kat": "meme",      "hebel": 1},
    "XL":    {"name": "XL Fleet",                  "kat": "meme",      "hebel": 1},
    "SNDL":  {"name": "Sundial Growers",           "kat": "meme",      "hebel": 1},
    "TLRY":  {"name": "Tilray Brands",             "kat": "meme",      "hebel": 1},
    "AYTU":  {"name": "AYTU BioScience",           "kat": "meme",      "hebel": 1},
    # Space erweitert
    "SPCE":  {"name": "Virgin Galactic",           "kat": "space",     "hebel": 1},
    "MAXR":  {"name": "Maxar Technologies",        "kat": "space",     "hebel": 1},
    "RDW":   {"name": "Redwire Corp.",              "kat": "space",     "hebel": 1},
    "BKSY":  {"name": "BlackSky Tech",             "kat": "space",     "hebel": 1},
    "IRDM":  {"name": "Iridium Comm.",             "kat": "space",     "hebel": 1},
    "SATL":  {"name": "Satellogic",                "kat": "space",     "hebel": 1},
    # Fintech / Payment Spekulation
    "SOFI":  {"name": "SoFi Technologies",         "kat": "fintech",   "hebel": 1},
    "AFRM":  {"name": "Affirm Holdings",           "kat": "fintech",   "hebel": 1},
    "UPST":  {"name": "Upstart Holdings",          "kat": "fintech",   "hebel": 1},
    "HOOD":  {"name": "Robinhood Markets",         "kat": "fintech",   "hebel": 1},
    "PYPL":  {"name": "PayPal Holdings",           "kat": "fintech",   "hebel": 1},
    "SQ":    {"name": "Block Inc.",                "kat": "fintech",   "hebel": 1},
    # Retail / Consumer Spekulation
    "ETSY":  {"name": "Etsy Inc.",                 "kat": "retail",    "hebel": 1},
    "CHWY":  {"name": "Chewy Inc.",                "kat": "retail",    "hebel": 1},
    "FVRR":  {"name": "Fiverr Intl.",              "kat": "retail",    "hebel": 1},
    "DXCM":  {"name": "DexCom Inc.",               "kat": "retail",    "hebel": 1},
    "SHOP":  {"name": "Shopify Inc.",              "kat": "retail",    "hebel": 1},
    # Energy / CleanTech Spekulation
    "ENPH":  {"name": "Enphase Energy",            "kat": "energy",    "hebel": 1},
    "FSLR":  {"name": "First Solar",               "kat": "energy",    "hebel": 1},
    "PLUG2":{"name": "Plug Power (Spec)",          "kat": "energy",    "hebel": 1},
    "RUN":   {"name": "Sunrun Inc.",               "kat": "energy",    "hebel": 1},
    "NEE":   {"name": "NextEra Energy",            "kat": "energy",    "hebel": 1},
    "BE":    {"name": "Bloom Energy",              "kat": "energy",    "hebel": 1},
    # Gaming / Metaverse Spekulation
    "RBLX":  {"name": "Roblox Corp.",              "kat": "gaming",    "hebel": 1},
    "U":     {"name": "Unity Software",            "kat": "gaming",    "hebel": 1},
    "GME2":  {"name": "GameStop (Spec2)",          "kat": "gaming",    "hebel": 1},
    "ATVI":  {"name": "Activision (Spec)",         "kat": "gaming",    "hebel": 1},
    "EA":    {"name": "Electronic Arts",           "kat": "gaming",    "hebel": 1},
    # Cannabis Spekulation
    "CGC":   {"name": "Canopy Growth",             "kat": "cannabis",  "hebel": 1},
    "ACB":   {"name": "Aurora Cannabis",           "kat": "cannabis",  "hebel": 1},
    "CRLBF": {"name": "Cresco Labs",               "kat": "cannabis",  "hebel": 1},
    "GTBIF": {"name": "Green Thumb Ind.",          "kat": "cannabis",  "hebel": 1},
    "MSOS":  {"name": "AdvisorShares MSOS",        "kat": "cannabis",  "hebel": 1},
}

CACHE_FILE = os.path.join(BASE, ".spec_cache.json")
LOG_FILE = os.path.join(BASE, "spec_log.json")

def fetch_and_analyze():
    """Holt Daten für alle Watchlist-Instrumente, berechnet Metriken."""
    ticker_list = list(WATCHLIST.keys())
    
    daten = yf.download(ticker_list, period="6mo", interval="1d", 
                        progress=False, auto_adjust=True)
    
    ist_multi = isinstance(daten.columns, pd.MultiIndex)
    
    ergebnis = {}
    now = datetime.now()
    
    for ticker in ticker_list:
        meta = WATCHLIST[ticker]
        try:
            if ist_multi:
                # yfinance MultiIndex: (Attribut, Ticker) — z.B. ('Close', 'IBIT')
                close = daten['Close'][ticker].dropna() if 'Close' in daten and ticker in daten['Close'] else None
                vol = daten['Volume'][ticker].dropna() if 'Volume' in daten and ticker in daten['Volume'] else None
            else:
                close = daten['Close'].dropna() if 'Close' in daten else None
                vol = daten['Volume'].dropna() if 'Volume' in daten else None
        except:
            # Fallback: Ticker einzeln
            try:
                t = yf.Ticker(ticker)
                h = t.history(period="6mo")
                close = h['Close'].dropna() if 'Close' in h else None
                vol = h['Volume'].dropna() if 'Volume' in h else None
            except:
                continue
        
        if close is None or len(close) < 20:
            continue
        
        aktuell = float(close.iloc[-1])
        vortag = float(close.iloc[-2]) if len(close) > 1 else aktuell
        tagesrendite = ((aktuell / vortag) - 1) * 100
        
        # SMA
        sma20 = float(close.tail(20).mean())
        sma50 = float(close.tail(50).mean()) if len(close) >= 50 else sma20
        
        # Volatilität (annualisiert)
        daily_returns = close.pct_change().dropna()
        volatilitaet = float(daily_returns.tail(20).std() * np.sqrt(252) * 100)
        
        # Max Drawdown
        cummax = close.cummax()
        drawdown = ((close - cummax) / cummax * 100)
        max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0
        
        # Sharpe Ratio (vereinfacht, risikoloser Zins = 0)
        sharpe = float(daily_returns.tail(60).mean() / daily_returns.tail(60).std() * np.sqrt(252)) if len(daily_returns) >= 60 else 0
        
        # Kursänderung 5 Tage
        if len(close) >= 6:
            woche = ((float(close.iloc[-1]) / float(close.iloc[-6])) - 1) * 100
        else:
            woche = 0
        
        # 30 Tage
        if len(close) >= 31:
            monat = ((float(close.iloc[-1]) / float(close.iloc[-31])) - 1) * 100
        else:
            monat = 0
        
        # Trend-Richtung
        uptrend = 1 if aktuell > sma20 > sma50 else (0 if aktuell < sma20 < sma50 else 0.5)
        
        ergebnis[ticker] = {
            "name": meta["name"],
            "kategorie": meta["kat"],
            "hebel": meta["hebel"],
            "aktuell": round(aktuell, 2),
            "tagesrendite": round(tagesrendite, 2),
            "sma20": round(sma20, 2),
            "sma50": round(sma50, 2),
            "uptrend": uptrend,
            "volatilitaet": round(volatilitaet, 1),
            "max_drawdown": round(max_dd, 1),
            "sharpe": round(sharpe, 2),
            "woche": round(woche, 2),
            "monat": round(monat, 2),
            "letztes_update": now.isoformat(),
        }
    
    return ergebnis

def log_verlauf(ticker_data):
    """Hängt täglichen Snapshot an Log-Datei an."""
    log = {"zeit": datetime.now().isoformat(), "daten": ticker_data, "instrumente": list(WATCHLIST.keys())}
    
    # Alte Logs laden
    history = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                history = json.load(f)
        except:
            history = []
    
    # Nur 90 Tage behalten
    history.append(log)
    if len(history) > 90:
        history = history[-90:]
    
    with open(LOG_FILE, "w") as f:
        json.dump(history, f, indent=1)

def analyse():
    """Erstellt Zusammenfassung der gesammelten Daten."""
    if not os.path.exists(LOG_FILE):
        return {"fehler": "Noch keine Daten gesammelt"}
    
    with open(LOG_FILE) as f:
        logs = json.load(f)
    
    if len(logs) < 2:
        return {"fehler": "Weniger als 2 Datenpunkte"}
    
    # Beste/schlechteste Instrumente im Beobachtungszeitraum
    letzter = logs[-1]["daten"]
    erster = logs[0]["daten"]
    
    vergleich = {}
    for ticker, info in letzter.items():
        if ticker in erster:
            erst_preis = erster[ticker].get("aktuell", 0)
            if erst_preis > 0:
                rendite = (info["aktuell"] / erst_preis - 1) * 100
            else:
                rendite = 0
            vergleich[ticker] = {
                "name": info["name"],
                "kategorie": info["kategorie"],
                "rendite": round(rendite, 2),
                "volatilitaet": info["volatilitaet"],
                "sharpe": info["sharpe"],
            }
    
    # Sortieren
    best = sorted(vergleich.items(), key=lambda x: -x[1]["rendite"])
    worst = sorted(vergleich.items(), key=lambda x: x[1]["rendite"])
    
    return {
        "zeitraum": f"{logs[0]['zeit'][:10]} → {logs[-1]['zeit'][:10]}",
        "tage": len(logs),
        "best": [{"ticker": t, **v} for t, v in best[:3]],
        "worst": [{"ticker": t, **v} for t, v in worst[:3]],
        "vergleich": vergleich,
    }

if __name__ == "__main__":
    quiet = "--quiet" in sys.argv
    
    if not quiet:
        print("📡 Spekulation-Watch – sammle Daten...", flush=True)
    
    try:
        daten = fetch_and_analyze()
        log_verlauf(daten)
        
        if not quiet:
            print(f"   ✅ {len(daten)} Instrumente aktualisiert", flush=True)
            
            # Kurzübersicht
            for ticker, info in sorted(daten.items(), key=lambda x: x[1]["kategorie"]):
                pfeil = "🟢" if info["tagesrendite"] > 1 else ("🔴" if info["tagesrendite"] < -1 else "⚪")
                print(f"   {pfeil} {ticker:>5} [{info['kategorie']:>10}]  ${info['aktuell']:<8}  {info['tagesrendite']:>+5.1f}%  Vola {info['volatilitaet']:.0f}%", flush=True)
        
        # Analyse
        if len(daten) > 0 and os.path.exists(LOG_FILE):
            with open(LOG_FILE) as f:
                logs = json.load(f)
            if len(logs) >= 2:
                a = analyse()
                if "fehler" not in a:
                    if not quiet:
                        print(f"\n📊 Analyse ({a['zeitraum']})", flush=True)
                        for e in a["best"]:
                            print(f"   🏆 {e['ticker']} ({e['name']})  {e['rendite']:+.1f}%  Sharpe {e['sharpe']}", flush=True)
                        for e in a["worst"]:
                            print(f"   🗑️ {e['ticker']} ({e['name']})  {e['rendite']:+.1f}%  Sharpe {e['sharpe']}", flush=True)
        
        # Save latest for dashboard
        spfad = os.path.join(BASE, "spec_watch.json")
        with open(spfad, "w") as f:
            json.dump(daten, f, indent=2)
            
    except Exception as e:
        print(f"❌ Fehler: {e}", flush=True)
