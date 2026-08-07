#!/usr/bin/env python3
"""
Batch-Trader v3 – 20 Depots mit Tier-basiertem Risiko (0–95).
Scannt einmal, bewertet je Risk-Stufe mit Tier-Bonus und füllt alle Depots.
"""
import sys, os, json, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from engine import scan_markt, bewerte, signal_aktion, ausführen, historie_aktualisieren, Depot
from ki_decisions import entscheide_aktien_depot, hole_kurs_fuer, get_client, MODEL, API_KEY, ZEN_URL, schreibe_ki_log
from ki_provider import call_ki  # Fallback-Kette: openai → zen → nous → openrouter


def _parse_ki_json(raus):
    """Robuster JSON-Parser fuer KI-Antworten (fängt Array/Object-Fehler ab)."""
    if not raus:
        return None
    raus = raus.strip()
    # Fall 1: Antwort beginnt mit [ (korrektes Array)
    if raus.startswith("["):
        start, end = raus.find("["), raus.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raus[start:end])
            except Exception:
                pass
    # Fall 2: Antwort beginnt mit { (Modell hat Array-Klammern vergessen)
    if raus.startswith("{"):
        # Versuche als einzelnes Objekt
        try:
            obj = json.loads(raus)
            return [obj] if isinstance(obj, dict) else obj
        except Exception:
            pass
        # Oder als Array ohne aeussere Klammern: "{"risk":0,...}, {"risk":1,...}"
        try:
            wrapped = "[" + raus + "]"
            return json.loads(wrapped)
        except Exception:
            pass
    # Fall 3: JSON in Markdown-Codeblock
    if "```" in raus:
        import re
        m = re.search(r"```(?:json)?\s*(.*?)```", raus, re.DOTALL)
        if m:
            return _parse_ki_json(m.group(1))
    # Fall 4: Irgendwo im Text ein Array finden
    start, end = raus.find("["), raus.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raus[start:end])
        except Exception:
            pass
    return None

from risk_profile import fuer_risk_stufe, RISK_STUFEN, TIERS, TICKER_TO_TIER

QUIET = "--quiet" in sys.argv

def alle_ticker():
    """Alle 100 Aktien aus allen Tiers."""
    ticker = []
    for t in range(5):
        ticker.extend(TIERS.get(t, []))
    return list(set(ticker))

def laden_oder_erstellen(risk):
    """Lädt Depot oder erstellt neues."""
    pfad = os.path.join(BASE, f"depot_{risk:03d}.json")
    if os.path.exists(pfad):
        with open(pfad) as f:
            data = json.load(f)
        d = Depot(start_wert=data.get("start_wert", 100), risk=risk, depot_pfad=pfad)
        d.bargeld = data.get("bargeld", 100)
        d.positions = data.get("positions", {})
        d.historie = data.get("historie", [])
        d.trades = data.get("trades", [])
        d.ki_letzte = data.get("ki_letzte")
        return d
    else:
        d = Depot(start_wert=100, risk=risk, depot_pfad=pfad)
        d.speichern()
        return d

