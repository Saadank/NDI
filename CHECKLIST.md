# Datarix Frontend — Screen Checklist

Legend: ✅ Complete · ⚠️ Partial · ❌ Missing · 🔧 Bug

---

## WORKFLOW ENGINE — spec v4.0 §4.4 compliance

| Spec rule | Status | Notes |
|-----------|--------|-------|
| 5-step canonical workflow (DPO → Source DO → Receiver DO → Source Steward → Delivery) | ✅ | `WorkflowEngine.create_workflow_steps` resolves assignees by `step_type`. CRITICAL: the source/receiver-vs-DB column mapping FLIPS by `request_direction` — see CLAUDE.md "Request Direction" section. The mapping is documented inline in the engine. |
| PULL vs PUSH direction (extension to spec §3.3) | ✅ | New `t_share_requests.request_direction` column (`pull`/`push`, default `pull`). Wizard Step 1 asks "request data from" vs "share data with". PUSH skips Source Steward Upload (file/SQL provided at create-time) and validates ≥1 attached file (file mode) or connection+selection (structured). External shares still skip Receiver DO. |
| SLA caps per classification (public 30 / internal 14 / confidential 7 / sensitive 3 business days) | ✅ | `_effective_sla_days` applies `min(template_sla, classification_cap)`. |
| Auto-delegation for self-approval (spec §3.5 / BRD EC-02/03/04) | ✅ | `ConflictService.resolve_step_conflicts` runs after step creation, reassigns to first Org Admin, logs `step.auto_delegated` with rule id. |
| Workflow B (Lite) — skip DPO when (public\|internal) AND !personal_data | ✅ | Engine's `_is_lite_workflow` skips the `dpo_review` step type without needing a separate template. |
| External shares skip Receiver Data Owner Confirmation | ✅ | Engine drops `receiver_data_owner_confirmation` when `sharing_type=='external'`. |
| DPO re-trigger on material PDPL changes at resubmit | ⚠️ | `submit_request` now accepts `changes_requested` status as a resubmit; `_maybe_retrigger_dpo` diffs PDPL fields against the last `request.submitted` audit snapshot. Resets DPO step to pending + later steps to waiting + writes `step.dpo_retriggered` audit row. **Untested live** — first-time resubmits where no prior snapshot exists default to "re-trigger" to be safe. |
| `can_approve_step` requires step.status == 'pending' | ✅ | Mirrors actual `/approve` endpoint gate so frontend never renders buttons that would 4xx. |

### Canonical default-template seed (POST `/api/v1/products/data-sharing/workflows/templates`)

```json
{
  "name": "Internal Default — Spec v4.0",
  "sharing_type": "internal",
  "data_classification": null,
  "is_active": true,
  "steps": [
    { "step_type": "dpo_review",                       "name": "DPO PDPL Review",                 "assignee_role": "dpo",          "execution_mode": "sequential", "sla_days": 2, "condition_expr": null },
    { "step_type": "source_data_owner_approval",       "name": "Source Data Owner Approval",      "assignee_role": "data_owner",   "execution_mode": "sequential", "sla_days": 3, "condition_expr": null },
    { "step_type": "receiver_data_owner_confirmation", "name": "Receiver Data Owner Confirmation","assignee_role": "data_owner",   "execution_mode": "sequential", "sla_days": 1, "condition_expr": null },
    { "step_type": "source_steward_upload",            "name": "Source Steward Upload",           "assignee_role": "source",       "execution_mode": "sequential", "sla_days": 2, "condition_expr": null },
    { "step_type": "delivery",                         "name": "Delivery",                         "assignee_role": null,           "execution_mode": "sequential", "sla_days": 0, "condition_expr": null }
  ]
}
```

External shares automatically drop step 3 (Receiver DO). Lite workflows
(`public`/`internal` + non-personal) automatically drop step 1 (DPO).

---

## SHARED / ALL ROLES

| Screen | Frame | Status | Notes |
|--------|-------|--------|-------|
| Login (email+password) | — | ✅ | |
| Login SSO | — | ✅ | |
| Login TOTP | — | ✅ | |
| Forgot Password | — | ✅ | |
| Notifications list | — | ✅ | |
| Profile — overview | — | ✅ | Null-safe initials/name + isError fallback |
| Profile — change password | — | ✅ | |
| Profile — notification prefs | — | ✅ | |
| Delegation — set up | qw3jM | ✅ | |
| Delegation — active window | Mf5ZW | ✅ | |
| Delegation — expired | 5s9YO | ✅ | |
| **Topbar — identity widget** | — | ✅ | Name + role + dept + avatar visible on every dashboard page (all 5 roles) |
| **Topbar — Logout** | — | ✅ | Avatar dropdown clears auth + React Query cache + redirects to /login |

