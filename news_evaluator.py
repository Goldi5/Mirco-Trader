#!/usr/bin/env python3
"""Bewertet News-Headlines via KI (OpenCode-Go API) und speichert in ki_log.json.

Läuft nur wenn:
  - Letzte Evaluierung >= 2h her
  - Neue/unbewertete Headlines vorhanden
  - OPENCODE_GO_API_KEY gesetzt

Aufruf: python news_evaluator.py
"""
import json, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path

BASE = os.path.dirname(os.path.abspath(__file__))
NEWS_CACHE = os.path.join(BASE, "news_cache.json")
KI_LOG    = os.path.join(BASE, "ki_log.json")

# .env aus Hermes-Config laden
for cand in [os.path.join(BASE, ".env"),
             os.path.expanduser("~/AppData/Local/hermes/.env")]:
    if os.path.exists(cand):
        with open(cand) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

MINDEST_ABSTAND = timedelta(hours=2)
BATCH_SIZE = 10

# Provider-Konfiguration – erst Go, dann Zen probieren
API_KEY  = (os.environ.get("OPENCODE_GO_API_KEY") or os.environ.get("OPENCODE_ZEN_API_KEY"))
GO_URL   = os.environ.get("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1")
ZEN_URL  = os.environ.get("OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1")
MODEL_GO = os.environ.get("KI_MODEL", "deepseek-v4-flash")
MODEL_ZEN = os.environ.get("KI_MODEL_ZEN", "deepseek-v4-flash-free")


try:
    from openai import OpenAI
except ImportError:
    print("Fehler: 'openai' package nicht installiert. Führe 'uv pip install openai' aus.", file=sys.stderr)
    sys.exit(1)


def lade_news():
    if not os.path.exists(NEWS_CACHE):
        return []
    with open(NEWS_CACHE, encoding="utf-8") as f:
        return json.load(f).get("headlines", [])


def lade_ki_log():
    if not os.path.exists(KI_LOG):
        return []
    with open(KI_LOG, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def bereits_bewertet_titel(ki_log):
    return {e.get("title", "").strip().lower() for e in ki_log}


def letzte_evaluierung(ki_log):
    zeiten = []
    for e in ki_log:
        z = e.get("zeit", "")
        if z:
            try:
                zeiten.append(datetime.fromisoformat(z))
            except ValueError:
                pass
    return max(zeiten) if zeiten else None


def batch_evaluieren(client, model, headlines):
    """Sendet Batch Headlines an KI und parst Ergebnis."""
    prompt = (
        "Du bewertest Börsen-News für ein Paper-Trading-System. "
        "Gib ein JSON-Array zurück:\n\n"
        "[\n"
        '  {"title": "Headline", "score": 0-100, "topics": ["markt","tech","earnings",\n'
        '   "geopolitik","energie","zinsen","regulation","sonstiges"],\n'
        '   "tickers": ["AAPL"], "reason": "kurzer Grund"},\n'
        "  ...\n"
        "]\n\n"
        "Score = Relevanz für Aktien-Trading (0=unwichtig, 100=sehr relevant).\n"
        "Wähle 1-2 passende topics aus der Liste. Nenne Ticker wenn erkennbar.\n"
        "Antworte NUR mit dem JSON-Array.\n\n"
        "Headlines:\n"
    )
    for h in headlines:
        prompt += f"- {h.get('title','?')}\n"

    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
        )
        raus = r.choices[0].message.content.strip()
        # JSON extrahieren
        start = raus.find("[")
        end  = raus.rfind("]") + 1
        raus = raus[start:end] if start >= 0 and end > 0 else raus
        bewertungen = json.loads(raus)
        if not isinstance(bewertungen, list):
            raise ValueError("Kein Array")
        return bewertungen
    except Exception as e:
        print(f"Fehler bei KI-Evaluierung: {e}", file=sys.stderr)
        return [
            {"title": h.get("title",""), "score": 50, "topics": ["sonstiges"],
             "tickers": [], "reason": "Fehler bei KI-Bewertung"}
            for h in headlines
        ]


