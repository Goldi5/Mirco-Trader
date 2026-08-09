# Micro-Trader

**KI-unterstützte Paper-Trading-Plattform mit Risikomanagement, Strategiebewertung, Multi-Tenant-Architektur und kontrollierter Order-Ausführung.**

Micro-Trader ist eine modulare Trading-Plattform zur Kombination von Marktdatenanalyse, deterministischen Strategie- und Risikoregeln sowie KI-gestützter Entscheidungsfindung in einer kontrollierten **Paper-Trading-Umgebung**.

Das zentrale Architekturprinzip lautet:

> **Die KI darf analysieren und Vorschläge erzeugen – deterministische Risiko- und Governance-Schichten entscheiden, was tatsächlich erlaubt ist.**

---

# ⚠️ Aktueller Status

> **Paper Trading — aktiv**
> **Live Trading — deaktiviert**

Micro-Trader ist derzeit als **Paper-Trading-System** ausgelegt und wird in diesem Modus betrieben.

Eine Ausführung von Orders mit echtem Kapital ist aktuell nicht vorgesehen.

## Systemstatus

| Komponente      | Status                 | Bereich    | Anmerkung                              |
| --------------- | ---------------------- | ---------- | -------------------------------------- |
| Paper Trading   | 🟢 Aktiv               | Paper      | Hauptausführungsumgebung               |
| KI-Analyse      | 🟢 Implementiert       | Paper      | Provider-Rotation/Fallback vorhanden   |
| Risk Engine     | 🟡 Aktiv / Validierung | Paper      | Mehrere Risikoprofile                  |
| Strategy Engine | 🟢 Implementiert       | Paper      | Zentralisierte Strategielogik          |
| Order Intent    | 🟢 Implementiert       | Paper      | KI führt Orders nicht direkt aus       |
| Multi-Tenant    | 🟢 Implementiert       | Anwendung  | Produktionsumfang derzeit begrenzt     |
| Security Layer  | 🟡 Aktiv / Hardening   | Anwendung  | Weitere Härtung erforderlich           |
| KI-Learning     | 🟡 Experimentell       | Paper      | Kontrollierte Validierung erforderlich |
| Live Trading    | 🔴 Deaktiviert         | Produktion | Derzeit nicht freigegeben              |

## Bekanntes kritisches Problem

**Die Kandidatenauswahl für Risk 70 benötigt weitere Korrektur und Validierung.**

Das dokumentierte Problem betrifft das Zusammenspiel zwischen verfügbarem Cash-Budget, Positionsgröße und dem Filter für bezahlbare Kandidaten.

Dadurch können grundsätzlich geeignete Kandidaten bereits vor dem Scoring bzw. der KI-Analyse herausgefiltert werden.

Dieses Problem wird hier bewusst sichtbar gemacht und nicht hinter einer allgemeinen Statusbeschreibung versteckt.

Die vollständige Root-Cause-Analyse, Reproduktion und technischen Details befinden sich in der vollständigen Handoff-Dokumentation.

---

# Was ist Micro-Trader?

Micro-Trader ist eine experimentelle Trading-Plattform mit Fokus auf:

* Marktüberwachung
* Kandidatenauswahl
* deterministische Bewertung
* konfigurierbare Risikoprofile
* KI-gestützte Analyse
* kontrollierte Order Intents
* Paper-Ausführung
* Portfolio-Tracking
* Analyse von Trade-Ergebnissen
* Lernen aus historischen Entscheidungen
* Multi-Tenant-Isolation
* Nachvollziehbarkeit und Governance

Die Plattform verfolgt bewusst den Ansatz, dass **die KI nicht die letzte Sicherheitsinstanz darstellt**.

Der geplante Entscheidungsweg ist:

```text
Marktdaten
    ↓
Kandidatenscanner
    ↓
Strategie / Scoring
    ↓
Risikoprofil
    ↓
KI-Analyse
    ↓
Order Intent
    ↓
Validierung
    ↓
Risk Enforcement
    ↓
Governance / Freigabe
    ↓
Paper Broker
    ↓
Datenbank
    ↓
Learning / Analytics
```

---

# Grundprinzipien

## 1. KI ist Analyst, nicht uneingeschränkter Ausführer

Die KI kann Marktdaten bewerten und eine Handelsentscheidung vorschlagen.

Sie darf jedoch nicht:

* Positionslimits umgehen
* Risikolimits umgehen
* Strategieregeln umgehen
* Freigaben umgehen
* Execution Controls umgehen
* Tenant-Grenzen überschreiten
* die Paper-/Live-Trennung umgehen