---

## DATA STEWARD

### My Requests List (`/data-sharing`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Populated list | KxDl8 | ✅ | |
| Empty state | 45v1c | ✅ | |
| Filters open | ZikVt | ✅ | |
| New Request button visible | XreaV | ✅ | |

### Request Detail (`/data-sharing/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Default / Submitted view | CizJ4 | ✅ | |
| Changes Requested banner | 8c02C | 🔧 | Banner fires on `rejected` not `changes_requested` — fix condition |
| Rejected state | Egmbo | ✅ | |
| Approved state | 3Pt7o | ✅ | |
| Cancelled state | ZOkpF | ✅ | |

### New Request Wizard (`/data-sharing/new`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Step 1 — Basic Info | — | ✅ | |
| Step 2 — Data Selection | — | ✅ | |
| Step 3 — Review & Submit | — | ✅ | |

### Prepare & Upload — Mode A: File Upload (`/prepare/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Upload landing (empty) | Zl4He | ⚠️ | Missing: request info card, Approved Selection panel |
| File uploading / progress | XqIo5 | ❌ | No progress bar per file |
| Virus scan in progress | 58hB9 | ❌ | No scanning state (queued→scanning) |
| Scan failed | OO2iL | ❌ | No scan-failed error state per file |
| Scan clean → Submit enabled | Zl4He | ❌ | "Submit to Requester" stays disabled |
| Raise an issue | — | ❌ | Button missing |

### Prepare & Upload — Mode B: Structured / SQL (`/prepare/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| DB connection picker | eJ6GL | ❌ | Not built |
| Table / query selector | RfplG | ❌ | Not built |
| Preview grid | jbcjq | ❌ | Not built |
| Confirm & submit | 95Oix | ❌ | Not built |

---

## DATA OWNER

> **Sidebar:** "Request Detail + Actions" item removed — DO sidebar now
> only has Approvals Inbox + My Department. Detail is reached by clicking
> a row.

### Approvals Inbox (`/approvals`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Outgoing tab — populated | dQEVX | ✅ | Filter inverted: outgoing now = receiver_group_id === my group (heavy review) |
| Incoming tab — populated | fLHDN | ✅ | requester_group_id === my group; row routes to `/approvals/incoming/[id]`; blue Confirm pill |
| Empty state | hQgJX | ✅ | "View recent dept activity" + orange "Return to Product Portal" buttons added |

### Outgoing Detail — Heavy review (`/approvals/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Mode A — file request | WHxPV | ✅ | FilesCard now shows "Scanned clean" chip per file status |
| Mode B — query preview | WZ5ul | ✅ | Connection chip + dark syntax-highlighted SQL block + 100-row preview placeholder |
| Approve modal | — | ✅ | Optional comment, redirects to /approvals |
| Request Changes modal | eWYRp | ✅ | Required comment, amber DPO re-trigger note |
| Reject modal | gJVwr | ✅ | Red banner, 2 chips ("Insufficient justification", "PDPL basis unclear"), required reason |
| Flag for Technical Review modal | myJeN | ✅ | Reviewer + required comment; submits via request-changes with `[FLAG: name]` prefix |
| Flagged-state banner + footer chip | myJeN | ✅ | Reads `[FLAG: …]` marker; shows blue banner + "Flagged · Waiting on …" chip |

### Incoming Detail — Light confirm (`/approvals/incoming/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Page (file mode + structured mode) | NEW | ✅ | No SQL, no PDPL, simpler summary card + read-only files / schema preview |
| Confirm receipt modal | NEW | ✅ | Optional comment; orange Confirm; POST step approve |
| Decline modal | NEW | ✅ | Required reason; red Decline; POST step reject |
| Request more details modal | NEW | ✅ | Required comment; orange Send; POST step request-changes |

