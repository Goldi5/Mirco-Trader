## [2.29.0] - 2026-08-08
### Added (PHASE 5: Trading-Modi-Zustandsmaschine — Mandanten-Ausbauauftrag)
- **8 Zustaende:** SHADOW/PAPER/LIVE_REQUESTED/LIVE_APPROVED/LIVE_ACTIVE/PAUSED/SUSPENDED/REVOKED.
- **db.py:** `trading_mode_transitions` Tabelle (Sektion 8 Pflichtfelder), `MODE_TRANSITIONS`, `mode_log_insert`/`mode_log_list`.
- **security.py:** `get_trading_mode`/`set_trading_mode` (erzwingt erlaubte Transition, `ValueError` sonst), `trading_mode_history`.
- **dashboard.py:** `/api/trading_mode` (GET), `/api/trading_mode/set` (POST, TENANT_ADMIN), `/api/trading_mode/history`.
- **ROUTE_ACCESS:** 3 neue Routen auf TENANT_ADMIN.
- **Tests:** Sektion 7e (+12) → **86 OK, 0 FAIL**.
- **PAPER_ONLY bleibt** — keine Live-Ausfuehrung.

## [2.28.0] - 2026-08-08
### Added (PHASE 4: Mandantentrennung — Mandanten-Ausbauauftrag)
- **Depot-Datentraeger pro Tenant:** SQLite-Tabellen `depots`/`etf_depots`/`spec_depots` (tenant_id).
- **`_tenant_scoped_depot_files(tid)`:** scannt alle Depot-JSONs, filtert auf `tenant_id` (Default 1).
- **`data()` lädt nur Depots des aktiven Tenants** (kein globaler Mix).
- **API-Tenant-Scope:** `/api/ki_log` (nur Tenant-Einträge), `/depot_json` (403 bei Fremd-Tenant), `/api/db_query` (erzwingt Session-Tenant, schließt PHASE-0-Lücke).
- **db.py:** `query_trades`/`query_ki` tenant_id-Parameter, `depot_register`/`depot_list_tenant`.
- **Tests:** Sektion 7d (+5) → **74 OK, 0 FAIL**.
- **Doku:** MULTI-TENANT-SECURITY-TESTPLAN.md.
- **PAPER_ONLY bleibt** — kein Live-Code.

## [2.27.0] - 2026-08-08
### Added (Rollen-/Berechtigungsmodell, PHASE 2 Mandanten-Ausbau)
- **Effektive Rolle** (`security.py`): Membership-Rolle im Tenant gewinnt vor globaler User-Rolle — User kann in Tenant A `admin`, in Tenant B `user` sein.
- **`TENANT_ROLE_PERMISSIONS`**: tenant-bezogene Permissions (`tenant_view`, `tenant_trade_control`, `tenant_manage`, `tenant_members`, `tenant_delete`). `tenant_delete` nur superadmin.
- **Neue Zugriffsklasse `TENANT_ADMIN`**: `before_request` prüft gegen die effektive Rolle (statt globaler) und setzt den Tenant-Kontext aus der Session. Systemweite Routen (`/api/tenants*`, `/api/users*`) bleiben global ADMIN — Tenant-Admin erreicht sie NICHT (403).
- **Decorators**: `require_tenant_role(min_role)` + `require_permission(perm)` (Tenant-Kontext).
- **API**: `GET /api/roles` (Rollenkatalog, TENANT_ADMIN), `GET /api/me/permissions` (effektive Rechte), `/api/me` um `effective_role`/`tenant_permissions` erweitert.
- **UI**: Mein-Konto zeigt effektive Rolle im Mandant (Chip, wenn abweichend).
- **Doku**: `ROLE-PERMISSION-MODEL.md`.
- **Tests**: Sektion 7c (14 neue) → **69 OK, 0 FAIL**.

## [2.26.0] - 2026-08-08
### Added (Mandanten-Modell, PHASE 1 Mandanten-Ausbau)
- SQLite-Tabellen `tenants`, `tenant_memberships`, `workspaces` (idempotente Migration).
- `tenant_id`-Spalten auf `trades`/`ki_decisions`.
- Tenant-Kontext aus Session (OWASP: nie vom Client) via ContextVar.
- Admin-Routen `/api/tenants`, `/api/tenants/create`, `/api/tenants/<id>/members`.
- UI: Mandant-Anzeige im Mein-Konto-Tab.
- Doku: `TENANT-DATA-MODEL.md`; Tests Sektion 7b (10 neue) → 55 OK.

## [2.25.1] - 2026-08-08
### Removed
- Drawdown-Warnungsbalken (kein Mehrwert).

## [2.20.2] - 2026-08-08
### Fixed (Risk 70 kauft endlich)
- **`batch_trader.py` Budget-Filter** (Z116-117 + Z146-148): `kauf_budget = depot.bargeld * 0.8` → `depot.bargeld * params["position_size"] * 1.5`.
  - Vorher: Risk 70 mit $107 Cash hatte `kauf_budget=$85.78` → nur Riesen-Einzelpositionen (> $85) erlaubt → keine Small-Caps ($5-30) → keine Kandidaten → keine Käufe.
  - Nachher: `kauf_budget=$52.27` → Small-Caps kommen durch → KI entscheidet → Käufe möglich.