def sternzahl(score):
    if score >= 70:  return "⭐⭐⭐"
    elif score >= 45: return "⭐⭐"
    elif score >= 20: return "⭐"
    return ""


def main():
    jetzt = datetime.now().isoformat()
    news = lade_news()
    ki_log = lade_ki_log()

    if not news:
        print("Keine News vorhanden.")
        return

    # Prüfen ob genug Zeit seit letzter Evaluierung vergangen
    letzte = letzte_evaluierung(ki_log)
    if letzte:
        abstand = datetime.now() - letzte.replace(tzinfo=None)
        if abstand < MINDEST_ABSTAND:
            print(f"Skip: letzte Evaluierung vor {int(abstand.total_seconds()//60)} Min "
                  f"(min {int(MINDEST_ABSTAND.total_seconds()//60)} Min)")
            return

    # Nur unbewertete Headlines
    bekannte = bereits_bewertet_titel(ki_log)
    neue = [h for h in news if h.get("title","").strip().lower() not in bekannte]

    if not neue:
        print("Keine neuen/unbewerteten Headlines.")
        return

    if not API_KEY:
        print("Fehler: Kein API-Key. Setze OPENCODE_GO_API_KEY oder OPENCODE_ZEN_API_KEY.", file=sys.stderr)
        return

    # Client erstellen – versuche Go, fallback zu Zen
    client = None
    model = MODEL_GO
    try:
        client = OpenAI(api_key=API_KEY, base_url=GO_URL)
        # Test-Call
        client.chat.completions.create(model=model, messages=[{"role":"user","content":"test"}], max_tokens=1)
        base_url = GO_URL
        print(f"Nutze OpenCode Go ({base_url}, Modell {model})")
    except Exception as e1:
        print(f"Go nicht verfügbar ({e1}), versuche Zen...", file=sys.stderr)
        model = MODEL_ZEN
        try:
            client = OpenAI(api_key=API_KEY, base_url=ZEN_URL)
            client.chat.completions.create(model=model, messages=[{"role":"user","content":"test"}], max_tokens=1)
            base_url = ZEN_URL
            print(f"Nutze OpenCode Zen ({base_url}, Modell {model})")
        except Exception as e2:
            print(f"Fehler: Weder Go noch Zen verfügbar: {e2}", file=sys.stderr)
            return
    print(f"Bewerte {len(neue)} neue Headlines (von {len(news)} gesamt, Modell {model})...")

    neue_eintraege = []
    for i in range(0, len(neue), BATCH_SIZE):
        batch = neue[i:i+BATCH_SIZE]
        bewertungen = batch_evaluieren(client, model, batch)

        for bw in bewertungen:
            orig = next(
                (h for h in batch if h.get("title","").strip().lower() == bw.get("title","").strip().lower()),
                batch[0] if batch else {}
            )
            titel = orig.get("title", bw.get("title", ""))
            score = bw.get("score", 50)
            neue_eintraege.append({
                "zeit": jetzt,
                "typ": "news",
                "title": titel,
                "score": score,
                "stars": sternzahl(score),
                "topics": bw.get("topics", ["sonstiges"]),
                "tickers": bw.get("tickers", []),
                "reason": bw.get("reason", ""),
                "link": orig.get("link", ""),
            })

        if i + BATCH_SIZE < len(neue):
            time.sleep(1)

    # An ki_log.json anhängen
    ki_log.extend(neue_eintraege)
    if len(ki_log) > 500:
        ki_log = ki_log[-500:]

    with open(KI_LOG, "w", encoding="utf-8") as f:
        json.dump(ki_log, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(neue_eintraege)} Headlines bewertet – ki_log.json aktualisiert "
          f"(jetzt {len(ki_log)} Einträge gesamt)")


if __name__ == "__main__":
    main()
