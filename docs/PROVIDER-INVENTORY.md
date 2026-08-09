# PROVIDER-INVENTORY.md

> **Phase 0 — Bestandsaufnahme** (2026-08-09, Stand v2.38.1)
> Alle Provider mit ihren Status, Keys (nur Namen), Rotation und Fallback-Verhalten — geprüft gegen Code.

---

## 1. Marktdaten-Provider (`marktdaten.py`, Super-Mix, 4-Tier)

| Tier | Quelle | Key (`.env`) | Drossel | Nutzung | Status |
|---|---|---|---|---|---|
| 1 | yfinance | — (kostenlos) | — | Bulk-Scan (663 Ticker, Hist/RSI/MACD), Kurs-Fallback | ✅ aktiv |
| 2 | Finnhub | `FINNHUB_KEY` | 60 s | Kurs bei yfinance-Exception | ✅ Key vorhanden |
| 3 | TwelveData | `TWELVEDATA_KEY` | 1 h | Kurs bei Finnhub-Drossel | ✅ Key vorhanden |
| 4 | AlphaVantage | `ALPHAVANTAGE_KEY` | — | Kurs bei TwelveData-Drossel | ✅ Key vorhanden |

**Mechanik:**
- `hole_kurs(ticker)` rotiert durch die Tiers; Kurs=0 wird nie nach oben durchgereicht (Crash-Schutz).
- Drossel-Verwaltung: `_gedrosselt()` / `_setze_drossel()` (in-memory + Persistenz via `_drossel_zeit`).
- Bulk-Fallback: `scan_fallback_yfinance()` → TwelveData `time_series`.