- **Verifiziert** (Ad-hoc-Test mit echten Indikatoren): Risk 70 `bewerte()` liefert 4 Aktien (SOFI/CLOU/LGI/TNDM), KI-Kandidaten da. Penny-Penalty greift (Small-Caps > Penny-Score).
- **Root-Cause war zweigeteilt:** (1) Budget-Filter zu eng + (2) `bewerte()` braucht Indikatoren (rsi/macd/bb/atr), sonst fällt alles unter `min_score=27`. Im echten `scan_markt` sind Indikatoren gegeben.

### Changed (vorher 2.20.1)
- (siehe 2.20.0 für strategie.py SSOT)

## [2.20.1] - 2026-08-07
### Fixed (strategie.py Selbsttest)
- Assertion `volumen_pos_size(0.20)` → `volumen_pos_size(0.10)` korrigiert (0.20 liegt zwischen Dämpfer-Stufen, korrekt 0.70). Selbsttest grün.

## [2.20.0] - 2026-08-07
### Added (Zentrale Strategie-Config)
- **Neue Datei `strategie.py`** (Single Source of Truth): Alle weichen Bewertungsregeln zentral.
  - `preis_score()`: Penny-Penalty (<$5 → -10), Small-Cap-Bonus ($5-30 → +8), Expensive (>$30 → +3)
  - `volumen_pos_size()`: Volumen-Dämpfer (0.3x→70%, 0.15x→40%, 0.08x→Verzicht)
  - `ist_hebel_etf()`: Hebel-ETF-Erkennung (Liste + Tier 3/4)
  - `STRATEGIE_HINWEISE`: KI-Prompt-Baustein (Volumen/Hebert/Tier-Mix)
- **Refactor:** `engine.bewerte()`, `etf_trader.etf_bewerte()`, `ki_decisions.STRATEGIE_HINWEISE` lesen jetzt aus `strategie.py` — keine hartcodierten Regelwerte mehr in den Modulen.
- **Konsistenz:** Penny-Penalty gilt jetzt für **Aktien + ETF + Spec** (vorher nur Aktien). Bug gefixt: ETF hatte altes "billig=mehr Score" Bias.
- **Verifiziert:** 3x Prüfung (Syntax/Import, Konsistenz, Verhalten+Integration) alle PASS.

## [2.19.7] - 2026-08-07
### Changed (Spec-Watchlist Masse)
- **`spec_watch.py` `WATCHLIST`**: 49 → **169 Ticker** (+120). Mehr Krypto/Leveraged/Volatility/Commodity/AI/EV/Biotech/Meme/Space/Fintech/Retail/Energy/Gaming/Cannabis. Ziel: KI hat pro Spec-Depot mehr Auswahl (Rotation/Diversifikation), ohne die Depot-Anzahl zu erhöhen (kein Klumpenrisiko durch mehr Depots).
- **`max_spec_depots` NICHT erhöht** (User: "nicht mehr Depots bei specs"). Die 49 bestehenden Depots bleiben, wählen aber aus 169 statt 49 Kandidaten.
- **Cron-Fenster**: Auswertungs-Crons auf 5-10 Min nach Börsenschluss (Audit 22:05, Monitor 22:17).

## [2.19.6] - 2026-08-07
### Changed (Risiko-Rampe Stufe 3: Penny-Penalty)
- **`engine.py` Z31-35**: Budget-Anpassung umgedreht (Hybrid b+c). Bisher: billigere Aktien kriegen MEHR Score (Penneys wie AMC $2.56 / WKHS $3.26 dominierten Top-10 bei $100-Cash-Depots → KI fand kein Signal → hielt). Neu: Aktien <$5 kriegen **Score-Abzug (-10)**, $5-30 Small-Caps **+8** (Diversifikation), >$30 **+3** (neutral). Penneys nicht ausgeschlossen (Pool bleibt voll), aber abgewertet.
- **Verifiziert**: Risk 70 Top-10 vorher 5 Penneys (<$5), nachher 10× $5-30 (CLOU $27, LGI $18, TNDM $22, EIDO $13, ACHR $5.5, PATH $15, CRSR $14, JKS $17, KSS $19, RELY $24). Bei $107 Cash + 37.5% Position = 2-3 kaufbare Positionen → echte Streuung.
- Kein Live-Geld — Shadow/Paper-Testsystem.

## [2.19.5] - 2026-08-07
### Changed (Risiko-Rampe Stufe 1+2)
- **Stufe 1 — Volumen-Filter geöffnet** (`ki_decisions.py` Z258-260): `vol_ratio <0.3x` → 70% Position (statt 50%); `<0.15x` → noch 40%; erst `<0.08x` = kompletter Verzicht (statt 0.15x). Ziel: mehr Käufe = mehr Lern-Signal.
- **Stufe 2 — Hebel-ETFs erlaubt** (`ki_decisions.py` Z261-263): 3x-Produkte (TQQQ/SQQQ/UVXY/VXX/VIXY/SOXS/SPXS/JDST/JNUG/FNGU/BOIL/UCO/SCO/NRGU/FAZ) dürfen gekauft werden, aber nur mit KLEINER Position (max 30% Cash) wegen Slippage/Vola. Kein generelles "halten" mehr.
- **Strategie:** Gestaffelte Risiko-Erhöhung ("wie Klaiber") — von sicher schrittweise öffnen, Ergebnis bewerten, bei Bedarf zurückdrehen (Backup + Git vorhanden).
- Kein Live-Geld — Shadow/Paper-Testsystem.

