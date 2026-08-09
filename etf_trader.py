#!/usr/bin/env python3
"""ETF-Trader – 20 Depots mit Risiko-Rating 0–95, ETF-Universum.

Analog zu batch_trader.py aber für ETFs mit risk_score (0-100).
Jedes Depot startet mit $100 → $2.000 Gesamt.
"""
import sys, os, json, time, random
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from engine import scan_markt, hole_kurs, signal_aktion, ausführen, historie_aktualisieren
import strategie  # v2.20.0: zentrale Strategie-Config
from etf_profile import ETF_TICKERS, TICKER_TO_ETF, TICKER_TO_RISK, risk_stufe

QUIET = "--quiet" in sys.argv

# 20 ETF-Depots mit Risiko 0-95 (5er Schritte wie Aktien)
ETF_RISK_STUFEN = list(range(0, 100, 5))  # [0, 5, 10, ..., 95]

def etf_pfad(risk):
    return os.path.join(BASE, f"etf_{risk:03d}.json")

def laden_oder_erstellen(risk):
    pfad = etf_pfad(risk)
    if os.path.exists(pfad):
        with open(pfad) as f:
            data = json.load(f)
        d = {
            "risk": risk,
            "start_wert": data.get("start_wert", 100),
            "bargeld": data.get("bargeld", 100),
            "positions": data.get("positions", {}),
            "historie": data.get("historie", []),
            "trades": data.get("trades", []),
            "gesperrt": data.get("gesperrt", False),
            "peak_wert": data.get("peak_wert", 100),
            "pfad": pfad,
        }
        return d
    else:
        d = {
            "risk": risk,
            "start_wert": 100,
            "bargeld": 100,
            "positions": {},
            "historie": [],
            "trades": [],
            "gesperrt": False,
            "peak_wert": 100,
            "pfad": pfad,
        }
        speichern(d)
        return d

def speichern(d):
    data = {k: v for k, v in d.items() if k != "pfad"}
    data["aktualisiert"] = datetime.now().isoformat()
    data.setdefault("tenant_id", 1)  # PHASE 3 §2.3: Depot tenant-markieren
    with open(d["pfad"], "w") as f:
        json.dump(data, f, indent=2)

def etf_bewerte(etf_liste, depot_risk):
    """Bewertet ETFs für ein Depot mit bestimmtem risk-Level.
    
    Depot risk 0-95 → sucht ETFs mit passendem risk_score.
    Ähnlich wie bewerte() in engine.py aber für ETF risk_score.
    """
    # Depot-Risiko in ETF-Stufe übersetzen
    depot_stufe = int(depot_risk / 20)  # 0-95 → 0-4
    
    erlaubt = []
    for e in etf_liste:
        score = e.get("risk_score", 50)
        stufe = risk_stufe(score)
        
        # Erlaubte Stufen: depot_stufe ±1
        if abs(stufe - depot_stufe) <= 1:
            preis = e.get("preis", 0)
            budget = 100
            # Preis-Bewertung zentral aus strategie.py (v2.20.0) - konsistent mit Aktien
            preis_bonus = strategie.preis_score(preis, budget) if preis > 0 else 0
            # 🛡 Preis-Malus: ETF teurer als Budget ist mit $100 Startkapital NICHT
            # kaufbar (menge=0) -> stark abwerten, damit bezahlbare Alternativen ranken
            if preis > budget:
                preis_bonus += strategie.TOO_EXPENSIVE_MALUS
        
            # Nächste zum idealen Risk-Score gewinnt
            ideal = depot_risk
            abstand = abs(score - ideal)
            naehe = max(0, 100 - abstand * 1.5)  # 100 = perfekt, ~70 bei 20 Punkte Abweichung
            # leichter Bias zu leicht aggressiveren ETFs (Wachstum)
            growth_bonus = min(5, max(0, score - ideal) * 0.15)
        
            ges_score = naehe + growth_bonus + preis_bonus
            erlaubt.append({
                "ticker": e["ticker"],
                "score": ges_score,
                "preis": preis,
                "name": e.get("name", ""),
                "sektor": e.get("sektor", ""),
                "risk_score": score,
            })
    
    # Top 8 nach Score (Fix v2.16.7: vorher nur Top 3 -> wenn die alle zu teuer
    # waren, kaufte das Depot nie; mehr Kandidaten = bezahlbare Alternativen dabei)
    erlaubt.sort(key=lambda x: x["score"], reverse=True)
    return erlaubt[:8]