**Lücken (Auftrag §6/§7/§12):**
- Kein `MarketSnapshot`-Objekt; Trading-Core ruft yfinance/TwelveData direkt.
- Kein Providerstatus (`HEALTHY/DEGRADED/…`), kein `last_success_at/last_error` je Verbindung.
- `markt_daten`-Tabelle wird **nicht** befüllt (0 Zeilen) — nur ad-hoc Scans.
- Fallback ist global, nicht tenant-/verbindungs-bewusst (Auftrag §6 „Provider-Fallback darf nicht blind global rotieren").
- Kein Datenqualitäts-Tracking (source_latency, quality) im Trading-Pfad.

## 2. KI-Provider (`ki_provider.py`, Rotation)

### Cron-Kette (`_baue_provider_liste_cron`, Batch/KI-Läufe)
| # | Name | Base-URL | Modell | Key |
|---|---|---|---|---|
| 1 | `zen` | opencode.ai/zen/v1 | `deepseek-v4-flash-free` | `OPENCODE_ZEN_API_KEY` |
| 2 | `zen-nemotron` | opencode.ai/zen/v1 | `nemotron-3-ultra-free` | `OPENCODE_ZEN_API_KEY` |
| 3 | `nous-step` | inference-api.nousresearch.com/v1 | `stepfun/step-3.7-flash:free` | Nous-OAuth (`~/AppData/Local/hermes/shared/nous_auth.json`) |
| 4 | `nous-hy3` | inference-api.nousresearch.com/v1 | `tencent/hy3:free` | Nous-OAuth |
| 5 | `openrouter` | openrouter.ai/api/v1 | `nvidia/nemotron-3-ultra-550b-a55b:free` | `OPENROUTER_API_KEY` |

### Chat-Kette (`_baue_provider_liste_chat`, User-Chat, temp=0.3)
- Primär nemotron/deepseek via zen (free, schnell), OpenRouter als Puffer — verbraucht **nicht** die Nous-Free-Quota des Crons.

**Mechanik:**
- `call_ki(messages, temperature, max_tokens)` rotiert bei Fehler/Rate-Limit auf nächsten Provider.
- `ki_faehig()` prüft Key-Verfügbarkeit; `_nous_creds()`/`_nous_refresh()` verwalten den Nous-OAuth-Refresh.
- `max_tokens=1024` (ki_decisions Z275) — 512 war zu klein (JSON abgeschnitten).
- Reasoning-Modelle (nous-hy3/nous-step) brauchen ≥1024 Tokens; `reasoning_content` wird akzeptiert; leere Antworten lösen **keinen** Cooldown mehr aus.

**Lücken (Auftrag §6):**
- KI-Provider sind global konfiguriert (Env/OAuth), nicht tenant-/user-scoped.
- Kein `provider_connections`-Eintrag für die aktive Kette (Tabelle leer).
- Kein Rate-Limit-/Status-Tracking je Verbindung in der DB.

## 3. Broker/Execution-Provider

| Adapter | Datei/Zeile | Umfang | Status |
|---|---|---|---|
| `BrokerProvider` (Interface) | security.py Z532 | connect/disconnect/health/account/buying_power/positions/quote/open_orders/place_order/cancel_order/order_status | ✅ |
| `PaperBrokerAdapter` | security.py Z571 | virtuelle Orders, virtuelles Portfolio (paper_orders/positions), Environment PAPER | ✅ |

**Lücken (Auftrag §8):**
- Kein `Simulator`-/`Sandbox`-Adapter (nur PAPER).
- Kein LIVE-Adapter (gewollt — PAPER_ONLY; erst nach Phase 18).
- `paper_portfolios`/`paper_orders`/`paper_positions` leer (Adapter ungenutzt; der Cron kauft weiter über engine.py-Datei-JSON).
- Broker-Umgebung steckt nicht in jeder Order (Auftrag §8: „Umgebung muss in jeder Order enthalten sein").

## 4. Secret-Store (`secret_store`-Tabelle + `security.secret_*`)

| Aspekt | Befund |
|---|---|
| Tabelle | `secret_store` (tenant_id, secret_key, secret_value, created_at, updated_at) |
| Einträge | 1: `OPENAI_API_KEY` (Länge 10 — Testwert) |
| APIs | `secret_set/get/list_keys` (security.py + db.py) |
| Maskierung | API `list_keys` zeigt nur Schlüsselnamen; volle Keys nie in UI — **jedoch keine `****…letzte 4`-Maske in Routen geprüft** |
| Logging | kein Hinweis auf Secret-Ausgabe in Logs gefunden |

**Lücken (Auftrag §6 Secret-Regeln):**
- Keine Rotation (`provider.rotate`), kein `last_test_at/last_error`, kein Ablaufdatum (`EXPIRED`-Status).
- `.env`-Keys (FINNHUB/TWELVEDATA/ALPHAVANTAGE) liegen **nicht** im Secret-Store, sondern in `.env` (git-ignored? prüfen) — Ziel: Secret-Referenzen statt Env.
- Kein Audit bei Set/Rotation (nur `audit_log` generisch möglich).

## 5. Audit-Datenquellen (Security-Events)

| Quelle | Format | Einträge |
|---|---|---|
| `security_audit.json` | JSONL (1 JSON pro Zeile) | 1.722 |
| `login_rate.json` | JSON | Test-Reste (203.0.113.7, 198.51.100.23, `__v23__` 5 Fehlversuche) |
| `security_users.json` | JSON | 1 User (admin, superadmin, MFA aus), **422 Sessions** |

## 6. Empfohlene Provider-Phase-Reihenfolge (aus Auftrag §19)

```text
8.  Provider-Datenmodell (Status UNCONFIGURED…EXPIRED, tenant-scoped, is_default)
9.  Secret-/Connection-Manager (Rotation, Test, Maskierung, Audit)
10. Datenprovider-Abstraktion (MarketSnapshot, Interfaces, Qualitäts-Fallback)
11. Paper-/Simulator-Broker (Simulator-Adapter)
19. Sandbox-Brokerintegration (erst nach Phase 18 Tests)
```