## [2.19.4] - 2026-08-07
### Changed (Strategie: Diversifikation)
- **`build_risk_profile.py` Z99-100**: `max_positions` 2-6 → **4-8** (Risk 0→8, Risk 95→4), `position_size` 0.30-0.60 → **0.15-0.40** (Risk 0→0.15, Risk 95→0.40). Ziel: mehrere kleine Positionen statt weniger teurer Klumpen.
- **`ki_decisions.py` Z252-260**: Prompt erweitert um STRATEGIE-HINWEISE — Volumen als Dämpfer (nicht als Hard-Stop, erst <0.15x illiquide), Diversifikation (max 1 Penny/Tier, Mix aus ≥2 Tiers), Bevorzugung von 3-5 kleinen Positionen. Gilt für ALLE Risk-Stufen.
- **`risk_profile.py`** neu generiert (1446 Zeilen).
- Kein Live-Trading während Testphase — nur Paper/Sim (wie bisher).

## [2.19.3] - 2026-08-07
### Fixed (Cash-Anzeige Risk-Depots)
- **`dashboard.html` Z616**: `dep.bargeld = dep.bargeld || 0` → `dep.bargeld = full.bargeld || 0`. Dashboard zeigte bei Risk-Depots (70-90) **CASH=$0.00** obwohl Depot $107–124 Cash hat. Root-Cause: bargeld wurde aus dem Overview-Objekt (`dep`) gelesen statt aus dem Detail-Response (`full`). Korrigiert auch `dep.wert`/`dep.start` auf `full.*`.
- Verifiziert: `/depot_json?risk=90` liefert `bargeld=123.96` → Dashboard zeigt jetzt `$123.96`.

### Echte Situation Risk 70–90 (KEIN Bug)
- Depots haben Cash ($107–124), KI läuft (ki_log.json: Entscheidungen heute 15:49 für MARA/LABU/UPRO/MRNA/JNUG/MSTR/VXX).
- KI empfiehlt **halten** (Marktlage: dünnes Volumen, Abwärtstrends in Kandidaten) → keine neuen Positionen.
- KI sieht im Prompt korrekt `bargeld=123.96` (batch_trader.laden_oder_erstellen liest bargeld aus JSON).
- Tracking-Note: spec-Depot-KI-Entscheidungen landen in ki_log.json unter `depot_typ="aktien"` (nicht `spec_XX`) → DB-Filter `spec_XX` findet 0. Kosmetisch, keine Kauf-Blockade.

## [2.19.2] - 2026-08-07
### Added (Trade→KI-Zuordnung — Infrastruktur)
- **`db._sync_trades`**: liest `decision_id` aus Depot-JSON-Trade (falls vorhanden, sonst NULL).
- **`db.match_trades_ki()`**: weicher Match Trade↔KI über Ticker + Zeitfenster (10min). Nur **eindeutige** Zuordnungen (1 KI im Fenster) werden gesetzt; sonst NULL (ehrlich, keine Erfindung). Direkter Key (`trade.decision_id == ki_decisions.decision_id`) hat Vorrang.
- **`db.sync()`**: ruft `match_trades_ki()` nach dem Sync auf.
- **`db.analyse_karten`**: `trades_mit_decision_id` + `trades_ohne_ki_zuordnung` (weicher Match) jetzt echt aus DB.

### Ehrlichkeits-Hinweis (wichtig)
- Bei **aktuellen/alten Daten** (vor v2.19.1) haben weder Trades noch ki_decisions eine `decision_id` → weicher Match findet zwar Ticker/Zeit-Treffer, aber KI-Seite `decision_id=NULL` →Trade bleibt NULL.
- Bei **neuen Läufen** (ab v2.19.1): `ki_decisions.decision_id` wird befüllt → weicher Match ordnet sie den Trades zu.
- **Offener Punkt:** `batch_trader.py`/`spec_trader.py` schreiben beim Trade-Export noch keine `decision_id` in Depot-JSON. Das ist ein größerer Umbau (decision_id durch Aktions-Pipeline tragen) → eigener Auftrag. Bis dahin: weicher Match als best-effort.

### Verifiziert
- `match_trades_ki()`: idempotent, 1 weicher Match bei aktuellen Daten (ki-Seite NULL → Trade NULL, ehrlich).
- `analyse_karten`: `trades_mit_decision_id=0/927` (korrekt für alte Daten).

## [2.19.1] - 2026-08-07
### Added (Audit-Felder — echte DB-Spalten)
- **DB-Schema-Migration** (`db._migrate_schema`, idempotent): `trades` + `ki_decisions` erhalten `decision_id`, `provider`, `regel_id`, `fallback` (TEXT, nullable). Bereits vorhandene Spalten werden übersprungen.
- **`ki_decisions.py`**: `entscheide_ticker` schreibt jetzt `provider` (welcher Free-Tier-Provider entschied) + `fallback` (True bei KI-Crash → sicheres `halten`, False bei echter KI-Entscheidung). Schon vorhanden: `decision_id` (immer erzeugt), `angewandte_regeln[].id` (→ `regel_id`).
- **`db._sync_ki`**: liest `decision_id` + `regel_id` aus `ki_log.json` beim Sync.
- **`db.analyse_karten`**: `entscheidungen_mit_decision_id`, `legacy_fallbacks`, `provider_fehler`, `provider_verteilung`, `entscheidungen_mit_regel` jetzt **echt aus DB** (nicht mehr `n/a`).
- **Analyse-Tab analyse2**: Filter Provider + Fallback (Echte KI / ⚠FB) + neue Spalten (Provider/decision_id/Regel-ID) + Karten mit Provider-Verteilung.
- **`report_pdf._datenvertrauen`**: `decision_id-Zuordnung` ehrlich aus DB (z.B. "vollständig (22% der Einträge)" oder "Legacy (alte ohne Feld)").

