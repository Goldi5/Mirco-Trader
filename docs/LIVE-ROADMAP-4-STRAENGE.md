# Live-Roadmap: 4 Arbeitsstränge (News / Notfallsteuerung / Broker / Freigabe)

**Datum:** 2026-08-10
**Autor:** Hermes (Strategie-Entwurf auf Basis Handoff-V3.pdf + Ist-Analyse)
**Status:** Planung, keine Implementierung begonnen
**Vault-Spiegel:** `Projekte/Micro-Trader/Micro-Trader-Live-Roadmap.md`

---

## Zusammenfassung

Der Übergang von Paper-Only zu verantwortbarem Live-Betrieb wird in **vier getrennte Arbeitsstränge** aufgeteilt (nicht ein einziger Live-Umbau):

1. **Professionelle News-Pipeline** — strukturierte News-Bewertung (P0–P3), Ticker-Zuordnung, Deduplizierung, KI-Impact in Trading-Prompt.
2. **Manuelle Notfall- & Depotsteuerung** — PAUSE/CANCEL/CLOSE/SUSPEND, Kill-Switch (jetzt im Paper-Modus baubar).
3. **Broker-/Trading-Plattform** — `BrokerProvider`-Interface, `PaperBrokerAdapter` → Sandbox → Live (Alpaca als Kandidat, EU-Reality-Check nötig).
4. **Regulatorischer & technischer Live-Freigabeprozess** — Live-Antrag, Micro-Live-Bedingungen.

## Ist-Zustand (verifiziert)

- ✅ Vorhanden: Tenant-Isolation, Order-Intent (15-Check), Risiko-Gates, Vier-Augen, KI-Pool (repariert 7a9bcc1).
- ⚠️ Teilweise: News-Monitor (RSS, aber kein Ticker-Map/Dedup), `news_evaluator.py` (alter `OPENCODE_GO_API_KEY`).
- ❌ Fehlt: `markt_daten` leer (blockiert Shadow→Paper), man. Depotsteuerung, echte Broker-Adapter.

## Kritische Blocker (zuerst fixen)

1. **`markt_daten` leer** → `monitor_boerse.py` muss in DB persistieren (nicht nur /data-Cache).
2. **News nicht strukturiert** → `news_evaluator.py` auf `ki_provider.call_ki` umstellen + Schema erweitern.
3. **Kein Kill-Switch** → `SUSPEND_TRADING`/`CLOSE_ALL_TENANT_PORTFOLIOS` im Paper-Modus bauen.

## Empfohlene Reihenfolge (12 Schritte)

| # | Schritt | Priorität |
|---|---|---|
| 1 | markt_daten-Persistenz fixen | P0 (Blocker) |
| 2 | News-Pipeline strukturieren (Ticker-Map, Dedup, Schema) | P0 |
| 3 | News-Prompt + 15-Min-Zyklus + P0-Eventweg | P1 |
| 4 | Man. Depot-Schließen (PAUSE/CANCEL/CLOSE/SUSPEND) | P0 (Notfall) |
| 5 | MarketSnapshot + Snapshot-ID in KI | P1 |
| 6 | Broker EU-Verfügbarkeit prüfen (Alpaca DE?) | P1 |
| 7 | PaperBrokerAdapter + Dashboard-Ansicht | P1 |
| 8 | Sandbox-Adapter anbinden | P2 |
| 9 | Brokerdaten im Dashboard | P2 |
| 10 | Order-Sync + Fehlerzustände | P2 |
| 11 | Live-Freigabeprozess testen | P3 |
| 12 | Micro-Live vorbereiten | P3 |

## Leitprinzip

**Nicht direkt mit Echtgeld starten.** Die Brücke Paper→Live ist: News + man. Schließung + persistierte Marktdaten + Sandbox-Broker + vollständiger Order-Sync.

## Nächste Entscheidungen

- [ ] Alpaca für DE-Wohnsitz verfügbar? (sonst EU-Broker)
- [ ] News-Quellen EU-IR (SEC nur US)
- [ ] Wer darf SUSPEND_TRADING (superadmin + MFA?)
- [ ] Welcher KI-Provider für News (openrouter nemotron-nano?)
