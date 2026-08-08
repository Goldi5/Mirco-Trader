# Rollen-/Berechtigungsmodell (PHASE 2, v2.27.0)

> Basis: Phase 0-Inventar (`PLATFORM-ARCHITECTURE-INVENTORY.md`) + Phase 1
> (`TENANT-DATA-MODEL.md`). OWASP Multi-Tenant-Cheat-Sheet: deny-by-default,
> serverseitige Autorisierung, Tenant nie aus Client-Input.

## Kernprinzip: Effektive Rolle

Jeder User hat zwei Rollen:

| Ebene | Quelle | Beispiel |
|-------|--------|----------|
| **Globale Rolle** | `security_users.json` → `user.role` | `user`, `operator`, `admin`, `superadmin` |
| **Tenant-Rolle** | `tenant_memberships.role` | User ist in Tenant A `admin`, in Tenant B nur `user` |

**Effektive Rolle** (`sec.effective_role(user, tenant_id)`):
1. Membership-Rolle im aktuellen Tenant (aktiv) **gewinnt**
2. sonst globale User-Rolle (Fallback)
3. sonst `visitor`

```
global: user  +  Tenant A-Membership: admin  →  effektiv in A: admin
global: user  +  Tenant B-Membership: (keine) →  effektiv in B: user
```

## Permission-Maps

`ROLE_PERMISSIONS` (global, Phase 6) bleibt unverändert für Nicht-Tenant-Code.
`TENANT_ROLE_PERMISSIONS` (neu, Phase 2) erweitert um `tenant_*`-Permissions:

| Permission | Bedeutung | Rollen |
|-----------|-----------|--------|
| `tenant_view` | Tenant-Daten sehen | user+ |
| `tenant_trade_control` | Trading-Pause/Resume im Tenant | operator+ |
| `tenant_manage` | Tenant-Konfiguration | admin |
| `tenant_members` | Mitglieder verwalten | admin |
| `tenant_delete` | Tenant löschen | **nur superadmin** |

`ALL_PERMISSIONS` = Vereinigung beider Maps (22 Permissions, für API/Doku).

## Zugriffsklassen (before_request)

`ROUTE_ACCESS` klassifiziert jede Route. **NEU in Phase 2: `TENANT_ADMIN`** —
prüft gegen die **effektive Rolle** (Membership gewinnt) und setzt den
Tenant-Kontext aus der Session (nie aus Client-Input):

| Klasse | Prüfung | Routen (Beispiele) |
|--------|---------|--------------------|
| PUBLIC | keine | `/`, `/landing`, `/assets/*` |
| AUTHENTICATED | gültige Session + Tenant-Kontext setzen | `/dashboard`, `/api/me`, `/api/me/permissions` |
| TENANT_ADMIN | effektive Rolle >= ADMIN | `/api/roles` |
| ANALYST/OPERATOR/ADMIN/SUPERADMIN | **globale** Rolle (systemweit) | `/api/tenants*`, `/api/users*`, `/admin/*` |

Sicherheits-Eigenschaft: Ein Tenant-Admin (global `user`) darf `/api/roles`
sehen (200), aber **nicht** `/api/tenants` oder `/api/users*` (403) — die
systemweite Verwaltung bleibt globalen Admins/Superadmins vorbehalten.

## Neue Funktionen (security.py)

```python
sec.effective_role(user, tenant_id=None)      # Membership > global > visitor
sec.effective_permissions(user, tenant_id=None)
sec.has_permission(user, perm, tenant_id=None)
sec.has_permission_in(role, perm)             # statisch, ohne DB
sec.require_tenant_role(min_role)             # Decorator (Tenant-Kontext)
sec.require_permission(perm)                  # Decorator
```

## Neue API-Routen (dashboard.py)

| Route | Klasse | Funktion |
|-------|--------|----------|
| `GET /api/roles` | TENANT_ADMIN | Rollenkatalog (6 Rollen, Level, Permissions) + `all_permissions` |
| `GET /api/me/permissions` | AUTHENTICATED | `effective_role` + Permissions im aktuellen Tenant |

`/api/me` zusätzlich: `effective_role` + `tenant_permissions`.

## UI

Mein-Konto zeigt neben der globalen Rolle die **effektive Rolle im Mandant**
(Chip „im Mandant: admin"), wenn sie abweicht.

## Tests (Sektion 7c, 14 neue → 69 OK, 0 FAIL)

- effektive Rolle gewinnt / fällt zurück je Tenant
- `tenant_manage` ja, `tenant_delete` nein (admin) / superadmin hat alles
- Tenant-Admin: `/api/roles` 200, `/api/tenants` 403 (systemweit)
- Operator ohne Membership: `/api/roles` 403
- `/api/me/permissions` liefert effektive Rechte je Rolle

## Offene Punkte (Folgephasen)

- Tenant-Switcher im UI (mehrere Memberships → aktiven Tenant wechseln)
- Datenfilterung: alle Queries/JSON-Pfade mit `tenant_id` (Phase 3)
- `/api/db_query` (ANALYST, direkter SQL) vor Mandanten-Trennung absichern
- CSRF-Token im HTML-Rendering verdrahten