### Ehrlichkeits-Hinweis
- Alte 178 ki_decisions (vor v2.19.1) haben **kein** decision_id/provider (aus Zeit vor Feld-Einführung) → in DB NULL, nicht erfunden. Nur neue Entscheidungen (ab jetzt) befüllen die Felder.
- `trades.decision_id` (Trade→KI-Zuordnung) bleibt offen: Depot-JSONs haben kein decision_id → Match folgt in eigener Migration.

### Verifiziert
- DB-Migration idempotent (2x sync = keine Duplicate-Spalten).
- `/api/db_karten`: `entscheidungen_mit_decision_id=0/178` (ehrlich, alte Daten), `provider_fehler=178` (alle unknown, alt).
- `/api/db_query?mode=ki&provider=zen` Filter funktional.

## [2.19.0] - 2026-08-07
### Added (Analyse- & Datenvertrauen-Stabilisierung)
- **Phase B — Datenvertrauens-Score**: Tagesbericht zeigt `DATENLAGE: HOCH|MITTEL|NIEDRIG|NICHT VERIFIZIERT` + 9 Statusfelder (Portfolio-Snapshot, Trade-Daten, Einzel-Trade-P&L, Gebühren, Slippage, Drawdown, decision_id-Zuordnung, KI-Provider, Report-Erzeugung). Kein erfundenener %-Wert.
- **Phase C — Statusübersicht**: Tabelle Produktiv/Shadow/Konzept/Offen (US/Aktien/ETF/Spec=PRODUKTIV; DE/JP/Profile=KONZEPT; Paper/Live-Freigabe=OFFEN; WhatsApp=EINGESCHRÄNKT).
- **Phase D/F — 9-Seiten-PDF**: Seite 1 Tagesstatus+Datenvertrauen, S2 Kategorien/Verlauf, S3 Performance/KI-Lernen, S4 Statusübersicht+Root-Cause-Historie, S5-9 Detail (Tagesstatus/Performance/Risiko/Trades/Governance/System).
- **Phase E — Analyse-Tab analyse2 erweitert**: API `/api/db_karten` liefert Kennzahlen (Trades/KI/K-V-H-Verhältnis/Konfidenz-Schnitt). Dashboard zeigt Karten. decision_id/Provider/Legacy ehrlich als `n/a` (DB-Feld fehlt).
- **Phase G — KI-Provider-Stabilität**: Transparente Tabelle im PDF (5 Provider, Cooldown-Status, Konfiguration).

### Unverändert (bewusst)
- DB-Schema: keine `decision_id`/`provider`/`regel_id`/`fallback`-Felder → im Report als `n/a`/`Legacy` markiert (ehrlich, nicht erfunden).
- Keine neuen Märkte/Profile/Live-Automatisierung (außerhalb dieses Auftrags).

### Fixed
- `anLaden2` korrupter Text (`l sucrose...`) → `lädt...`.
- JS `node --check` valid (kein SyntaxError).

### Verifiziert
- PDF-Generierung: 9 Seiten, 264KB, Datenvertrauens-Sektion + Statusübersicht + Root-Cause-Tabelle gerendert.
- API `/api/db_karten`: trades=927, ki=178, K/V/H=140/102/138, Konfidenz=56.5%.

## [2.18.3] - 2026-08-06
### Changed
- **KI-Wellen (gestreckte Calls)**: KI-Taktung auf 30min zurück (statt 120), aber Calls gestreckt statt gebündelt. Scheduler triggert `ki_welle` alle 30min mit `--welle 0-3` (rotierend), jede Welle verarbeitet nur 13 der 49 Spec-Ticker. Ursache Rate-Limit (zen Free-Tier 429 nach ~20 Calls): 49 Calls auf einmal. Jetzt ~13/Welle → zen hält durch, andere Provider springen ein. Verifiziert: Welle 0/1 laufen sauber, nur zen rate-limited.

### Fixed
- **PDF falsche Gesamt-Zahlen (erneut)**: `lade_depots_flat()` ignorierte leere Aktien-Depots (0 Positionen) komplett → deren Startkapital (3×100$=300) fehlte in Aktien-Summe (1400 statt 2000) → Gesamt-PnL falsch (~+0,02% statt echter +0,92%). Fix: leere Depots als reines Startkapital in Bilanz aufgenommen. Version-Hardcode in PDF auf `version.json` (2.18.3) korrigiert. Verifiziert: Aktien +4,65%, Gesamt +0,92%.

