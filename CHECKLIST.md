# Datarix Frontend — Screen Checklist

Legend: ✅ Complete · ⚠️ Partial · ❌ Missing · 🔧 Bug

---

## SHARED / ALL ROLES

| Screen | Frame | Status | Notes |
|--------|-------|--------|-------|
| Login (email+password) | — | ✅ | |
| Login SSO | — | ✅ | |
| Login TOTP | — | ✅ | |
| Forgot Password | — | ✅ | |
| Notifications list | — | ✅ | |
| Profile — overview | — | ✅ | |
| Profile — change password | — | ✅ | |
| Profile — notification prefs | — | ✅ | |
| Delegation — set up | qw3jM | ✅ | |
| Delegation — active window | Mf5ZW | ✅ | |
| Delegation — expired | 5s9YO | ✅ | |

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

### Approvals Inbox (`/approvals`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Populated list | dQEVX | ✅ | |
| Pending-only list | fLHDN | ✅ | |
| Empty state | hQgJX | ⚠️ | Missing "View recent department activity" + "Return to Product Portal" buttons |

### Approval Detail (`/approvals/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Default / pending view | WHxPV | ✅ | |
| Approve flow | WZ5ul | ✅ | |
| Reject flow | eWYRp | ✅ | |
| Request changes flow | gJVwr | ✅ | |
| Flagged for Technical Review | myJeN | ❌ | Blue banner + "Flagged - Waiting on [name]" footer chip missing |

### My Department (`/my-department`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Default view | CsiYN | ✅ | |
| Delegation active banner | bTnoL | ❌ | Banner not shown when delegation is active |
| Delegation info pane | NMO4e | ⚠️ | Pane exists but layout doesn't match Pencil |

---

## DPO

### DPO Request List (`/dpo`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Populated list | JrK39 | ✅ | |
| Saved Filter Presets panel | yb3bg | ❌ | Presets button does nothing |
| Export modal | Ynk3G | ❌ | Export goes directly to CSV download; modal missing |

### DPO Request Detail + PDPL Review (`/dpo/[id]`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Overview tab | aJ5Mp | ✅ | |
| Data Minimisation tab | C093h | ⚠️ | Generic checkboxes; needs AI-generated color-coded checklist |
| DPIA Status tab | 2ehvN | ⚠️ | Generic dropdown; needs DPIA record display + "I reviewed DPIA-[id]" checkbox |
| All PDPL Checks tab (4th tab) | QQd5D | ❌ | Tab missing entirely |

### DPO sub-pages

| Screen | Frame | Status | Notes |
|--------|-------|--------|-------|
| Workflow Editor (`/dpo/workflows`) | — | ✅ | |
| Request Templates (`/dpo/templates`) | — | ✅ | |
| Audit Trail (`/dpo/audit`) | — | ✅ | |
| External Recipients (`/dpo/recipients`) | — | ❌ | Should not exist (removed in Pencil) |

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
| Invite user modal | xAXsE | ✅ | |
| Deactivate confirm modal | nw5YQ | ⚠️ | Shows generic warning; needs user name + active request count |

### Set Delegation on Behalf (`/admin/users/[userId]/delegation`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Full page | — | ✅ | |

### Business Holidays (`/admin/holidays`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Holiday list | HFIE1 | ✅ | |
| Add holiday — should be full page | 4oaiC | ❌ | Implemented as modal; Pencil shows full page with back nav |
| Delete confirm | — | ❌ | No delete confirmation |

### Retention Policy (`/admin/retention`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| Policy editor | ygqwL | ✅ | |

### Database Connections (`/admin/connections`)

| State | Frame | Status | Notes |
|-------|-------|--------|-------|
| List + add (step 1) | — | ✅ | |
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