Das gewünschte Modell lautet:

```text
KI
 ↓
Vorschlag

Risk Engine
 ↓
Erlaubt / Abgelehnt

Execution Layer
 ↓
Paper Order
```

---

## 2. Paper First

Micro-Trader ist darauf ausgelegt, Strategien und Entscheidungslogik zunächst ohne echtes Kapital zu entwickeln und zu validieren.

Die aktuelle Execution-Architektur verwendet einen Paper-Broker.

Live Execution ist bewusst deaktiviert.

---

## 3. Deterministische Kontrolle um probabilistische KI

KI-Entscheidungen können probabilistisch und kontextabhängig sein.

Risiko- und Ausführungsregeln sollten deshalb soweit möglich deterministisch bleiben.

Beispiele:

* maximale Positionsgröße
* maximale Anzahl von Positionen
* Mindestscore
* Risikolevel
* Budget-/Bezahlbarkeitsprüfung
* Freigabeanforderungen
* Tenant-Isolation

---

# Architektur

```text
                    ┌──────────────────┐
                    │    Marktdaten    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Kandidatenscanner│
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Strategie/Score  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │   Risk Engine    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │    KI-Analyse    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │   Order Intent   │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Validierung/Gates│
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │    Paper Broker  │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │    Datenbank     │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Learning/Statistik│
                    └──────────────────┘
```

---

# Trading-Pipeline

Die zentrale Trading-Pipeline besteht aus mehreren aufeinanderfolgenden Stufen.

## 1. Marktdaten

Marktdaten werden über konfigurierte Provider bezogen.

Die dokumentierte Provider-/Fallback-Architektur umfasst unter anderem:

* Yahoo Finance
* Finnhub
* Twelve Data
* Alpha Vantage

Bei der Interpretation der Ergebnisse müssen insbesondere Verfügbarkeit, Rate Limits und Datenaktualität berücksichtigt werden.

---

## 2. Kandidatenauswahl

Der Scanner untersucht das konfigurierte Universum und wendet erste Filter an.

Kandidaten können anschließend anhand verschiedener Kriterien bewertet werden:

* Preis
* Volumen
* Volatilität
* technische Indikatoren
* Marktregime
* strategische Faktoren
* Risikolevel
* Budget-/Bezahlbarkeitsregeln

---

## 3. Strategie und Scoring

Die Strategie-Schicht überführt Markteigenschaften in deterministische Scores und Anpassungen.

Beispiele:

* Preisbewertung
* Small-Cap-Anpassungen
* Volumenanpassungen
* Behandlung gehebelter ETFs
* Diversifikationsregeln
* Tier-basierte Logik

Die Strategie soll zentralisiert bleiben und nicht an mehreren Stellen unabhängig voneinander implementiert werden.

---

## 4. Risikoprofile

Micro-Trader unterstützt mehrere Risikoprofile.

Das Risikolevel beeinflusst unter anderem:

* Positionsgröße
* maximale Anzahl von Positionen
* Mindestscore
* Stop Loss
* Take Profit
* erlaubte Instrumente/Tiers
* Portfolio-Exposure
* Budgetgrenzen

Das Risikoprofil ist damit ein tatsächlicher Bestandteil der Ausführungslogik und nicht lediglich eine Information für die Benutzeroberfläche.

---

## 5. KI-Entscheidung

Die KI erhält einen strukturierten Kontext mit relevanten Informationen, beispielsweise:

* Kandidatendaten
* Marktdaten
* Strategiedaten
* Risikokontext
* Nachrichten bzw. Kontextinformationen
* gelernte Regeln

Anschließend erzeugt die KI eine strukturierte Entscheidung.

Der vollständige aktuelle KI-Prompt und die detaillierte Entscheidungsarchitektur befinden sich bewusst in der technischen Handoff-Dokumentation und werden nicht vollständig in dieser README dupliziert.

---

# Order Governance

Ein zentrales Architekturkonzept ist der **Order Intent**.

Der vorgesehene Ablauf:

```text
KI-Entscheidung
      ↓
Order Intent erzeugen
      ↓
Order Intent validieren
      ↓
Risk Enforcement
      ↓
Rule Enforcement
      ↓
Freigabe / Governance
      ↓
Paper Broker
```

Damit wird bewusst zwischen

> **„Was möchte die KI tun?“**

und

> **„Was darf das System tatsächlich ausführen?“**

unterschieden.