## [2.18.2] - 2026-08-06
### Changed / Added
- **Scheduler intelligent getaktet**: Engine (Daten-Sammeln) alle 15min, KI-Trading (Entscheidungen) nur alle 60min (`MT_KI_INTERVAL=60`). Root-Cause: 26 volle KI-Läufe/Tag × ~90 Calls = 2340 Calls/Tag → zen Free-Tier Rate-Limit (429) voll → KI-Trading tot. Jetzt ~6 KI-Läufe/Tag = ~540 Calls (unter Limit).
- **Integritätsprüfung** (`pruefe_pipeline_ergebnis`): warnt bei Cooldown-Blockade, 0-Kursen, nur-"halten"-Fallback oder Timeouts im Log.
- **NEU: SQLite-Analyse-DB** (`micro_trader.db` + `db.py`): spiegelt alle JSON-Depots nach jedem Pipeline-Lauf. Schnelles Auslesen + Quer-Analysen (`trades`, `ki_decisions`, `depot_snapshot`, `markt_daten`). Verifiziert: 925 Trades in DB.

## [2.18.1] - 2026-08-06
### Fixed
- **KRITISCH: KI-Trading war lahmgelegt** — Root-Cause 1: alle 5 Provider im Circuit-Breaker-Cooldown (`ki_cooldown.json`) wegen hängengebliebenem State vom Hermes-Modell-Wechsel. Root-Cause 2: Reasoning-Modelle (nous-hy3/step) lieferten bei kleinem `max_tokens` KEIN `content` → `_ki_call` wertete das als Fehler → Cooldown "timeout". Fix: `CALL_TIMEOUT` 120→180s, Cooldown-Datei >6h auto-verworfen, `_ki_call` akzeptiert `reasoning_content` + leere Antworten lösen KEINEN Cooldown, `ki_cooldown.json` geleert. hy3 bleibt in Rotation (braucht `max_tokens>=1024` im Trader-Prompt, gegeben).
- **Spec-Trader final gefixt**: Workers 3→8 + Pipeline-Timeout 300→600s. Lief vorher bei 300s-Limit ins Timeout, brach mitten in KI-Calls ab → Orders blieben aus. Jetzt: 93-106s sauber durch (OK).
- **Verifiziert**: KI entscheidet echte kaufen/verkaufen, `ki_log.json` vollständig, kein Cooldown mehr.

## [2.18.0] - 2026-08-06
### Added
- **Phase 13: Live-Freigabe** (§29.F): Profile us_shadow/de_shadow/jp_shadow auf `modus=live` aktiviert via `freigabe.py --activate --confirm` (User-Freigabe erteilt 06.08.2026 20:31). Pre-Flight-Check bestanden. 29 Regeln (27 Meta-Caps + 2 Anti-Hold) bleiben bewusst Shadow. Dashboard-Profil-Karten zeigen `status=live`.
- **Tagesauswertungs-PDF (6 Pflichtsektionen)**: `report_pdf.py` erweitert — Tagesstatus, Performance/P&L, Risiko/Exposure, Trades/Ausführung, KI/Regel/Governance, Systemstatus/Anomalien/Audit. Report-ID (`RPT-YYYYMMDD-NNN`) + Audit-Fußzeile (KI GENERIERT, Seitenzahl) auf jeder Seite. Dateiname: `daily_report_YYYY-MM-DD_v<VERSION>_<RPT-ID>.pdf`.
- **Neue 9-Seiten-Struktur**: S1 Portfolio/Tag, S2 Kategorien, S3 Performance/KI-Lernen (endet nach Marktregime), S4 Projektstatus (getrennt!), S5-9 Tagesauswertung-Detail.
- **Live-Kurse in PDF**: `lade_depots_flat()` nutzt `marktdaten.hole_kurs()` (4-Tier-Fallback) statt nur `avg_price`.
- **Version zentral aus `version.json`** (kein Hardcode mehr).

### Fixed
- **KRITISCH — Falsche PDF-Werte** (User gemeldet): `lade_depots_flat()` rechnete ETF-/Aktien-Positionen OHNE Depot-Bargeld (`wert = shares*kurs` statt `bargeld_anteil + shares*kurs`) → künstliches Minus (-10,41% statt +0,97%). Fix: Cash-Anteil pro Position, wie das Dashboard.
- **Warnstatus-Falsch-Positiv**: Positive "Risk 50-95: +Rendite"-Meldungen zählten als Warnung → Seite 5 zeigte WARNUNG trotz STABIL. Fix: nur echte Warnungen (❌/gesperrt/Drawdown/Fehler).
- **Verwaiste Überschrift Seite 3**: "3.3 Marktregime" stand allein am Seitenende, Text auf S4. Fix: `KeepTogether`.
- **KI-JSON-Parse-Crash** (Bug 2): `json.loads` auf ungültiges JSON crashte unhandled → K:0-Trades. Fix: `try/except` + 1× Retry mit strikterem Prompt + Fallback `halten K:50`.
- **Anti-Hold-Ping-Pong** (Bug 1): Anti-Hold-Regeln (`VERBOT/MEIDE`, wirkung=verbot) erzwangen sofortigen Verkauf nach Kauf. Fix: `VORSICHT/ABWÄGEN`, wirkung=gewichtung, `durchgesetzt=False` — KI entscheidet final, Regeln als Kontext.
- **KI-Rate-Limit**: `entscheide_spec_batch` max_workers 12→3 (weniger gleichzeitige Calls gegen Nous-free-Quota).
- **`undefined` in Trade-Historie**: Depot-Trades hatten `aktion`, nicht `typ` → Dashboard zeigte `undefined`. Fix: 336 Trades migriert (`aktion`→`typ`) + Frontend-Fallback `t.typ || t.aktion || "?"`.
- **Leere ETF/Spec-Depots**: 19 Spec (bargeld=0) + 17 ETF (falsch gesperrt) repariert via `reparatur_depots.py` (Reset auf 100$, Unlock bei DD<30%).

