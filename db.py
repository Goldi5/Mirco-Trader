#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Micro-Trader Analyse-Datenbank (SQLite).

Sekundaerer Store fuer schnelles Auslesen + Quer-Analysen.
Primary bleiben die JSON-Depot-Dateien; diese DB spiegelt sie regelmaessig
(_sync()) fuer Dashboard/Reports/Auswertungen. Kein Server noetig.

Schemas:
  trades          Alle Ausfuehrungen (Aktien/ETF/Spec)
  ki_decisions    Alle KI-Entscheidungen (ki_log.json)
  depot_snapshot  Wert-Stand pro Depot + Zeit
  markt_daten     Kurs/RSI/SMA pro Ticker + Zeit

Nutzung:
  from db import MTDB
  db = MTDB()            # oeffnet micro_trader.db
  db.sync()              # spiegelt alle JSONs -> DB
  db.trades_letzte(7)    # alle Trades der letzten 7 Tage
  db.ki_aktionen_vert()  # Verteilung kaufen/verkaufen/halten
"""
import os, json, sqlite3, glob
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PFAD = os.path.join(BASE, "micro_trader.db")


class MTDB:
    def __init__(self, pfad=DB_PFAD):
        self.pfad = pfad
        self.conn = sqlite3.connect(pfad)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        c = self.conn.cursor()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zeit TEXT, depot_typ TEXT, ticker TEXT, aktion TEXT,
            menge REAL, preis REAL, grund TEXT, konfidenz REAL
        );
        CREATE INDEX IF NOT EXISTS idx_trades_zeit ON trades(zeit);
        CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);

        CREATE TABLE IF NOT EXISTS ki_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zeit TEXT, ticker TEXT, aktion TEXT, konfidenz REAL,
            grund TEXT, depot_typ TEXT, risk INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_ki_zeit ON ki_decisions(zeit);

        CREATE TABLE IF NOT EXISTS depot_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zeit TEXT, depot_typ TEXT, ref TEXT, wert REAL,
            rendite REAL, shares REAL, bargeld REAL
        );
        CREATE INDEX IF NOT EXISTS idx_snap_zeit ON depot_snapshot(zeit);

        CREATE TABLE IF NOT EXISTS markt_daten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zeit TEXT, ticker TEXT, kurs REAL, rsi REAL,
            sma20 REAL, sma50 REAL
        );
        CREATE INDEX IF NOT EXISTS idx_markt_ticker ON markt_daten(ticker);
        """)
        self.conn.commit()

    # ── Sync: JSON -> DB ──
    def sync(self, verbose=False):
        self._sync_trades()
        self._sync_ki()
        self._sync_snapshots()
        self.conn.commit()
        if verbose:
            print("DB-Sync fertig:", self.stats())

    def _sync_trades(self):
        c = self.conn.cursor()
        # Letzter Stand, um Duplikate zu vermeiden
        last = c.execute("SELECT MAX(zeit) FROM trades").fetchone()[0] or "0"
        # Aktien
        for fn in glob.glob(os.path.join(BASE, "depot_*.json")):
            self._trades_aus_datei(fn, "aktien", last)
        # ETF
        for fn in glob.glob(os.path.join(BASE, "etf_0*.json")):
            self._trades_aus_datei(fn, "etf", last)
        # Spec
        for fn in glob.glob(os.path.join(BASE, "spec_depots", "*.json")):
            self._trades_aus_datei(fn, "spec", last, ticker_aus_dateiname=True)

    def _trades_aus_datei(self, fn, typ, last, ticker_aus_dateiname=False):
        c = self.conn.cursor()
        try:
            d = json.load(open(fn, encoding="utf-8"))
        except Exception:
            return
        ticker = d.get("ticker")
        if ticker_aus_dateiname and not ticker:
            ticker = os.path.basename(fn).replace(".json", "")
        for t in d.get("trades", []):
            if not isinstance(t, dict):
                continue
            zeit = t.get("zeit", "")
            if zeit <= last:
                continue
            aktion = t.get("aktion") or t.get("typ") or "?"
            c.execute(
                "INSERT INTO trades (zeit, depot_typ, ticker, aktion, menge, preis, grund, konfidenz) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (zeit, typ, ticker, aktion,
                 t.get("menge", 0), t.get("preis", 0),
                 str(t.get("grund", ""))[:200], t.get("konfidenz")))

    def _sync_ki(self):
        c = self.conn.cursor()
        last = c.execute("SELECT MAX(zeit) FROM ki_decisions").fetchone()[0] or "0"
        pfad = os.path.join(BASE, "ki_log.json")
        if not os.path.exists(pfad):
            return
        try:
            data = json.load(open(pfad, encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, list):
            return
        for e in data:
            zeit = e.get("zeit", "")
            if zeit <= last:
                continue
            c.execute(
                "INSERT INTO ki_decisions (zeit, ticker, aktion, konfidenz, grund, depot_typ, risk) "
                "VALUES (?,?,?,?,?,?,?)",
                (zeit, e.get("ticker"), e.get("aktion"), e.get("konfidenz"),
                 str(e.get("grund", ""))[:200], e.get("depot_typ"), e.get("risk")))

    def _sync_snapshots(self):
        c = self.conn.cursor()
        jetzt = datetime.now().isoformat()
        # Aktien
        for fn in glob.glob(os.path.join(BASE, "depot_*.json")):
            self._snapshot_aus_datei(fn, "aktien", jetzt)
        for fn in glob.glob(os.path.join(BASE, "etf_0*.json")):
            self._snapshot_aus_datei(fn, "etf", jetzt)
        for fn in glob.glob(os.path.join(BASE, "spec_depots", "*.json")):
            self._snapshot_aus_datei(fn, "spec", jetzt, ticker_aus_dateiname=True)

    def _snapshot_aus_datei(self, fn, typ, jetzt, ticker_aus_dateiname=False):
        c = self.conn.cursor()
        try:
            d = json.load(open(fn, encoding="utf-8"))
        except Exception:
            return
        ref = d.get("ticker")
        if ticker_aus_dateiname and not ref:
            ref = os.path.basename(fn).replace(".json", "")
        wert = d.get("wert") or d.get("bargeld", 0)
        rendite = d.get("rendite", 0)
        if not rendite and d.get("start_wert"):
            rendite = (wert / d.get("start_wert") - 1) * 100
        c.execute(
            "INSERT INTO depot_snapshot (zeit, depot_typ, ref, wert, rendite, shares, bargeld) "
            "VALUES (?,?,?,?,?,?,?)",
            (jetzt, typ, ref, wert, rendite,
             d.get("shares", 0), d.get("bargeld", 0)))

    # ── Abfragen ──
    def stats(self):
        c = self.conn.cursor()
        return {
            "trades": c.execute("SELECT COUNT(*) FROM trades").fetchone()[0],
            "ki_decisions": c.execute("SELECT COUNT(*) FROM ki_decisions").fetchone()[0],
            "snapshots": c.execute("SELECT COUNT(*) FROM depot_snapshot").fetchone()[0],
        }

    def trades_letzte(self, tage=7):
        since = (datetime.now() - timedelta(days=tage)).isoformat()
        rows = self.conn.execute(
            "SELECT zeit, depot_typ, ticker, aktion, menge, preis FROM trades "
            "WHERE zeit >= ? ORDER BY zeit DESC", (since,)).fetchall()
        return [dict(r) for r in rows]

    def ki_aktionen_vert(self):
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT aktion, COUNT(*) FROM ki_decisions GROUP BY aktion").fetchall()
        return {r["aktion"]: r["COUNT(*)"] for r in rows}

    def trades_nach_typ(self, tage=7):
        since = (datetime.now() - timedelta(days=tage)).isoformat()
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT depot_typ, aktion, COUNT(*) FROM trades WHERE zeit >= ? "
            "GROUP BY depot_typ, aktion", (since,)).fetchall()
        res = {}
        for r in rows:
            res.setdefault(r["depot_typ"], {})[r["aktion"]] = r["COUNT(*)"]
        return res

    def query_trades(self, typ=None, ticker=None, aktion=None, tage=30,
                     limit=200, order="DESC"):
        """Flexible Trade-Suche mit Filtern.
        typ: 'aktien'|'etf'|'spec'|None (alle)
        ticker: Teilstring-Suche (LIKE %x%)
        aktion: 'kaufen'|'verkaufen'|None
        tage: nur Trades der letzten N Tage
        order: 'DESC'|'ASC' (Zeit)
        """
        since = (datetime.now() - timedelta(days=tage)).isoformat()
        sql = ("SELECT zeit, depot_typ, ticker, aktion, menge, preis, grund, konfidenz "
               "FROM trades WHERE zeit >= ?")
        params = [since]
        if typ:
            sql += " AND depot_typ = ?"
            params.append(typ)
        if ticker:
            sql += " AND ticker LIKE ?"
            params.append(f"%{ticker}%")
        if aktion:
            sql += " AND aktion = ?"
            params.append(aktion)
        sql += f" ORDER BY zeit {order} LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def query_ki(self, typ=None, ticker=None, aktion=None, tage=30,
                 limit=200, order="DESC"):
        """Flexible KI-Entscheidungs-Suche (ki_decisions Tabelle)."""
        since = (datetime.now() - timedelta(days=tage)).isoformat()
        sql = ("SELECT zeit, ticker, aktion, konfidenz, grund, depot_typ, risk "
               "FROM ki_decisions WHERE zeit >= ?")
        params = [since]
        if typ:
            sql += " AND depot_typ = ?"
            params.append(typ)
        if ticker:
            sql += " AND ticker LIKE ?"
            params.append(f"%{ticker}%")
        if aktion:
            sql += " AND aktion = ?"
            params.append(aktion)
        sql += f" ORDER BY zeit {order} LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def analyse_karten(self, tage=30):
        """Phase E: Kompakte Kennzahlen für Analyse-Tab (ehrlich, keine erfundenen Felder)."""
        since = (datetime.now() - timedelta(days=tage)).isoformat()
        c = self.conn
        trades = c.execute("SELECT aktion, konfidenz FROM trades WHERE zeit >= ?", (since,)).fetchall()
        kis = c.execute("SELECT aktion, konfidenz FROM ki_decisions WHERE zeit >= ?", (since,)).fetchall()
        n_trades = len(trades)
        n_ki = len(kis)
        kauf = sum(1 for t in trades if t["aktion"] == "kauf")
        verkauf = sum(1 for t in trades if t["aktion"] == "verkauf")
        halten = sum(1 for t in kis if t["aktion"] == "halten")
        # Konfidenz-Durchschnitt (nur wo vorhanden)
        konf_vals = [t["konfidenz"] for t in kis if t["konfidenz"] is not None]
        konf_schnitt = round(sum(konf_vals)/len(konf_vals), 1) if konf_vals else None
        # decision_id / Legacy / Provider: Felder existieren NICHT in DB -> ehrlich n/a
        return {
            "trades_zeitraum": n_trades,
            "ki_entscheidungen": n_ki,
            "kauf_verkauf_halte": {"kauf": kauf, "verkauf": verkauf, "halten": halten},
            "entscheidungen_mit_decision_id": "n/a (Feld nicht in DB)",
            "legacy_fallbacks": "n/a (Feld nicht in DB)",
            "konfidenz_schnitt": konf_schnitt,
            "konfidenz_ohne_treffer": "n/a",
            "provider_fehler": "n/a (Feld nicht in DB)",
            "cooldown_ereignisse": "siehe ki_cooldown.json",
            "trades_ohne_ki_zuordnung": "n/a (Feld nicht in DB)",
        }

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    db = MTDB()
    db.sync(verbose=True)
    print("\nKI-Aktionen (gesamt):", db.ki_aktionen_vert())
    print("Trades letzte 7 Tage:", db.trades_nach_typ(7))