### My Department (`/my-department`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Steward list (default) | bTnoL | ✅ | Members table + active delegation surfaced inline |
| Add Steward modal | CsiYN | ✅ | Tenant-member picker, excludes existing members |
| Role Delegation card | NMO4e | ✅ | Green status header + backup picker + window dates |
| Delegation active banner | bTnoL | ✅ | Now blue (`#EFF6FF` / `#1D4ED8`) per Pencil — was orange |

---

## DPO

### DPO Request Detail (`/dpo/[id]`) — action wiring

| Button | Status | Notes |
|--------|--------|-------|
| Approve modal | ✅ | Removed silent `void`, surfaces errors inline |
| Reject modal | ✅ | Same |
| Request Changes modal | ✅ | Same |

> **Sidebar:** trimmed to 4 items per Pencil — Organisation Request List,
> Workflow Editor, External Recipients Directory, Audit Trail. The
> "Request Detail + PDPL Review" duplicate was removed (reach the detail
> by clicking a row). "Request Templates" sidebar entry removed; the
> `/dpo/templates` route remains orphaned for now.

### DPO Request List (`/dpo`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Populated list | JrK39 | ✅ | Header counts (N total · M awaiting DPO review · K in progress) wired |
| Saved Filter Presets panel | yb3bg | ✅ | Presets row toggle, default presets, click-to-apply, X-to-clear |
| Export modal | Ynk3G | ✅ | Active filter chips + PDF/CSV format radios + count-aware Export button |

### DPO Request Detail + PDPL Review (`/dpo/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Legal Basis tab | aJ5Mp | ✅ | DPO override (Accept/Override) + justification |
| Data Minimisation tab | C093h | ✅ | 5-row colour-coded check list + DPO assessment radios |
| DPIA Status tab | 2ehvN | ✅ | DPIA record card + verification radios + assessment radios |
| All Checks Summary (4th tab) | QQd5D | ✅ | Roll-up banner (green when complete / amber with N issues) + per-check ✓/✗ rows. Pencil only renders 3 tab labels visibly — added the 4th label per task spec |
| Sticky action bar | QQd5D | ✅ | Reject (red outline) / Request Changes (amber outline) / Approve Request (orange) — modals show errors inline, redirect to `/dpo` on success |

### DPO sub-pages

| Screen | Frame | Status | Notes |
|--------|-------|--------|-------|
| Workflow Editor list (`/dpo/workflows`) | NzuxG | ✅ | Versions pills, status badges, scope chips |
| Workflow Editor edit | 6ukvd | ✅ | Drag-drop steps, sharing-type/classification dropdowns, Save changes button |
| Save Workflow modal (Apply to active) | 0eeET | ✅ | Toggle + required justification + in-flight warning. Save invalidates list + per-template; create/save have `onError`; no INFLIGHT_COUNT placeholder |
| Audit Trail list | r3rex | ✅ | Filter chips + lock-icon append-only banner (gray, matches Pencil) |
| Audit Trail filtered | 6pTkz | ✅ | "N of M events match active filters" line + Clear filters action |
| Audit Trail export modal | 2VgF4 | ✅ | Active filter chips + PDF/CSV format + filename input + real export blob download |
| External Recipients list (`/dpo/recipients`) | rSC1w | ✅ | Counter chips (active/expired/revoked), filter chips, columns Org/Contact/Files/Token Status/Last Accessed/View+Revoke. Token-level fields fall back to `is_active` + "—" until backend exposes them |
| External Recipients view (`/dpo/recipients/[id]`) | RN3Ki | ✅ | NEW. Recipient Overview counters + Share Requests Delivered table (placeholder until per-request token endpoint) + Download Activity Log + CSV export. Revoke all active tokens button. |
| External Recipients revoke modal | CjghO | ✅ | NEW. Info rows + optional reason + red "Revoke access" button. Wired to `DELETE /external-recipients/{id}?reason=…` |
| Request Templates (`/dpo/templates`) | — | ⚠️ | Route file kept; sidebar link removed. Not in Pencil. Safe to delete in a follow-up |

---

## ORG ADMIN

### Departments (`/admin/departments`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| List | 7VRQU | ✅ | |
| Add/edit department modal | QVqAe | ✅ | |
| Delete blocked modal | QdoXs | ⚠️ | Shows generic text; needs blocking request list + "Reassign requests" button |