### Verified
- PDF: Gesamtwert ~8.785$ / +0,97% (konsistent mit Dashboard +0,96%), 9 Seiten, keine Überläufe, Version v2.18.0 überall.
- ETF-Depots: 0 gesperrt, 20/21 mit Positionen. Spec: 0 leer.
- KI liefert echte Entscheidungen (K:55-60) via Hermes-Nous-Verbindung.

## [2.17.0] - 2026-08-06
### Added
- **Banner/Logo in Dashboard**: `assets/banner.png` + `logo.png` + `logo.ico`, Banner-Header in `dashboard.html` (height:90px, object-fit:contain), ASCII-Banner + Titel in `dashboard.bat`, README-Banner.
- **Dashboard Asset-Route**: `static_folder=assets` + explizite `/assets/<path>` Route via `send_file`.
- **PDF v5**: Banner/Logo, Cyan/Violett/Mint-Farbwelt, Kategorie-Graphen.

### Fixed
- **/assets/banner.png 404**: Alte 5300-Instanz (PID 22740) lief mit altem Code im RAM → gezielter `taskkill` + frischer Start.
- **Banner falsch platziert**: `object-fit:cover`+`max-height:96px` clippte Text → `object-fit:contain`+`height:90px`+`background:#0b1220`.

### Verified
- HTTP 200 für /, /assets/banner.png, /assets/logo.png, /assets/logo.ico auf 5300.

## [2.16.12] - 2026-08-05
### Fixed
- **7 leere Spec-Depots gelöscht**: LABU, MARA, MNMD, QQQ, SOXS, TQQQ, VXX (0 Trades, 0 Pos, Cash übrig). KI hielt bewusst (Hebele/Volatility per Anti-Regel, MNMD delisted) → blockierten Spec-Übersicht. Nur 42 aktive Spec-Depots übrig (alle mit Trades/Positionen). Backup: `.backup/spec_empty-*`.

### Verified
- Spec-Depots: 42 (alle aktiv, keine leeren mehr)

## [2.16.11] - 2026-08-05
### Fixed
- **38 tote Spec-Depot-Dateien gelöscht**: Nicht in WATCHLIST, `start=0` (wertlos). Verzerrten Spec-Tab-Ansicht. Nur 49 gültige Spec-Depots übrig (alle in WATCHLIST). Backup in `.backup/spec_depots-dead-*`.

### Verified
- Spec-Depots: 49 (alle in WATCHLIST, keine toten Placeholder mehr)
- Dashboard `data().spec_depots` filtert korrekt (Platzhalter ohne Startkapital)

## [2.16.10] - 2026-08-05
### Added
- **spec_trader.fetch_analyse() Super-Mix-Fallback** (v2.16.10): Wenn yfinance im Batch einen Ticker auslässt (Flakiness) → Single-Download + `marktdaten.hole_kurs()` (4-Tier). Rettet z.B. MNMD (delisted, $0.69 via marktdaten).
- **`_MAX_SPEC`-Limit-Fix**: `tickers[:_MAX_SPEC]` schnitt QQQ ab (49 Ticker > Limit 48). Jetzt `max(_MAX_SPEC, len(tickers))` → kein Ticker mehr verloren.
- **RSI-Berechnung robuster**: `try/except` + NaN→50.0 Fallback (verhinderte QQQ-Crash im Loop).

### Fixed
- **ETF-Depots systematisch tot** (P55-Altlast): 20 ETF-Depots hatten `bargeld 8–72$`, `shares=0` (0$-Verkauf zerstörte sie). Reset auf `bargeld=100, start_wert=100, shares=0` + ungültige 0$-Trades entfernt. `etf_trader` füllt sie jetzt wieder (VGK/VEA/VWO/SCHD/ARKK/XLF <100$ kaufbar).
- **7 leere Spec-Depots**: JOBY/LABU/MARA/QQQ/RKLB/SOXS/TQQQ/VXX bekamen keine KI-Entscheidung (yfinance-Batch-Flakiness + QQQ-Limit-Bug). Jetzt alle 49 Ticker in `fetch_analyse()` → KI entscheidet (Hebele/Volatility bewusst "halten" via Anti-Regeln).

### Verified
- `fetch_analyse()`: 49 Ticker (alle 8 leeren Spec + QQQ da)
- ETF-Reset: 20 Depots auf 100$ (keine Toten mehr)
- Spec-Trader: 49 KI-Entscheidungen/Run (vorher ~40 durch Abstürze)
### Fixed
- **Spekulations-Depots kauften nie** (39 leere Spec-Depots mit Cash): Root-Cause in `ki_decisions.entscheide_ticker()` — bei `shares=0` stand nur `POSITION: Keine Position`, kein Kauf-Hinweis → KI hielt konservativ. Fix: `[LEER: BITTE KAUFEN — {bargeld}$ Cash verfügbar, Ticker ist in Watchlist!]` bei `bargeld >= 20$`.
  - **Ergebnis**: 18 Spec-Depots mit neuen Käufen (ASTS 1.47st @$68, BB 12st @$8.90, COIN 0.66st @$152, CRSP, GME, IBIT, MSTR, RIVN, RGTI etc.).
  - **Bewusst erhalten**: Volatility-/Hebele-ETFs (UVXY, SQQQ, SOXS, TNA, UPRO, VIXY) weiterhin per gelernter Anti-Regel geblockt (nicht blind kaufen).

