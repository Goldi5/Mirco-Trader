"""live_system.py — Phase 7: Getrenntes Live-System (Gerüst).

AUFTRAG §2.2: Live-System ist strikt getrennt vom Lern-/Paper-System:
- eigene Secrets (live_secret_store, tenant-isoliert)
- eigene Brokerverbindung (nur via Simulator/Sandbox, NIEMALS echte Orders hier)
- eigener Scheduler (live_loop, separat vom batch_trader)
- eigene Risiko-Limits (live_risk_limits)
- eigener Audit-Log (live_audit)
- eigener Kill-Switch (live_kill_switch)
- eigene Monitoring-Schicht
- nur freigegebene Releases (live_release Gate, siehe freigabe.py / Phase 8)

SICHERHEIT: PAPER_ONLY gilt weiter. Dieses Modul enthält KEINE echten
Broker-Orders. Broker-Adapter ist Phase 9 (Simulator/Sandbox). Live-Aktivierung
nur durch manuellen Prozess Phase 14.

Aufruf: from live_system import LiveSystem
"""

import os, json, sqlite3, time, threading
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "micro_trader.db")

# Eigener Kill-Switch-State (nur Live)
_KILL_SWITCH_FILE = os.path.join(BASE, "live_kill_switch.json")
_LIVE_CONFIG_FILE = os.path.join(BASE, "live_config.json")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LiveSystem:
    """Kapselt den isolierten Live-Bereich. Liest KEINE Lern-JSON / Paper-Depots."""

    def __init__(self, tenant_id=1):
        self.tenant_id = tenant_id
        self.config = self._lade_config()
        self.kill_switch = self._lade_kill_switch()

    def _lade_config(self):
        if os.path.exists(_LIVE_CONFIG_FILE):
            try:
                return json.load(open(_LIVE_CONFIG_FILE, encoding="utf-8"))
            except Exception:
                pass
        # Default: deaktiviert (PAPER_ONLY), nur Zielzustand vorbereitet
        return {
            "aktiv": False,            # NIEMALS True ohne Phase-14-Freigabe
            "modus": "PAPER_ONLY",
            "broker": None,             # Phase 9: Simulator/Sandbox
            "max_positions": 1,         # Micro-Live: 1 Portfolio (Phase 13)
            "max_pos_groesse": 100.0,   # harte Limits (Phase 13)
            "tagesverlust_limit": 10.0,
            "gesamtverlust_limit": 20.0,
            "drawdown_limit": 15.0,
            "erstellt": _now(),
        }

    def _lade_kill_switch(self):
        if os.path.exists(_KILL_SWITCH_FILE):
            try:
                return json.load(open(_KILL_SWITCH_FILE, encoding="utf-8"))
            except Exception:
                pass
        return {"safe_stop": True, "grund": "Initial (PAPER_ONLY)", "zeit": _now()}

    def speichern(self):
        json.dump(self.config, open(_LIVE_CONFIG_FILE, "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
        json.dump(self.kill_switch, open(_KILL_SWITCH_FILE, "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)

    # ── Kill-Switch (eigen, Phase 11 detailliert) ──
    def kill_switch_aktivieren(self, grund="Manuell"):
        self.kill_switch = {"safe_stop": True, "grund": grund, "zeit": _now()}
        self.speichern()
        self._audit("KILL_SWITCH_ON", grund)
        return True

    def kill_switch_freigeben(self, grund="Manuell"):
        # Nur mit autorisierter Freigabe (Phase 14). Hier nur Platzhalter.
        self.kill_switch = {"safe_stop": False, "grund": grund, "zeit": _now()}
        self.speichern()
        self._audit("KILL_SWITCH_OFF", grund)
        return True

    @property
    def ist_gestoppt(self):
        return bool(self.kill_switch.get("safe_stop"))

    # ── eigene Audit-Log (isoliert von Paper-Audit) ──
    def _audit(self, aktion, detail=""):
        pf = os.path.join(BASE, "live_audit.json")
        log = []
        if os.path.exists(pf):
            try:
                log = json.load(open(pf, encoding="utf-8"))
            except Exception:
                log = []
        log.append({"zeit": _now(), "tenant": self.tenant_id, "aktion": aktion,
                    "detail": detail})
        json.dump(log[-500:], open(pf, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # ── Release-Gate (Phase 8): nur freigegebene Releases ausführen ──
    def release_erlaubt(self, release_hash):
        """Prüft ob Release im live_release Gate freigegeben ist.
        Platzhalter: Phase 8 implementiert Registry."""
        from db import MTDB
        try:
            row = MTDB().conn.execute(
                "SELECT status FROM live_requests WHERE release_hash=?",
                (release_hash,)).fetchone()
            return bool(row and row[0] == "APPROVED")
        except Exception:
            return False

    def status(self):
        return {
            "tenant": self.tenant_id,
            "aktiv": self.config.get("aktiv"),
            "modus": self.config.get("modus"),
            "safe_stop": self.ist_gestoppt,
            "broker": self.config.get("broker"),
            "limits": {
                "max_positions": self.config.get("max_positions"),
                "max_pos_groesse": self.config.get("max_pos_groesse"),
                "tagesverlust": self.config.get("tagesverlust_limit"),
                "gesamtverlust": self.config.get("gesamtverlust_limit"),
                "drawdown": self.config.get("drawdown_limit"),
            },
        }


if __name__ == "__main__":
    ls = LiveSystem(tenant_id=1)
    print(json.dumps(ls.status(), indent=2, ensure_ascii=False))
    print("Kill-Switch aktiv?", ls.ist_gestoppt)