Diese Trennung ist wesentlich für Sicherheit, Kontrolle und Nachvollziehbarkeit.

---

# Risikomanagement

Das Risikomanagement bildet eine eigenständige Schicht um Strategie und KI.

Unterstützte Kontrollen umfassen unter anderem:

* Positionsgrößen
* Portfolio-Limits
* maximale Anzahl von Positionen
* Score-Schwellenwerte
* Stop Loss
* Take Profit
* Budget-/Bezahlbarkeitsprüfung
* Instrumentenbeschränkungen
* Freigabeanforderungen

Die vollständige Risikomatrix und sämtliche Formeln befinden sich in der technischen Handoff-Dokumentation.

---

# KI-Learning

Micro-Trader enthält eine experimentelle Learning-Schicht, die Informationen aus vergangenen Trading-Ergebnissen ableiten soll.

Das konzeptionelle Modell:

```text
Trade
  ↓
Ergebnis
  ↓
Beobachtung
  ↓
Regelkandidat
  ↓
Validierung
  ↓
Aktive Regel
```

Dieser Bereich befindet sich bewusst in einer experimentellen Phase.

Eine gelernte Regel darf nicht allein deshalb zu einer aktiven Trading-Regel werden, weil sie in einer kleinen Anzahl vergangener Trades erfolgreich war.

Zu berücksichtigende Risiken sind unter anderem:

* kleine Stichproben
* Overfitting
* Feedback Loops
* Änderungen des Marktregimes
* selbstverstärkende Regeln

Die Governance des KI-Learnings bleibt daher ein aktives Entwicklungsgebiet.

---

# Multi-Tenant-Architektur

Micro-Trader besitzt eine Tenant-fähige Anwendungsarchitektur.

Der Tenant-Kontext soll sich durch die Anwendung ziehen:

```text
Request
  ↓
Authentifizierung
  ↓
Tenant Context
  ↓
Autorisierung
  ↓
Business Logic
  ↓
Datenbankzugriff
```

Das System ist darauf ausgelegt, dass ein Tenant nicht auf die Daten eines anderen Tenants zugreifen kann.

Wichtig ist jedoch die Unterscheidung zwischen **implementiert** und **vollständig produktionsvalidiert**.

Beispielsweise kann ein System:

```text
MULTI-TENANT — VERIFIED

Status:
VERIFIED

Evidence:
test_server_security.py
Test-Tenant T2

Last Verified:
2026-08-09

Code:
Tenant-Isolation implementiert.

Tests:
Cross-Tenant-Access-Tests erfolgreich.

Production:
Aktuell 1 Tenant.

Limitation:
Ein zweiter unabhängiger Production-Tenant wurde noch nicht
unter produktionsähnlicher Last validiert.

Confidence:
HIGH
```

Damit bedeutet „VERIFIED“ nicht automatisch „vollständig Production-ready“.

---

# Security

Security wird als Architekturkomponente und nicht als einzelnes Feature betrachtet.

Das System enthält bzw. ist um folgende Sicherheitsmechanismen aufgebaut:

* Authentifizierung
* rollenbasierte Autorisierung
* Tenant-Isolation
* Rate Limiting
* Audit Logging
* MFA-Unterstützung
* sichere Secret-Verwaltung
* Freigabeprozesse
* Four-Eyes-Prinzip
* lokale Service-Bindings
* Reverse Proxy
* explizite Live-Trading-Sperren

Die Security-Härtung bleibt ein fortlaufender Entwicklungsbereich.

Die vollständige technische Bewertung, bekannte Lücken und Implementierungsdetails befinden sich in der Handoff-Dokumentation.

---

# Technologiestack

| Bereich           | Technologie                                 |
| ----------------- | ------------------------------------------- |
| Backend           | Python / Flask                              |
| Datenbank         | SQLite                                      |
| Trading-Modus     | Paper Trading                               |
| KI                | Konfigurierbare KI-Provider                 |
| Marktdaten        | Mehrere externe Provider                    |
| Authentifizierung | Application Authentication Layer            |
| Security          | Rollen-/Tenant-/Rate-Limit-Kontrollen       |
| Scheduling        | Cron / Scheduler                            |
| Deployment        | Lokaler Service + Reverse-Proxy-Architektur |

Exakte Versionen und umgebungsspezifische Konfiguration gehören in die technische Dokumentation.

---

# Projektstruktur

Das Repository ist nach Verantwortlichkeiten getrennt und nicht als monolithische Trading-Logik aufgebaut.

Vereinfachte Darstellung:

```text
project/
├── app/
│   ├── routes/
│   ├── trading/
│   ├── strategy/
│   ├── risk/
│   ├── ai/
│   ├── database/
│   ├── security/
│   └── ...
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── trading/
│   └── ...
│
├── backups/
├── docs/
├── config/
└── ...
```

Die tatsächliche aktuelle Repository-Struktur ist gegenüber dieser konzeptionellen Übersicht immer maßgeblich.

---

# Installation

> **Nur für Entwicklungs- und Forschungszwecke.**

Eine typische lokale Einrichtung:

```bash
git clone <repository>
cd micro-trader

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Anschließend müssen die erforderlichen Umgebungsvariablen und Secrets entsprechend der Projektkonfiguration eingerichtet werden.

**Keine API-Keys, Passwörter oder andere Secrets in das Repository einchecken.**

---

# Konfiguration

Die Konfiguration kann unter anderem enthalten:

* KI-Provider-Credentials
* Marktdaten-API-Credentials
* Datenbankkonfiguration
* Tenant-Konfiguration
* Authentifizierung
* Scheduler
* Strategieparameter
* Risikoparameter

Secrets müssen über den vorgesehenen Secret-/Konfigurationsmechanismus bereitgestellt werden.

Produktive Zugangsdaten dürfen niemals direkt im Quellcode gespeichert werden.

---

# Anwendung starten

Der genaue Startvorgang hängt von der jeweiligen Umgebung ab.

Für die lokale Entwicklung wird die konfigurierte Flask-/Application-Entry-Point verwendet.

Die produktionsähnliche Architektur sollte die dokumentierte Reverse-Proxy-/Netzwerkkonfiguration verwenden und den Flask-Service nicht ungeschützt direkt ins öffentliche Internet stellen.

---

# Tests

Die Tests sind in mehrere Bereiche aufgeteilt:

```text
Unit
Integration
Trading
Risk
Security
Multi-Tenant
Database
AI
Regression
```

Wichtig ist nicht nur die Code Coverage, sondern das korrekte Verhalten des Systems.

Beispiele:

* Risikolevel erzeugen das erwartete Kandidatenverhalten.
* Nicht autorisierte Tenant-Zugriffe werden abgewiesen.
* Orders können die Risk Engine nicht umgehen.
* Orders können erforderliche Freigaben nicht umgehen.
* Live Execution bleibt deaktiviert.
* Secrets werden nicht offengelegt.
* Paper Execution verhält sich deterministisch.

Die aktuelle Testanzahl sollte nicht dauerhaft in der README festgeschrieben werden. Sie sollte aus dem jeweils aktuellen Testlauf bzw. CI-Ergebnis stammen.

---

# Bekannte Einschränkungen

Micro-Trader befindet sich aktiv in Entwicklung.

## Risk 70 — Kandidatenauswahl

Das Zusammenspiel zwischen Budgetfilter und Positionsgröße benötigt Korrektur bzw. weitere Validierung.

## KI-Learning

Die Learning Engine benötigt eine stärkere Validierung, bevor gelernte Regeln als zuverlässige Trading-Erkenntnisse behandelt werden können.

## Production Multi-Tenancy

Die Anwendung verfügt über Tenant-Isolation, aber der Umfang der realen Multi-Tenant-Produktionsvalidierung ist derzeit begrenzt.

## Security Hardening

Einige Sicherheitsmechanismen benötigen weitere Härtung und breitere Tests.

## Marktdaten-Persistenz

Nicht jeder Marktkontext wird möglicherweise so vollständig persistiert, dass jede historische KI-Entscheidung vollständig reproduzierbar wäre.

Diese Einschränkungen werden bewusst transparent dargestellt.

Die vollständige technische Analyse, Reproduktion und Root-Cause-Dokumentation befindet sich im Handoff.

---

# Roadmap

Die bevorzugte Entwicklungsreihenfolge ist:

## 1. Trading Core stabilisieren

* Risk 70 korrigieren
* Budgetlogik zentralisieren
* doppelte Filter entfernen
* sämtliche Risikolevel validieren
* Behavioral Tests erweitern

## 2. Observability verbessern

* vollständige Decision IDs
* Market Snapshots
* Strategy Versions
* Prompt Versions
* Ruleset Versions
* Model-/Provider-Tracking

## 3. Reproduzierbarkeit verbessern

Eine historische KI-Entscheidung sollte langfristig anhand folgender Informationen rekonstruierbar sein:

```text
Market Snapshot
+
Strategy Version
+
Risk Profile
+
Ruleset Version
+
Prompt Version
+
Model
+
KI-Entscheidung
+
Execution Result
```

## 4. KI-Learning kontrollieren

Zielprozess:

```text
Beobachtung
  ↓