### Verified
- Unit-Test: ASTS (leer, $100, Kurs $68.27) → KI sagt "kaufen" (K:60)
- Spec-Trader Run: 9 non-Hold, 18 Kauf-Trades in Depot-Dateien

## [2.16.8] - 2026-08-05
### Added
- **Super-Mix Datenquellen** (`marktdaten.py` neu): Live-Kurs via 4-Tier-Fallback
  yfinance → Finnhub `/quote` (60/min) → TwelveData `/quote` (800/day) → AlphaVantage `GLOBAL_QUOTE` (25/day).
  Löst das yfinance-Rate-Limit-Problem (Kurs = 0 → P55-Crash bei Verkauf).
- **Scan-Resilienz**: `scan_markt()` yfinance-Primary, bei Exception/leerem DataFrame TwelveData `time_series` als Fallback (begrenzt auf 50 Ticker/Run, da 800 credits/day).
- **`.env`** mit `FINNHUB_KEY`, `TWELVEDATA_KEY`, `ALPHAVANTAGE_KEY` (Keys nicht im Repo — `.gitignore` ergänzt).

### Fixed
- **Leere Depots kauften nie** (Risk 65/70/80/85/90): Root-Cause war Feldname-Bug — `bewerte()` liefert `preis`, aber `batch_trader.py` las `aktuell` → alle Kandidaten Preis 0 → fielen durch Budget-Filter → KI sah "keine Kandidaten" → hielt. Fix: `alle_kandidaten` liest `t.get("preis", 0)`.
  - **Ergebnis**: Risk 65/80/85/90 kaufen jetzt LCID/AMC/DOMO/SOXS (alles im Budget).

### Verified
- Unit-Test: yfinance deaktiviert → Finnhub liefert AAPL 309.80, LCID 6.65 (Fallback greift)
- Live-Test: AAPL 309.76, LCID 6.63, AMC 2.71 (yfinance-Primary)
- KI-Batches: 4×5 Depots, zen-nemotron stabil, leere Depots mit Kauf-Aktionen

## [2.16.7] - 2026-08-05
### Fixed
- **ETF-Depots kauften nie**: `etf_bewerte()` gab nur Top 3 Kandidaten — wenn die alle teurer als das $100-Budget waren (z.B. Risk 25: DIA $544/SPY $775/VTI $382), ergab `menge = int(bargeld/preis) = 0` → `continue` → kein Kauf. etf_025 blieb ewig leer.
  - Fix 1: Preis-Malus in `etf_bewerte()` (preis > budget → Score -40) → bezahlbare ETFs ranken höher.
  - Fix 2: `return erlaubt[:8]` statt `[:3]` → Kauf-Loop erreicht bezahlbare Alternativen.
  - **Ergebnis**: etf_025 kaufte VGK 1st @$92.07 (Rest $7.93) — alle 20 ETF-Depots haben jetzt Positionen.
- **Back-Button in Depot-Detailseiten**: `showTab('overview')` war hartcodiert → nach "← Zurück" landete man immer auf der Übersicht, egal aus welchem Tab. Fix: `showTab(typ === 'main' ? 'overview' : typ)` → zurück in Aktien/ETF/Spec-Tab.
- **ETF-Karten-Klick ging nicht**: `JSON.stringify(e).replace(/\\\"/g,...)` (4 Backslashes im Source) matchte fast nie → rohe `"` im onclick → Attribut brach. Fix: 2 Backslashes wie in `renderCard` → Karten öffnen Detailseite.

### Verified
- etf_025: VGK-Position, 1 Trade, HTTP 200
- Back-Button: ETF-Karte → Detail → Zurück → Tab = 📦 ETF (nicht mehr Übersicht)
- ETF-Karten: `showDepot({&quot;cash&quot;:8.32,...})` korrekt escaped

## [2.16.6] - 2026-08-05
### Changed
- **Summary-Chips vereinheitlicht** (Spec-Tab): Die doppelte summary-row unten im spec-overview-Pane (Gesamtwert/Ø-Rendite/Aktive Pos./Beobachtet) entfernt — war ein Relikt aus v2.11.1-Umbau. Alle 6 Stats jetzt in EINER Row oben: Gesamtwert, Rendite, Depots, Trades, Bester, Schlechtester. 24h-Widgets (Top-Gewinner/Verlierer) bleiben unten.
- **Aktien- & ETF-Tab**: Bester/Schlechtester-Chips ergänzt (fehlten dort) — Aktien/ETF zeigen "Risk X +Y.Z%" bzw. "Risk X -Y.Z%", Spec zeigt Ticker.
### Verified
- Spec: Oben 6 Chips, Unten-Duplikat weg (grep Spec-Gesamtwert = 1 statt 2)
- Aktien: $2116 · +5.81% · 20 · 14 · 189 · Risk 90 +20.3% · Risk 65 -2.6%
- ETF: $2014 · +0.69% · 20 · Risk 95 +10.8% · Risk 90 -7.8%

## [2.16.5] - 2026-08-05
### Fixed (kritisch)
- **Depot-Crash durch Verkauf zum Preis 0**: yfinance-Rate-Limit (YFRateLimitError) liess `hole_kurs_fuer()` 0 liefern → KI-Verkauf mit `preis=0` → `erlös=0`, Position geloescht ohne Bargeld-Gutschrift → Depot-Werte stuerzten um bis zu -92% in Minuten. Betroffen: 14 Depots (DOMO, ASTC, AA, ALKS, CVM, CIFR).
  - `batch_trader.py`: Verkauf wird uebersprungen wenn Kurs <= 0 (Position bleibt).
  - `engine.py`: gleicher Schutz in `ausführen()`.