def main():
    ticker = alle_ticker()
    if not QUIET:
        print(f"🔍 Scanne {len(ticker)} Aktien...", flush=True)

    scan = scan_markt(ticker)

    aktien_liste = []
    for t, a in scan.items():
        a["ticker"] = t
        aktien_liste.append(a)

    if not QUIET:
        print(f"   ✅ {len(aktien_liste)} Aktien", flush=True)

    ergebnisse = []

    # Sammle alle Depot-Kontexte für parallele KI-Calls
    depot_kontexte = []
    for risk in RISK_STUFEN:
        params = fuer_risk_stufe(risk)
        depot = laden_oder_erstellen(risk)
        budget = depot.start_wert
        # 🛡 v2.16.8: Aktien-Liste NACH Preis filtern BEVOR bewertet wird.
        # bewerte() vergibt hohe Scores an teure Large-Caps -> top[:10] waeren fast
        # nur unbezahlbare -> nach Budget-Filter bliebe nichts. So bewertet bewerte()
        # nur Aktien, die das Depot mit 80% des Bargelds kaufen KANN.
        kauf_budget = depot.bargeld * 0.8
        bezahlbare = [a for a in aktien_liste if 0 < a.get("aktuell", 0) <= kauf_budget]
        # TEMP-DEBUG: was filtert der Budget-Filter?
        try:
            if risk in (80, 90):
                with open(os.path.join(BASE, "_budget_debug.txt"), "a", encoding="utf-8") as _pf:
                    _pf.write(f"Risk {risk}: Cash={depot.bargeld:.2f}, Budget={kauf_budget:.2f}, "
                              f"aktien_liste={len(aktien_liste)}, bezahlbare={len(bezahlbare)}\n")
                    if bezahlbare:
                        g = sorted(bezahlbare, key=lambda x: x.get("aktuell", 0))[:5]
                        _pf.write(f"  Guenstigste: {[(x['ticker'], round(x.get('aktuell',0),2)) for x in g]}\n")
        except Exception:
            pass
        if not bezahlbare:
            # Fallback: nur Ticker mit gueltigem Preis > 0
            mit_preis = [a for a in aktien_liste if a.get("aktuell", 0) > 0]
            bezahlbare = [min(mit_preis, key=lambda a: a["aktuell"])] if mit_preis else []
        top = bewerte(bezahlbare, budget, risk_params=params)
        alle_kandidaten = [{
                "ticker": t["ticker"],
                "preis": t.get("preis", 0),  # bewerte() gibt 'preis' zurück, nicht 'aktuell'
                "score": t.get("score", 0),
                "tier": t.get("tier", 2),
                "atr": t.get("atr", 0),
                "vol_ratio": t.get("vol_ratio", 1),
            } for t in top[:10]]  # Top 10 bewerten, dann filtern
        
        # 🛡 v2.16.8 Budget-Filter (Sicherung): Nur Kandidaten, die das Depot mit 80% des
        # Bargelds kaufen KANN. Teure Top-Scorer (AAPL $308 bei $100 Cash) würden
        # sonst den Prompt dominieren -> KI schlägt unbezahlbare Käufe vor -> nichts passiert.
        kandidaten = [k for k in alle_kandidaten if 0 < k["preis"] <= kauf_budget]
        # Fallback (User-Idee): keine bezahlbaren Kandidaten -> günstigsten mit
        # gueltigem Preis aus der Gesamtliste nehmen, damit das Depot IMMER
        # mindestens eine Kauf-Option hat
        if not kandidaten and alle_kandidaten:
            mit_preis = [k for k in alle_kandidaten if k["preis"] > 0]
            kandidaten = [min(mit_preis, key=lambda k: k["preis"])] if mit_preis else []
        kandidaten = kandidaten[:5]  # max 5 Kandidaten pro Depot
        
        # Priorisiere: Nur Depots mit negativer Rendite ODER vielen Trades bekommen KI
        wert = depot.wert()
        rendite_pct = (wert / depot.start_wert - 1) * 100
        anzahl_pos = len(depot.positions)
        anzahl_trades = len(depot.trades)
        
        # KI-Priorität score (höher = dringender)
        prioritaet = 0
        if rendite_pct < -2:
            prioritaet += 3
        elif rendite_pct < -0.5:
            prioritaet += 2
        if anzahl_pos >= 3:
            prioritaet += 2
        if anzahl_trades > 0 and anzahl_trades % 5 == 0:
            prioritaet += 1
        
        depot_kontexte.append((risk, params, depot, kandidaten, prioritaet))
    
    # ── BÖRSE-AWARE KI-FILTER (v2.15.8) ─────────────────────────────
    # Nur Depots mit mind. einer OFFENEN Position an einer gerade offenen
    # Börse brauchen KI-Bewertung. Das spart KI-Calls, wenn die jeweilige
    # Börse zu ist (z.B. Xetra zu, keine DE-Positionen -> keine Calls).
    # exchanges-Feld (von engine.py) hat Vorrang; Fallback auf Suffix-Mapping.
    try:
        from boersen import boerse_fuer_ticker, ist_offen as _boerse_offen
        _hat_boersen_mod = True
    except Exception:
        _hat_boersen_mod = False
        def boerse_fuer_ticker(t):
            t = (t or "").upper().strip()
            for s, b in ((".DE", "XETRA"), (".F", "XETRA"), (".T", "TSE"),
                         (".HK", "HKEX"), (".L", "LSE")):
                if t.endswith(s):
                    return b
            return "US"
        def _boerse_offen(b):
            return False  # Fallback: bei Modul-Fehler lieber KI-Call machen
    def _depot_hat_offene_boerse(dep):
        pos = getattr(dep, "positions", {}) or {}
        # 🛡 Fix v2.16.8: Depot OHNE Positionen (aber mit Cash) IMMER zur KI lassen —
        # es kann neue Käufe machen. Vorher gab dieser Filter False -> leere Depots
        # wurden nie von der KI bewertet -> kauften nie nach (6 Depots mit 97-120$ Cash).
        if not pos:
            return True
        ex = getattr(dep, "exchanges", {}) or {}
        for t, p in pos.items():
            if (p.get("shares", 0) if isinstance(p, dict) else 0) <= 0:
                continue
            b = ex.get(t) or boerse_fuer_ticker(t)
            if _boerse_offen(b):
                return True
        return False
    depot_kontexte_vor = len(depot_kontexte)
    depot_kontexte = [c for c in depot_kontexte if _depot_hat_offene_boerse(c[2])]
    if not QUIET and len(depot_kontexte) != depot_kontexte_vor:
        print(f"   🌍 Börse-Filter: {depot_kontexte_vor - len(depot_kontexte)} Depots ohne offene Börse übersprungen (spart KI-Calls)", flush=True)
    
    # Sortiere nach Priorität (höchste zuerst), nimm Top 4
    depot_kontexte.sort(key=lambda x: x[4], reverse=True)
    
    # KI-Cache: pro Depot max 1 Call pro 60 Minuten (spart API-Quota)
    KI_CACHE_DAUER = 3600  # 1 Stunde
    jetzt_ts = time.time()
    cache = {}
    cp = os.path.join(BASE, "ki_cache_batch.json")
    if os.path.exists(cp):
        try:
            with open(cp) as f:
                cache = json.load(f)
        except:
            cache = {}
    
    # Filtere: nur Depots die noch keinen Cache-Eintrag haben
    ki_kontexte_frisch = []
    for ctx in depot_kontexte:  # ALLE 20 Depots, nicht nur Top 4
        risk = ctx[0]
        letzter_call = cache.get(str(risk), {}).get("ts", 0)
        if jetzt_ts - letzter_call > KI_CACHE_DAUER:
            ki_kontexte_frisch.append(ctx)
    
    if not QUIET:
        risks = [str(c[0]) for c in ki_kontexte_frisch]
        print(f"   🤖 KI für Depots: {len(risks)} von 20 (Priorität + Cache)", flush=True)
    
    # Rate-Limit-sicher: EIN KI-Call für ALLE Depots (20 auf einmal)
    def ki_call_alleeps(args_list):
        import time as _time
        # Warte falls vorheriger Call noch nicht lange her
        last = getattr(ki_call_alleeps, "_last_call", 0)
        elapsed = _time.time() - last
        if elapsed < 35:
            _time.sleep(35 - elapsed)
        ki_call_alleeps._last_call = _time.time()
        
        # ── v2.16.8: Batches à 5 Depots statt 1 Mega-Prompt (20 Depots) ──
        # Der 20-Depot-Prompt mit max_tokens=4096 überforderte die Free-Provider
        # (>200s, Timeout, Cooldown) -> "KI nicht verfügbar" -> keine Käufe.
        # 4 Calls à 5 Depots = kleinere Prompts, schnellere Antworten, stabiler.
        def depot_to_dict(d):
            return {
                "risk": d.risk,
                "bargeld": d.bargeld,
                "positions": getattr(d, "positions", {}),
                "start": d.start_wert,
            }
        
        depot_dicts = [(risk, params, depot_to_dict(depot), kandidaten, prio) 
                       for risk, params, depot, kandidaten, prio in args_list]
        
        def _baue_prompt(chunk):
            depot_infos = []
            for risk, params, dep, kandidaten, _ in chunk:
                pos_liste = []
                for t, pos in dep.get("positions", {}).items():
                    if pos.get("shares", 0) > 0:
                        preis = hole_kurs_fuer(t)
                        pnl = ((preis / pos["avg_price"]) - 1) * 100 if pos["avg_price"] > 0 else 0
                        pos_liste.append(f"{t}: {pos['shares']:.2f}st @${pos['avg_price']:.2f} (Kurs ${preis:.2f}, P&L {pnl:+.2f}%)")
                
                depot_wert = dep.get("bargeld", 0)
                for t, pos in dep.get("positions", {}).items():
                    if pos.get("shares", 0) > 0:
                        depot_wert += pos["shares"] * hole_kurs_fuer(t)
                
                kandidaten_str = ", ".join(
                    f"{k['ticker']} ${k['preis']:.1f} ({k['preis']/max(dep.get('bargeld',1),0.01)*100:.0f}% Cash)"
                    for k in (kandidaten or [])[:5]
                )
                # 🛡 v2.16.8: Leere Depots (Cash, keine Position) explizit markieren —
                # die KI soll dort KAUFEN, nicht halten.
                hinweis = ""
                if not pos_liste and dep.get('bargeld', 0) >= 20:
                    hinweis = " [LEER: bitte KAUFEN aus den Kandidaten waehlen, die ins Budget passen!]"
                depot_infos.append(f"Risk {risk}: Cash ${dep.get('bargeld',0):.1f}, Wert ${depot_wert:.1f}, "
                                  f"Pos: {', '.join(pos_liste) if pos_liste else 'keine'}, "
                                  f"Kandidaten: {kandidaten_str or 'keine'}{hinweis}")
            
            prompt = f"Analysiere {len(chunk)} Aktien-Depots. Entscheide pro Depot: Welche Positionen KAUFEN/VERKAUFEN/HALTEN.\n\n"
            prompt += "\n".join(depot_infos)
            prompt += "\n\nAntworte NUR mit JSON [{\"risk\":0, \"aktionen\":[{\"ticker\":\"AAPL\",\"aktion\":\"kaufen\"|\"verkaufen\"|\"halten\",\"menge\":\"voll\"|\"teil\",\"grund\":\"...\"}]}]\n"
            # TEMP-DEBUG (v2.16.8): Prompt fuer Diagnose loggen
            try:
                if any(f"Risk {c[0]}:" in prompt for c in chunk):
                    with open(os.path.join(BASE, "_prompt_debug.txt"), "w", encoding="utf-8") as _pf:
                        _pf.write(prompt)
            except Exception:
                pass
            return prompt
        
        BATCH_GROESSE = 5
        results = {}
        chunks = [depot_dicts[i:i+BATCH_GROESSE] for i in range(0, len(depot_dicts), BATCH_GROESSE)]
        if not QUIET and len(chunks) > 1:
            print(f"   📦 KI-Batches: {len(chunks)} x {BATCH_GROESSE} Depots", flush=True)
        
        for chunk in chunks:
            prompt = _baue_prompt(chunk)
            try:
                raus, provider_genutzt = call_ki(
                    [
                        {"role": "system", "content": "Du antwortest NUR mit JSON. Kein Denken, keine Erklärung, nur das JSON-Array."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2000,
                )
            except Exception as e:
                if not QUIET:
                    print(f"   ⚠ KI-Batch Fehler: {e}", file=sys.stderr, flush=True)
                raus = None
            
            if not raus:
                # KI nicht verfuegbar (Rate-Limit/Cooldown) -> naechster Batch versuchen,
                # am Ende sauber mit dem abbrechen, was wir haben.
                if not QUIET:
                    print(f"   ⚠ KI-Batch ohne Antwort (Provider gedrosselt/Cooldown) — übersprungen", flush=True)
                continue
            
            if not QUIET and provider_genutzt:
                print(f"   KI via {provider_genutzt}", flush=True)
        
        # JSON extrahieren (robust)
            entscheidungen = _parse_ki_json(raus)
            if entscheidungen is None:
                if not QUIET:
                    print(f"   ⚠ KI-JSON ungültig, Fallback auf 'halten'", flush=True)
                    print(f"   🔍 KI-RAW: {raus[:500]}", flush=True)  # DEBUG: raw response
                entscheidungen = []
            
            # Konvertiere zu depot_action Format
            for ed in entscheidungen:
                risk_val = ed.get("risk")
                if risk_val is not None:
                    depot_dict = next((c for c in args_list if c[0] == risk_val), None)
                    if depot_dict:
                        depot_obj = depot_dict[2]  # Depot-Objekt
                        params = depot_dict[1]
                        kandidaten = depot_dict[3]
                        aktionen = []
                        for a in ed.get("aktionen", []):
                            ticker = a.get("ticker", "")
                            akt = a.get("aktion", "halten")
                            grund = a.get("grund", "KI-Entscheidung")
                            if akt == "kaufen":
                                cand = next((k for k in (kandidaten or []) if k["ticker"] == ticker), None)
                                if cand and cand.get("preis", 0) > 0:
                                    menge_faktor = 1.0 if a.get("menge") == "voll" else 0.5
                                    budget = depot_obj.bargeld * menge_faktor
                                    menge = budget / cand["preis"]
                                    aktionen.append({
                                        "typ": "kaufen", "ticker": ticker,
                                        "menge": round(menge, 4), "preis": cand["preis"],
                                        "grund": f"🤖 KI: {grund[:50]}",
                                        "tier": cand.get("tier", 2),
                                    })
                            elif akt == "verkaufen":
                                pos = getattr(depot_obj, "positions", {}).get(ticker, {})
                                if pos.get("shares", 0) > 0:
                                    menge_faktor = 1.0 if a.get("menge") == "voll" else 0.5
                                    preis = hole_kurs_fuer(ticker)
                                    # 🛡 Fix: Verkauf zum Preis 0/None verhindern (yfinance Rate-Limit
                                    # liefert 0 -> Erlös 0, Position verschwindet ohne Bargeld-Gutschrift)
                                    if not preis or preis <= 0:
                                        if not QUIET:
                                            print(f"   🛡 KEIN VERKAUF {ticker}: Kurs {preis} (Rate-Limit/Fehler) — Position behalten", flush=True)
                                        continue
                                    aktionen.append({
                                        "typ": "verkaufen", "ticker": ticker,
                                        "menge": round(pos["shares"] * menge_faktor, 4),
                                        "preis": preis,
                                        "grund": f"🤖 KI: {grund[:50]}",
                                    })
                        
                        ki_letzte = {
                            "typ": "decision",
                            "zeit": datetime.now().isoformat(),
                            "aktion": ed.get("analyse", ed.get("kommentar", ""))[:60] or f"KI Risk {risk_val}",
                            "konfidenz": ed.get("konfidenz", 50),
                            "analyse": ed.get("analyse", ed.get("kommentar", "")),
                            "ticker": f"Risk {risk_val}",
                        }
                        schreibe_ki_log(ki_letzte)
                        results[risk_val] = (depot_obj, params, {"aktionen": aktionen, "ki_letzte": ki_letzte})
                        # Cache aktualisieren
                        cache[str(risk_val)] = {"ts": time.time(), "aktionen": aktionen, "ki_letzte": ki_letzte}
                        
                        if not QUIET:
                            print(f"   🤖 KI[Risk {risk_val}]: {len(aktionen)} Aktionen (K:{ki_letzte['konfidenz']})", flush=True)
            if not QUIET and len(chunks) > 1:
                print(f"   ✅ Batch {chunks.index(chunk)+1}/{len(chunks)} verarbeitet", flush=True)
        return results
    
    if ki_kontexte_frisch:
        ki_ergebnisse = ki_call_alleeps(ki_kontexte_frisch) or {}
        # Cache speichern
        with open(cp, "w") as f:
            json.dump(cache, f, ensure_ascii=False)
    else:
        ki_ergebnisse = {}
    
    # Restliche Depots: Cache verwenden oder leer
    for risk in RISK_STUFEN:
        if risk not in ki_ergebnisse:
            depot = laden_oder_erstellen(risk)
            params = fuer_risk_stufe(risk)
            # Cache-Eintrag?
            cached = cache.get(str(risk), {})
            if cached and jetzt_ts - cached.get("ts", 0) < KI_CACHE_DAUER:
                # Verwende gecachte Entscheidung
                ki_letzte_cached = cached.get("ki_letzte")
                aktionen_cached = cached.get("aktionen", [])
                ki_ergebnisse[risk] = (depot, params, {"aktionen": aktionen_cached, "ki_letzte": ki_letzte_cached})
                if not QUIET and ki_letzte_cached:
                    print(f"   💾 Cache[Risk {risk}]: {len(aktionen_cached)} Aktionen", flush=True)
            else:
                ki_ergebnisse[risk] = (depot, params, {"aktionen": [], "ki_letzte": depot.ki_letzte})

    # Ausführen (sequentiell, da Datei-IO)
    for risk in RISK_STUFEN:
        if risk not in ki_ergebnisse:
            continue
        depot, params, ki_ergebnis = ki_ergebnisse[risk]
        aktionen = ki_ergebnis["aktionen"]
        depot.ki_letzte = ki_ergebnis["ki_letzte"]

        # Ausführen
        buys = [a for a in aktionen if a["typ"] == "kaufen"]
        sells = [a for a in aktionen if a["typ"] == "verkaufen"]

        for a in aktionen:
            ausführen(depot, [a], params)
            if not QUIET:
                t = a["ticker"]
                if a["typ"] == "kaufen":
                    print(f"   🟢 Kauf {t} {a['menge']:.2f}st @${a['preis']:.2f} (Tier {a.get('tier','?')}) – {a.get('grund','')}", flush=True)
                elif a["typ"] == "verkaufen":
                    print(f"   🔴 Verkauf {t} {a['menge']:.2f}st @${a['preis']:.2f} – {a.get('grund','')}", flush=True)

        # Historie
        historie_aktualisieren(depot)
        depot.speichern()

        wert = depot.wert()
        rendite_pct = (wert / depot.start_wert - 1) * 100
        ergebnisse.append((risk, wert, depot.bargeld, rendite_pct, len(depot.positions), len(depot.trades)))

    # ─── Ergebnis-Tabelle ────────────────────────────────
    ges_wert = sum(e[1] for e in ergebnisse)
    ges_start = len(RISK_STUFEN) * 100
    print(f"\n{'='*60}", flush=True)
    print(f"📊 {len(RISK_STUFEN)} Depots | Trades: {sum(e[5] for e in ergebnisse)} | Gesamtwert: ${ges_wert:.2f}", flush=True)
    print(f"{'='*60}", flush=True)
    print(f" {'Risk':>5} {'Wert':>8} {'Cash':>7} {'Rendite':>8} {'Pos':>3} {'Trades':>6}", flush=True)
    print(f"{'─'*42}", flush=True)
    for risk, wert, cash, rendite, pos, trades in ergebnisse:
        farbe = "🟢" if rendite > 0 else ("🔴" if rendite < -0.1 else "⚪")
        invest_pct = (1 - cash/wert) * 100 if wert > 0 else 0
        print(f" {farbe} {risk:>4} ${wert:>6.2f} ${cash:>5.2f}  {rendite:>+6.2f}%  {pos:>2}  {trades:>4}", flush=True)

    # Zusammenfassung
    investiert = ges_wert
    gesamt_rendite = (ges_wert / ges_start - 1) * 100
    print(f"\n💰 Gesamt: ${investiert:.2f} von ${ges_start:.0f} ({gesamt_rendite:+.2f}%)", flush=True)

    # Best/Worst
    best = max(ergebnisse, key=lambda x: x[3])
    worst = min(ergebnisse, key=lambda x: x[3])
    print(f"🏆 Best: Risk {best[0]} ({best[3]:+.2f}%)  |  😱 Worst: Risk {worst[0]} ({worst[3]:+.2f}%)", flush=True)

    # Save summary
    summary = {
        "zeit": datetime.now().isoformat(),
        "depots": len(RISK_STUFEN),
        "gesamtwert": round(ges_wert, 2),
        "gesamt_rendite": round(gesamt_rendite, 2),
        "best_risk": best[0],
        "best_rendite": round(best[3], 2),
        "worst_risk": worst[0],
        "worst_rendite": round(worst[3], 2),
        "trades": sum(e[5] for e in ergebnisse),
        "detail": [{"risk":r, "wert":round(w,2), "rendite":round(rend,2), "pos":p, "trades":t}
                   for r,w,_,rend,p,t in ergebnisse],
    }
    spfad = os.path.join(BASE, "batch_summary.json")
    with open(spfad, "w") as f:
        json.dump(summary, f, indent=2)

    # Status speichern
    try:
        from trader_status import update_status
        update_status("batch_trader", {
            "depots": len(RISK_STUFEN),
            "trades": sum(e[5] for e in ergebnisse),
            "rendite": round(gesamt_rendite, 2),
        })
    except Exception:
        pass

    # System-Log
    try:
        from system_log import log_eintrag
        level = "ok" if gesamt_rendite >= 0 else "warn"
        log_eintrag("batch", f"Batch-Lauf: {len(RISK_STUFEN)} Depots, "
                    f"{sum(e[5] for e in ergebnisse)} Trades, Rendite {gesamt_rendite:+.2f}%", level)
    except Exception:
        pass


if __name__ == "__main__":
    main()