Regelkandidat
  ↓
Backtest
  ↓
Paper Validation
  ↓
Freigabe
  ↓
Aktive Regel
```

## 5. Security Hardening

Weiterentwicklung von:

* CSRF-Schutz
* Session Security
* MFA
* Recovery
* API Scopes
* Audit Controls
* Tenant-Isolation-Tests
* Security Regression Tests

## 6. Vorbereitung auf Live Trading

Live Trading ist **nicht einfach das nächste Feature**.

Vor einer möglichen Aktivierung müssen explizite Anforderungen für:

* Security
* Risk
* Audit
* Reproduzierbarkeit
* Betrieb
* Fehlerbehandlung
* Recovery
* Validierung

erfüllt sein.

---

# Dokumentation

Die README ist bewusst als **Einstiegspunkt** gehalten.

Die vollständige technische Dokumentation enthält deutlich mehr Details, unter anderem:

* vollständige Architektur
* konkrete Dateien und Funktionen
* Datenbankschema
* Strategielogik und Formeln
* Risikomatrizen
* KI-Prompts
* Provider-Fallbacks
* Scheduler
* Security-Implementierung
* historische Bugs
* Root-Cause-Analysen
* Tests
* Architecture Decision Records
* Troubleshooting
* Betriebsprozesse
* Zielarchitektur

Empfohlene Dokumentationsstruktur:

```text
README.md

docs/
├── HANDOFF.md
├── ARCHITECTURE.md
├── TRADING.md
├── RISK.md
├── AI.md
├── SECURITY.md
├── DATABASE.md
├── TESTING.md
├── OPERATIONS.md
├── TROUBLESHOOTING.md
├── ADR/
└── ROADMAP.md
```

Die Aufgabenteilung ist bewusst:

> **README = Was ist Micro-Trader und warum ist es interessant?**

> **Handoff = Wie funktioniert Micro-Trader tatsächlich?**

---

# Mitwirken

Beiträge sollten die Trennung zwischen folgenden Bereichen erhalten:

```text
KI
Strategy
Risk
Execution
Governance
Database
Security
```

Änderungen an Trading-Logik müssen geeignete Regression Tests enthalten.

Änderungen an Security, Tenant-Isolation oder Order Execution müssen entsprechende Security- und Behavioral Tests enthalten.

Vor Änderungen an kritischer Trading-Logik:

1. aktuelle Implementierung verstehen
2. bestehende Tests prüfen
3. bekannte Probleme prüfen
4. Regression Test definieren
5. Änderung durchführen
6. relevante Tests ausführen
7. technische Dokumentation aktualisieren

---

# Haftungsausschluss

Micro-Trader ist ein Softwareentwicklungs- und Forschungsprojekt.

**Diese Software stellt keine Finanzberatung dar.**

Ergebnisse aus Paper Trading garantieren keine Ergebnisse im realen Handel.

Marktdaten können verspätet, unvollständig oder fehlerhaft sein.

KI-generierte Analysen können falsch sein.

Strategien können versagen.

Historische Ergebnisse sind keine Garantie für zukünftige Ergebnisse.

Eine Aktivierung von Echtgeldhandel sollte erst nach einer unabhängigen technischen, sicherheitsbezogenen und risikobezogenen Validierung sowie geeigneten betrieblichen Schutzmaßnahmen erfolgen.

---

# Philosophie

Micro-Trader basiert auf einem einfachen Prinzip:

> **KI dort einsetzen, wo Analyse und Mustererkennung hilfreich sind. Deterministische Systeme dort einsetzen, wo Sicherheit, Limits und Governance erforderlich sind.**

Das Ziel ist nicht, eine KI zu bauen, die ohne Einschränkungen handeln kann.

Das Ziel ist ein System, bei dem:

```text
KI
 ↓
Analyse

Strategie
 ↓
Struktur

Risk Engine
 ↓
Limits

Governance
 ↓
Berechtigung

Execution
 ↓
Kontrollierte Aktion

Audit
 ↓
Nachvollziehbarkeit
```

Jede wichtige Entscheidung soll langfristig erklärbar, reproduzierbar und nachvollziehbar sein.

---

**Projektstatus:** Aktive Entwicklung / Paper Trading

**Live Trading:** Deaktiviert