- **Daten-Restore**: 14 zerstörte Depots aus Dev-Clone wiederhergestellt (Positionen + Entfernen der preis-0-Trades). Backup: `.backup/depot-restore-20260805_155305/`.
- Scheduler neu gestartet mit Fix.

### Lesson
- Nie einen Trade mit Preis <= 0 ausfuehren — lieber Position behalten als zu 0 verkaufen.
- Rate-Limit von yfinance ist ein bekanntes Risiko: `hole_kurs_fuer()` muss bei Fehler `None` (nicht 0) liefern und Aufrufer muessen das pruefen.

## [2.16.4] - 2026-08-05
### Fixed
- **Profilwechsel jetzt sofort sichtbar**: `data()` cached das Dashboard-Ergebnis 60s — `/api/profile?set=` hat den Cache nicht invalidiert, daher zeigte das Dropdown nach Wechsel bis zu 60s das alte Profil ("wechselt aber nicht"). Fix: Cache-Invalidierung (`data._cache = None`) nach erfolgreichem Wechsel.
- **Import-Fix**: `_profil_info()` importierte `lade_aktives_profil` — Name jetzt konsistent mit `profile_schema.py` (Funktion existierte, nur Referenz falsch). Root-Cause via `traceback.print_exc()` im except sichtbar gemacht.

# Micro-Trader DEV — CHANGELOG

> Entwicklungs-Zweig (Clone von Produktiv). Port 5400. Produktiv (5300) bleibt unberührt.
> Reihenfolge gemäß Zielarchitektur §28 (von innen nach außen).

## v2.16.3 "Profil-Modell" (2026-08-05 14:00) — DEV
**👤 Phase 2 (Identität & Struktur): Profil-Schema + US_Test_Shadow**

- **NEU `profile_schema.py`**: `Profil`-Klasse + JSON-Schema-Validierung + Default `US_Test_Shadow`
  (US-Markt, Shadow-Modus, USD, Aktien/ETF/Spec).
- **NEU Route `/api/profile`** (dashboard.py) + `profil` in `data()`.
- **NEU Profil-Karte** im Übersicht-Tab (Name/Modus/Base-Währung/Märkte/Depotarten/Version).
- Reine Metadaten-Hülle — greift noch **nicht** steuernd in Trading ein (folgt Phase 3+).
- **Verifiziert:** `/api/profile` liefert Profil, `/data` profil-Block, HTTP 200, Produktiv (5300) unberührt.

### Dateien geändert (nur Dev-Clone)
- `profile_schema.py` — NEU
- `dashboard.py` — `/api/profile` + `_profil_info()` + `profil` in `data()`
- `dashboard.html` — Profil-Karte im Übersicht-Tab
- `profile.json` — auto-erstellt (US_Test_Shadow)
- `version.json` — v2.16.3

### Nächster Schritt (Phase 2 weiter)
- [ ] Profil-Wechsel (mehrere Profile anlegen, aktives Profil umschalten)
- [ ] Profil in Scheduler/Trader einbinden (Phase 3: Marktmodell nutzt profil.märkte)

### Profil-Wechsler (Phase 2 Erweiterung, 2026-08-05 14:10)
- **Mehrfach-Profile:** `profile_US_Test_Shadow.json`, `profile_DE_Test_Shadow.json`,
  `profile_JP_Test_Shadow.json` (DE/JP als Platzhalter für Phase 3).
- **`active_profile.json`** steuert das aktive Profil (via `setze_aktives_profil()`).
- **Route `/api/profile?set=<name>`** wechselt Profil. **`/api/profile`** listet verfügbare.
- **Wechsel-UI** im Dashboard (Dropdown in Profil-Karte).
- **Verifiziert:** Wechsel US→DE→US funktioniert, alle 3 Profile gelistet, `aktiv` korrekt.
- **Hinweis:** Flask-Modul-Cache! Nach Änderung an `profile_schema.py` Dashboard neu starten,
  sonst alter Code im Cache (hat Debugging verzögert).

### Nächster Schritt (Phase 2 → Phase 3)
Phase 2 abgeschlossen (Profil-Modell + Wechsler). Nächstes: **Phase 3 (Marktmodell)** nutzt
`profil.märkte` steuernd (Scheduler/Trader filtern nach aktivem Profil). Dann zurück in Produktiv.


### Profil-Wechsel Bugfix (2026-08-05 14:45)
- **Symptom:** Dropdown-Wechsel bestätigt, aber Profil blieb gleich (US_Test_Shadow).
- **Root-Cause:** `_profil_info()` in `dashboard.py` nutzte `lade_profil()` (Default),
  ignorierte `active_profile.json`. `data()` lieferte immer das Default-Profil →
  Dropdown zeigte falsche `selected`-Option.
- **Fix:** `lade_profil()` → `lade_aktives_profil()` in `_profil_info()`. Jetzt liest
  `data().profil` das aktive Profil → Wechsel sichtbar.
- **Verifiziert (Browser + curl):** Wechsel US↔DE↔JP funktioniert, Dropdown springt mit.