### Users (`/admin/users`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| User list | 9RBxy | ✅ | |
| Invite user modal | xAXsE | ✅ | Was 405; now POST /api/v1/platform/invitations/ via invitations.api.ts |
| Edit user modal (NEW) | — | ✅ | Pencil icon now wired; supports department change via PUT /platform/users/{id}/group |
| Deactivate confirm modal | nw5YQ | ✅ | Wired to POST /platform/users/{id}/deactivate (new backend route); shows active request list |

### Set Delegation on Behalf (`/admin/users/[userId]/delegation`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Full page | — | ✅ | |

### Business Holidays (`/admin/holidays`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Holiday list | HFIE1 | ✅ | URL was 404; fixed to GET /api/v1/platform/holidays/ |
| Add holiday — full page | 4oaiC | ✅ | URL was 404; fixed to POST /api/v1/platform/holidays/ via holidays.api.ts |
| Delete confirm | — | ❌ | No delete confirmation (UI not yet built) |

### Retention Policy (`/admin/retention`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Policy editor | ygqwL | ✅ | URL was wrong; fixed to PUT /api/v1/platform/tenants/{tenant_id}/retention-policy via tenants.api.ts |

### Database Connections (`/admin/connections`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| List + add (step 1) | — | ✅ | |
| Edit connection page | — | ✅ | Backend PUT /connections/{id} added; frontend now persists changes & surfaces errors |
| Connection wizard step 2 | tdvBK | ❌ | Wizard only has step 1 |

---

## PLATFORM ADMIN

### Organisations (`/platform/organisations`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Org list | nA3wN | ✅ | |

### Onboard Company (`/platform/onboard`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Step 1 — Company details | 9SDZB | ✅ | |
| Step 2 — Admin user | yb2n2 | ✅ | |
| Step 3 — Products | ZCpQy | ✅ | |
| Step 4 — Review | uZBf3 | ✅ | |

---

## EXTERNAL / PICKUP

| Screen | Frame | Status | Notes |
|--------|-------|--------|-------|
| Accept Invitation (`/pickup/[token]`) | zGwYH | ❌ | Stub `return null` — complete page missing |

---

## SIDEBAR

| Role | Status | Notes |
|------|--------|-------|
| Data Steward | ✅ | |
| Data Owner | ⚠️ | Missing "Request Detail + Actions" item; "All Products" should be "Product Portal" |
| DPO | ⚠️ | "Workflow Templates" should be "Request Templates"; External Recipients should be removed |
| Org Admin | ⚠️ | Missing GOVERNANCE section; "All Products" → "Product Portal"; footer missing Delegation |
| Platform Admin | ⚠️ | Missing special "PLATFORM ADMIN" header with "ADMIN" badge; footer should show vendor name/avatar |

---

## KNOWN ISSUES — FIX ORDER

| # | Location | Frame | Issue |
|---|----------|-------|-------|
| 1 | `/data-sharing/[id]` | 8c02C | Changes Requested banner condition: `rejected` → `changes_requested` |
| 2 | `/prepare/[id]` | Zl4He/XqIo5/58hB9/OO2iL | Complete Mode A virus scan flow |
| 3 | `/approvals` | hQgJX | Empty state missing two buttons |
| 4 | `/approvals/[id]` | myJeN | Flagged for Technical Review state |
| 5 | `/dpo` | yb3bg | Saved Filter Presets panel |
| 6 | `/dpo` | Ynk3G | Export modal (not direct CSV download) |
| 7 | `/dpo/[id]` | C093h/2ehvN/QQd5D | Data Min tab, DPIA tab, 4th "All PDPL Checks" tab |
| 8 | `/my-department` | bTnoL | Delegation active banner |
| 9 | `/my-department` | NMO4e | Delegation pane layout |
| 10 | `/admin/departments` | QdoXs | Delete blocked modal with request list |
| 11 | `/admin/users` | nw5YQ | Deactivate modal with user name + request count |
| 12 | `/admin/holidays` | 4oaiC | Add Holiday → full page (not modal) |
| 13 | `/pickup/[token]` | zGwYH | Implement full Accept Invitation page |
| 14 | `/prepare/[id]` | eJ6GL/RfplG/jbcjq/95Oix | Mode B structured/SQL data flow |
| 15 | `/admin/connections` | tdvBK | Connection wizard step 2 |
| 16 | Sidebar | — | Org Admin GOVERNANCE section |
| 17 | Sidebar | — | Platform Admin special header + footer |