def main():
    scan = scan_markt(ETF_TICKERS)
    
    etf_liste = []
    for t in ETF_TICKERS:
        info = TICKER_TO_ETF.get(t, {})
        preis = scan.get(t, {}).get("aktuell", 0)
        if preis == 0:
            preis = hole_kurs(t)
        etf_liste.append({
            "ticker": t,
            "name": info.get("name", ""),
            "preis": max(preis, 0.01),
            "risk_score": TICKER_TO_RISK.get(t, 50),
            "sektor": info.get("sektor", ""),
        })
    
    if not QUIET:
        print(f"📦 ETF-Trader: {len(etf_liste)} ETFs", flush=True)
    
    ergebnisse = []
    
    for risk in ETF_RISK_STUFEN:
        depot = laden_oder_erstellen(risk)
        
        if depot["gesperrt"]:
            if not QUIET:
                print(f"   ⛔ Risk {risk:>3} – GESPERRT", flush=True)
            ergebnisse.append((risk, depot["bargeld"], depot["bargeld"], 0, 0, 0))
            continue
        
        # Top ETFs finden
        top = etf_bewerte(etf_liste, risk)
        
        if not top:
            continue
        
        # Prüfen ob wir Positionen halten die nicht mehr passen
        zu_verkaufen = []
        for ticker, pos in list(depot["positions"].items()):
            info = TICKER_TO_ETF.get(ticker)
            if info:
                stufe = risk_stufe(info["risk_score"])
                depot_stufe = int(risk / 20)
                if abs(stufe - depot_stufe) > 1:
                    zu_verkaufen.append(ticker)
        
        for ticker in zu_verkaufen:
            pos = depot["positions"][ticker]
            preis = hole_kurs(ticker)
            if preis > 0:
                menge = pos["shares"]
                depot["bargeld"] += menge * preis
                depot["trades"].append({
                    "zeit": datetime.now().isoformat(),
                    "ticker": ticker,
                    "typ": "verkaufen",
                    "menge": menge,
                    "preis": round(preis, 2),
                    "grund": f"Risk mismatch (ETF Stufe {risk_stufe(TICKER_TO_RISK.get(ticker,50))} vs Depot {int(risk/20)})",
                })
                del depot["positions"][ticker]
                if not QUIET:
                    print(f"   🔴 ETF Verkauf {ticker} {menge:.2f}st @${preis:.2f} (Risk-Mismatch)", flush=True)
        
        # Kaufe Top-ETFs
        max_pos = max(1, int(3 - risk / 33))  # 3 bei risk 0, 1 bei risk 90
        aktuelle = len(depot["positions"])
        
        for e in top:
            if aktuelle >= max_pos:
                break
            if e["ticker"] in depot["positions"]:
                continue
            
            preis = e["preis"]
            if preis <= 0:
                continue
                
            menge = int(depot["bargeld"] * 0.5 / preis)
            if menge <= 0:
                menge = 1
            kosten = menge * preis
            if kosten > depot["bargeld"]:
                menge = int(depot["bargeld"] / preis)
                if menge <= 0:
                    continue
                kosten = menge * preis
            
            depot["bargeld"] -= kosten
            depot["positions"][e["ticker"]] = {
                "shares": menge,
                "avg_price": preis,
                "stop_loss": preis * 0.88,
                "take_profit": preis * 1.15,
                "kauf_zeit": datetime.now().isoformat(),
            }
            depot["trades"].append({
                "zeit": datetime.now().isoformat(),
                "ticker": e["ticker"],
                "typ": "kaufen",
                "menge": menge,
                "preis": round(preis, 2),
                "grund": f"Score {e['score']:.0f} | RiskScore {e['risk_score']} | {e['sektor']}",
            })
            aktuelle += 1
            if not QUIET:
                print(f"   🟢 ETF Kauf {e['ticker']} {menge:.0f}st @${preis:.2f} "
                      f"(RiskScore {e['risk_score']}, Score {e['score']:.0f})", flush=True)
        
        # Stop-Loss / Take-Profit prüfen
        for ticker, pos in list(depot["positions"].items()):
            preis = hole_kurs(ticker)
            if preis <= 0:
                continue
            if preis <= pos.get("stop_loss", 0):
                depot["bargeld"] += pos["shares"] * preis
                depot["trades"].append({
                    "zeit": datetime.now().isoformat(),
                    "ticker": ticker,
                    "typ": "verkaufen",
                    "menge": pos["shares"],
                    "preis": round(preis, 2),
                    "grund": "Stop-Loss",
                })
                del depot["positions"][ticker]
                if not QUIET:
                    print(f"   🔴 ETF Stop-Loss {ticker} @${preis:.2f}", flush=True)
            elif preis >= pos.get("take_profit", 999):
                depot["bargeld"] += pos["shares"] * preis
                depot["trades"].append({
                    "zeit": datetime.now().isoformat(),
                    "ticker": ticker,
                    "typ": "verkaufen",
                    "menge": pos["shares"],
                    "preis": round(preis, 2),
                    "grund": "Take-Profit",
                })
                del depot["positions"][ticker]
                if not QUIET:
                    print(f"   🟢 ETF Take-Profit {ticker} @${preis:.2f}", flush=True)
        
        # Historie
        wert = depot["bargeld"]
        for t, p in depot["positions"].items():
            try:
                preis = hole_kurs(t)
                wert += p["shares"] * max(preis, 0)
            except:
                wert += p["shares"] * p.get("avg_price", 0)
        
        if wert > depot["peak_wert"]:
            depot["peak_wert"] = wert
        
        dd = (depot["peak_wert"] - wert) / max(depot["peak_wert"], 1) * 100
        if dd > 30:
            depot["gesperrt"] = True
            if not QUIET:
                print(f"   ⛔ Risk {risk:>3} – Drawdown {dd:.1f}% → GESPERRT", flush=True)
        
        depot["historie"].append({
            "zeit": datetime.now().isoformat(),
            "wert": round(wert, 2),
            "bargeld": round(depot["bargeld"], 2),
        })
        
        speichern(depot)
        
        rendite = (wert / depot["start_wert"] - 1) * 100
        ergebnisse.append((risk, wert, depot["bargeld"], rendite, len(depot["positions"]), len(depot["trades"])))
    
    # Zusammenfassung
    ges_wert = sum(e[1] for e in ergebnisse)
    ges_start = len(ETF_RISK_STUFEN) * 100
    ges_rendite = (ges_wert / ges_start - 1) * 100 if ges_start > 0 else 0
    
    if not QUIET:
        print(f"\n{'='*60}", flush=True)
        print(f"📊 ETF: {len(ergebnisse)} Depots | ${ges_wert:.2f} ({ges_rendite:+.2f}%)", flush=True)
        for risk, wert, cash, rendite, pos, trades in ergebnisse:
            farbe = "🟢" if rendite > 0 else ("🔴" if rendite < -0.1 else "⚪")
            print(f"   {farbe} Risk {risk:>3} ${wert:>6.2f} {rendite:>+6.2f}%  {pos} Pos  {trades} Trades", flush=True)
    
    # Save summary
    summary = {
        "zeit": datetime.now().isoformat(),
        "depots": len(ETF_RISK_STUFEN),
        "gesamtwert": round(ges_wert, 2),
        "gesamt_rendite": round(ges_rendite, 2),
        "trades": sum(e[5] for e in ergebnisse),
        "detail": [{"risk": r, "wert": round(w,2), "rendite": round(rend,2), "pos": p, "trades": t}
                   for r,w,_,rend,p,t in ergebnisse],
    }
    with open(os.path.join(BASE, "etf_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Status speichern
    try:
        from trader_status import update_status
        update_status("etf_trader", {
            "depots": len(ETF_RISK_STUFEN),
            "trades": sum(e[5] for e in ergebnisse),
            "rendite": round(ges_rendite, 2),
        })
    except Exception:
        pass

    # System-Log
    try:
        from system_log import log_eintrag
        level = "ok" if ges_rendite >= 0 else "warn"
        log_eintrag("etf", f"ETF-Lauf: {len(ETF_RISK_STUFEN)} Depots, "
                    f"{sum(e[5] for e in ergebnisse)} Trades, Rendite {ges_rendite:+.2f}%", level)
    except Exception:
        pass


if __name__ == "__main__":
    main()
