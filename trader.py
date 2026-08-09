#!/usr/bin/env python3
"""
Micro-Trader – Dein Geld vermehren, ein Trade nach dem anderen
===============================================================
Du sagst mir einen Betrag, ich such passende Aktien raus und trade.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from tabulate import tabulate
import json, os, sys

# ─── Basispfad ─────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DATEI_DEPOT = os.path.join(BASE, "depot.json")
DATEI_LOG = os.path.join(BASE, "trades.log")

# ─── Watchlist ────────────────────────────────────────────────
# Normal (moderate risk)
WATCHLIST_MODERATE = [
    "AAPL","MSFT","GOOGL","AMZN","TSLA","META","NVDA","AMD","INTC",
    "JPM","BAC","V","MA","PYPL",
    "JNJ","PFE","MRK","ABBV","UNH",
    "WMT","COST","HD","MCD","SBUX","NKE","DIS",
    "XOM","CVX","KO","PEP","PG","BA","CAT",
    "IBM","CSCO","ORCL","CRM","ADBE","NFLX",
    "BABA","JD","NIO","PLTR","SOFI","RIVN","LCID",
    "F","GM","AAL","CCL","MGM",
    "DKNG","COIN","MARA","SNAP","T","VZ",
]

# Hochrisiko (zusätzlich: Hebel-ETFs, Meme-Stocks, Mini-Penny)
WATCHLIST_AGGRESSIVE = WATCHLIST_MODERATE + [
    # 3x Long-ETFs
    "TQQQ",   # 3x Nasdaq
    "SOXL",   # 3x Halbleiter
    "FAS",    # 3x Finanzen
    "LABU",   # 3x Biotech
    "NAIL",   # 3x Hausbau
    # 3x Short/Inverse
    "SQQQ",   # -3x Nasdaq
    "SPXS",   # -3x S&P500
    # Meme / High Beta
    "GME","AMC","BB","KOSS",
    # Crypto-Miner
    "MARA","RIOT","CLSK","WULF",
    # Volatile Tech
    "UPST","AFRM","HOOD","CVNA","CHWY",
    # Small Cap Bio
    "CRSP","EDIT","NTLA",
]

# ─── Risk-Profil ──────────────────────────────────────────────
# Defaults (fallback) — können via settings.json überschrieben werden
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from settings_loader import risk_param
    RISK = {
        "moderate": {
            "position_size": risk_param("moderate_position_size", 0.35),
            "stop_loss": risk_param("moderate_stop_loss", 0.92),
            "take_profit": risk_param("moderate_take_profit", 1.12),
            "min_score": 40, "bonus_volatil": 5,
        },
        "aggressive": {
            "position_size": risk_param("aggressive_position_size", 0.50),
            "stop_loss": risk_param("aggressive_stop_loss", 0.85),
            "take_profit": risk_param("aggressive_take_profit", 1.20),
            "min_score": 30, "bonus_volatil": 15,
        },
    }
except Exception:
    RISK = {
        "moderate": {"position_size": 0.35, "stop_loss": 0.92, "take_profit": 1.12, "min_score": 40, "bonus_volatil": 5},
        "aggressive": {"position_size": 0.50, "stop_loss": 0.85, "take_profit": 1.20, "min_score": 30, "bonus_volatil": 15},
    }

# ─── Indikatoren ────────────────────────────────────────────────
def berechne_indikatoren(close):
    """Berechnet alle Indikatoren auf einmal."""
    if len(close) < 50:
        return None
    aktuell = float(close.iloc[-1])

    # SMAs
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else aktuell

    # EMAs
    ema12 = float(close.rolling(12).mean().iloc[-1])
    ema26 = float(close.rolling(26).mean().iloc[-1])

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = float((100 - (100 / (1 + rs))).iloc[-1]) if not pd.isna(rs.iloc[-1]) else 50

    # MACD
    macd = ema12 - ema26
    signal_line = float(close.rolling(9).mean().iloc[-1])  # vereinfacht
    macd_hist = macd - signal_line

    # Bollinger Bands (20,2)
    bb_mittel = sma20
    bb_std = float(close.tail(20).std())
    bb_oben = bb_mittel + 2 * bb_std
    bb_unten = bb_mittel - 2 * bb_std

    # ATR (14)
    high_low = close.rolling(14).max() - close.rolling(14).min()
    atr = float(high_low.iloc[-1]) if not pd.isna(high_low.iloc[-1]) else 0

    # Momentum
    mom_1w = ((aktuell / float(close.iloc[-5])) - 1) * 100 if len(close) >= 5 else 0
    mom_1m = ((aktuell / float(close.iloc[-21])) - 1) * 100 if len(close) >= 21 else 0
    mom_3m = ((aktuell / float(close.iloc[-63])) - 1) * 100 if len(close) >= 63 else 0

    return {
        "aktuell": aktuell, "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "ema12": ema12, "ema26": ema26, "rsi": rsi,
        "macd": macd, "macd_hist": macd_hist,
        "bb_oben": bb_oben, "bb_unten": bb_unten,
        "atr": atr, "mom_1w": mom_1w, "mom_1m": mom_1m, "mom_3m": mom_3m,
    }

# ─── Scanner ──────────────────────────────────────────────────
def scan_markt(limit=0, quiet=False, watchlist=None, risk_name="moderate"):
    """Scannt Markt. limit=0 = alle, sonst nur so viele."""
    if watchlist is None:
        watchlist = WATCHLIST_MODERATE
    if not quiet:
        print(f"  🔍 Scanne {len(watchlist)} Aktien ({risk_name})...\n")
    funde = []
    liste = watchlist[:limit] if limit > 0 else watchlist

    for sym in liste:
        try:
            df = yf.download(sym, period="4mo", progress=False, auto_adjust=True)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                close = df["Close"][sym].dropna()
                vol = df["Volume"][sym]
            else:
                close = df["Close"].dropna()
                vol = df["Volume"]

            if len(close) < 50:
                continue

            ind = berechne_indikatoren(close)
            if ind is None:
                continue

            # Volumen
            avg_vol = float(vol.tail(20).mean())

            funde.append({
                "symbol": sym,
                **ind,
                "volume": avg_vol,
            })
        except:
            continue
    return funde

def bewerte(aktien, budget, risk_name="moderate"):
    """Bewertet Aktien nach Eignung (Score 0-100)."""
    r = RISK.get(risk_name, RISK["moderate"])
    for a in aktien:
        score = 0
        # ─── Preis (je günstiger desto besser) ───
        if a["aktuell"] < budget * 0.2:
            score += 25
        elif a["aktuell"] < budget * 0.5:
            score += 15
        elif a["aktuell"] < budget:
            score += 5
        else:
            score -= 10

        # ─── Trend-Güte ───
        # Über SMA50?
        if a["aktuell"] > a["sma50"]:
            score += 20
        # SMA20 > SMA50? (bullisher Crossover)
        if a["sma20"] > a["sma50"]:
            score += 10
        # Über SMA200?
        if a["aktuell"] > a["sma200"]:
            score += 10

        # ─── RSI ───
        if 40 <= a["rsi"] <= 65:
            score += 15
        elif 30 <= a["rsi"] <= 70:
            score += 8

        # ─── Momentum ───
        if a["mom_1m"] > 8:
            score += 15
        elif a["mom_1m"] > 3:
            score += 8
        if a["mom_1w"] > 2:
            score += 8

        # ─── MACD ───
        if a["macd_hist"] > 0:
            score += 5

        # ─── Volatilität (ATR) ───
        vol_ratio = a["atr"] / a["aktuell"]
        if vol_ratio > 0.02 and vol_ratio < 0.15:
            score += r["bonus_volatil"]
        elif vol_ratio > 0.01:
            score += r["bonus_volatil"] // 2

        # ─── Volumen ───
        if a["volume"] > 10_000_000:
            score += 7
        elif a["volume"] > 2_000_000:
            score += 4

        a["score"] = max(0, min(100, score))
    return aktien

# ─── Strategie-Signale ─────────────────────────────────────────
def signal_aktion(close, ind, in_position=False):
    """Gibt (action, grund) zurück."""
    if ind is None:
        return (0, "Keine Daten")

    aktuell = ind["aktuell"]
    sma50 = ind["sma50"]
    rsi = ind["rsi"]
    macd_hist = ind["macd_hist"]
    bb_unten = ind["bb_unten"]

    # ─── EXIT-Signale (wenn in Position) ───
    if in_position:
        # Trendbruch: Kurs fällt unter SMA50
        if aktuell < sma50 and rsi < 45:
            return (-1, f"Trendbruch (Kurs ${aktuell:.2f} < SMA50 ${sma50:.2f}, RSI {rsi:.0f})")
        # RSI überkauft
        if rsi > 75:
            return (-1, f"Überkauft (RSI {rsi:.0f})")
        # MACD bearish
        if macd_hist < 0 and rsi < 50:
            return (-1, f"MACD bearish + RSI fallend")

    # ─── ENTRY-Signale ───
    # 1) Bullischer Crossover + RSI OK
    if aktuell > sma50 and 40 <= rsi <= 65:
        grund = f"Aufwärtstrend (${aktuell:.2f} > SMA50 ${sma50:.2f}, RSI {rsi:.0f})"
        return (1, grund)

    # 2) Bollinger-Band-Bounce (Kurs am unteren Band + RSI tief)
    if aktuell <= bb_unten * 1.01 and rsi < 35:
        grund = f"BB-Bounce (${aktuell:.2f} am unteren Band ${bb_unten:.2f}, RSI {rsi:.0f})"
        return (1, grund)

    # 3) MACD bullisch
    if macd_hist > 0 and rsi > 45 and aktuell > sma50:
        grund = f"MACD bullisch (RSI {rsi:.0f}, über SMA50)"
        return (1, grund)

    return (0, "Kein Signal")

# ─── Depot ──────────────────────────────────────────────────────
class Depot:
    def __init__(self, start=100):
        self.bargeld = start
        self.start_wert = start
        self.positions = {}
        self.trades = []

    def laden(self):
        if os.path.exists(DATEI_DEPOT):
            with open(DATEI_DEPOT) as f:
                d = json.load(f)
                self.bargeld = d.get("bargeld", self.start_wert)
                self.start_wert = d.get("start_wert", self.start_wert)
                self.positions = {k: v for k, v in d.get("positions", {}).items() if v["shares"] > 0}
                self.trades = d.get("trades", [])
                self.risk_name = d.get("risk_name", "moderate")

    def speichern(self):
        with open(DATEI_DEPOT, "w") as f:
            json.dump({"bargeld": self.bargeld, "start_wert": self.start_wert,
                       "positions": self.positions, "trades": self.trades,
                       "risk_name": getattr(self, "risk_name", "moderate"),
                       "tenant_id": int(getattr(self, "tenant_id", 1) or 1)}, f, indent=2)  # PHASE 3 §2.3

    def kaufen(self, symbol, kurs, ind, budget_anteil=0.35, stop_loss_pct=0.92, take_profit_pct=1.12):
        betrag = self.bargeld * budget_anteil
        if betrag < 10:
            return False, "Betrag zu klein"
        shares = round(betrag / kurs, 4)
        kosten = shares * kurs
        if kosten > self.bargeld:
            shares = round(self.bargeld * 0.95 / kurs, 4)
            kosten = shares * kurs
        if kosten < 5:
            return False, "Position zu klein"
        self.bargeld -= kosten
        if symbol in self.positions:
            alt = self.positions[symbol]
            gesamt = alt["shares"] * alt["avg_price"] + kosten
            neue = alt["shares"] + shares
            self.positions[symbol] = {
                "shares": neue, "avg_price": gesamt / neue,
                "entry_date": alt.get("entry_date", datetime.now().strftime("%Y-%m-%d")),
                "entry_price": alt["avg_price"],
                "stop_loss": None, "take_profit": None
            }
        else:
            # Stop-Loss & Take-Profit setzen
            self.positions[symbol] = {
                "shares": shares, "avg_price": kurs,
                "entry_date": datetime.now().strftime("%Y-%m-%d"),
                "entry_price": kurs,
                "stop_loss": kurs * stop_loss_pct,
                "take_profit": kurs * take_profit_pct,
                "trailing_stop": None
            }
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.trades.append({"zeit": ts, "symbol": symbol, "side": "BUY",
                            "shares": shares, "price": round(kurs, 2),
                            "value": round(kosten, 2), "trade_id": len(self.trades) + 1,
                            "grund": ind.get("_grund", "")})
        return True, f"Kauf {shares:.2f} {symbol} @ ${kurs:.2f}"

    def verkaufen(self, symbol, kurs, grund=""):
        if symbol not in self.positions:
            return False, "Nicht vorhanden"
        pos = self.positions[symbol]
        erloes = pos["shares"] * kurs
        gewinn = erloes - (pos["shares"] * pos["avg_price"])
        rendite = (kurs / pos["avg_price"] - 1) * 100
        self.bargeld += erloes
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.trades.append({"zeit": ts, "symbol": symbol, "side": "SELL",
                            "shares": pos["shares"], "price": round(kurs, 2),
                            "value": round(erloes, 2), "pnl": round(gewinn, 2),
                            "rendite": round(rendite, 2),
                            "trade_id": len(self.trades) + 1, "grund": grund})
        del self.positions[symbol]
        return True, f"Verkauf {pos['shares']:.2f} {symbol} @ ${kurs:.2f} (PnL: ${gewinn:+.2f}, {rendite:+.2f}%)"

    def depotwert(self, kurse):
        wert = self.bargeld
        for s, p in self.positions.items():
            wert += p["shares"] * kurse.get(s, 0)
        return wert

    def rendite(self, kurse):
        dw = self.depotwert(kurse)
        return (dw / self.start_wert - 1) * 100 if self.start_wert > 0 else 0

# ─── Hauptprogramm ──────────────────────────────────────────────
def main():
    quiet = "--quiet" in sys.argv
    quick = "--quick" in sys.argv
    risk_name = "moderate"
    for a in sys.argv:
        if a.startswith("--risk="):
            risk_name = a.split("=")[1]
        elif a == "--risk" and sys.argv.index(a) + 1 < len(sys.argv):
            risk_name = sys.argv[sys.argv.index(a) + 1]
    risk_name = risk_name if risk_name in RISK else "moderate"
    r = RISK[risk_name]
    watchlist = WATCHLIST_AGGRESSIVE if risk_name == "aggressive" else WATCHLIST_MODERATE

    neues_depot = False

    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        try:
            budget = float(sys.argv[1].replace("€", "").replace("$", "").replace(",", "."))
            neues_depot = True
        except:
            budget = 50.0
    else:
        budget = 50.0

    depot = Depot(budget)
    depot.laden()

    if neues_depot or not depot.trades:
        depot.bargeld = budget
        depot.start_wert = budget
        depot.positions = {}
        depot.trades = []
        depot.risk_name = risk_name
        titel = f"{budget:.0f}€ NEU {risk_name}"
    else:
        depotwert_gestern = depot.depotwert(
            {s: p["avg_price"] for s, p in depot.positions.items()}
        )
        risk_name = getattr(depot, "risk_name", risk_name)
        r = RISK[risk_name]
        watchlist = WATCHLIST_AGGRESSIVE if risk_name == "aggressive" else WATCHLIST_MODERATE
        titel = f"↻ {risk_name}"
        if not quiet:
            print(f"  ↻ Depot: ${depot.bargeld:.2f} Cash, {len(depot.positions)} Position(en)")

    if not quiet:
        print(f"  ─── {titel} ───")

    # ─── Schnell-Check (nur offene Positionen) ───
    kurse = {}
    trades_heute = 0
    trade_msgs = []

    if quick:
        # Nur offene Positionen prüfen
        for sym in list(depot.positions.keys()):
            try:
                df = yf.download(sym, period="5d", progress=False, auto_adjust=True)
                if df.empty:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    close = df["Close"][sym].dropna()
                else:
                    close = df["Close"].dropna()
                if close.empty:
                    continue
                kurs = float(close.iloc[-1])
                kurse[sym] = kurs
                ind = berechne_indikatoren(close)
                sig, grund = signal_aktion(close, ind, in_position=True)
                if sig == -1:
                    ok, msg = depot.verkaufen(sym, kurs, grund)
                    if ok:
                        trade_msgs.append(f"🔴 {msg}")
                        trades_heute += 1
                elif sig == 0:
                    # Kein Verkaufssignal -> Stop-Loss prüfen
                    pos = depot.positions[sym]
                    sl = pos.get("stop_loss")
                    tp = pos.get("take_profit")
                    if sl and kurs < sl:
                        ok, msg = depot.verkaufen(sym, kurs, "Stop-Loss erreicht")
                        if ok:
                            trade_msgs.append(f"🛑 {msg}")
                            trades_heute += 1
                    elif tp and kurs > tp:
                        ok, msg = depot.verkaufen(sym, kurs, "Take-Profit erreicht")
                        if ok:
                            trade_msgs.append(f"✅ {msg}")
                            trades_heute += 1
            except:
                continue

        if trades_heute == 0 and quiet:
            depot.speichern()
            return  # komplett still, keine Ausgabe
        elif trades_heute == 0:
            print("  ⚪ Keine Änderungen")
    else:
        # ─── Voller Scan ───
        alle = scan_markt(quiet=quiet, watchlist=watchlist, risk_name=risk_name)
        bewertet = bewerte(alle, depot.bargeld + sum(p["shares"] * p.get("avg_price", 0) for p in depot.positions.values()), risk_name=risk_name)

        # Bestehende Positionen prüfen
        for sym in list(depot.positions.keys()):
            try:
                df = yf.download(sym, period="3mo", progress=False, auto_adjust=True)
                if df.empty:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    close = df["Close"][sym].dropna()
                else:
                    close = df["Close"].dropna()
                if close.empty:
                    continue
                kurs = float(close.iloc[-1])
                kurse[sym] = kurs
                ind = berechne_indikatoren(close)
                sig, grund = signal_aktion(close, ind, in_position=True)
                if sig == -1:
                    ok, msg = depot.verkaufen(sym, kurs, grund)
                    if ok:
                        trade_msgs.append(f"🔴 {msg}")
                        trades_heute += 1
                else:
                    pos = depot.positions[sym]
                    sl = pos.get("stop_loss")
                    tp = pos.get("take_profit")
                    if sl and kurs < sl:
                        ok, msg = depot.verkaufen(sym, kurs, "Stop-Loss")
                        if ok:
                            trade_msgs.append(f"🛑 {msg}")
                            trades_heute += 1
                    elif tp and kurs > tp:
                        ok, msg = depot.verkaufen(sym, kurs, "Take-Profit")
                        if ok:
                            trade_msgs.append(f"✅ {msg}")
                            trades_heute += 1
            except:
                continue

        # Neue Einstiege suchen
        for a in sorted(bewertet, key=lambda x: x["score"], reverse=True)[:6]:
            sym = a["symbol"]
            if sym in depot.positions:
                continue
            if a["score"] < r["min_score"]:
                continue
            kurs = a["aktuell"]
            kurse[sym] = kurs
            sig, grund = signal_aktion(None, a, in_position=False)
            if sig == 1:
                a["_grund"] = grund
                ok, msg = depot.kaufen(sym, kurs, a,
                    budget_anteil=r["position_size"],
                    stop_loss_pct=r["stop_loss"],
                    take_profit_pct=r["take_profit"])
                if ok:
                    trade_msgs.append(f"🟢 {msg} – {grund}")
                    trades_heute += 1

        # Top-Vorschläge anzeigen
        if not quiet:
            top = sorted(bewertet, key=lambda x: x["score"], reverse=True)[:6]
            rows = []
            for a in top:
                sig_s = "🟢" if a["aktuell"] > a["sma50"] else "🔴"
                stuecke = max(1, int(depot.bargeld * 0.35 / a["aktuell"]))
                rows.append([a["symbol"], f"${a['aktuell']:.2f}", f"{a['mom_1w']:+.1f}%",
                            f"{a['rsi']:.0f}", f"{a['score']}", f"{stuecke}x", sig_s])
            print(tabulate(rows,
                          headers=["Sym", "Kurs", "1W%", "RSI", "Score", "Stk", ""],
                          tablefmt="rounded_grid", numalign="right"))

    # Nachrichten ausgeben
    for m in trade_msgs:
        print(f"  {m}")

    if trades_heute == 0 and not quiet:
        print("  ⚪ Keine Trades")

    # Depot-Status
    if not quiet or trades_heute > 0:
        depotwert = depot.depotwert(kurse) if kurse else depot.bargeld
        pnl = depotwert - depot.start_wert
        rendite = (depotwert / depot.start_wert - 1) * 100 if depot.start_wert > 0 else 0

        pos_rows = []
        for s, p in depot.positions.items():
            k = kurse.get(s, 0)
            wert = p["shares"] * k
            gewinn = ((k / p["avg_price"]) - 1) * 100 if p["avg_price"] > 0 else 0
            pos_rows.append([s, f"{p['shares']:.4f}", f"${p['avg_price']:.2f}",
                            f"${k:.2f}", f"${wert:.2f}", f"{gewinn:+.2f}%"])

        print(f"\n  💰 ${depot.bargeld:.2f} | 📈 ${depotwert:.2f} | PnL: ${pnl:+.2f} ({rendite:+.2f}%)")

        if pos_rows:
            print(tabulate(pos_rows, headers=["Sym", "Shares", "Ø-Kauf", "Kurs", "Wert", "Gewinn"],
                          tablefmt="simple", numalign="right"))

    depot.speichern()

    # Für Cronjob: Nur wenn Trades, die Zusammenfassung ausgeben
    if trades_heute > 0:
        print(f"\n📊 TRADES HEUTE: {trades_heute}")
        print(f"📈 Depot: ${depot.depotwert(kurse):.2f} | PnL: ${depot.depotwert(kurse)-depot.start_wert:+.2f}")

if __name__ == "__main__":
    main()
