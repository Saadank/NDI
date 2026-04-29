# Datarix Frontend — Claude Instructions
> Read this file before doing ANYTHING in this project.

## Project Overview
Datarix is an enterprise data governance platform.
- Frontend: Next.js 15, TypeScript strict, Tailwind CSS, shadcn/ui
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- Frontend runs on: http://localhost:3001
- Branch: Frontend

## Code Quality Standards — Non-Negotiable
You are a Senior Software Engineer. Every line must reflect that.

- TypeScript strict mode — zero `any` types ever
- Every component has a typed props interface
- Max 150 lines per file — split if longer
- All API calls go through src/lib/api/client.ts ONLY
- Never call axios or fetch directly in components
- Use TanStack Query for ALL server state (GET → useQuery, mutations → useMutation)
- Use React Hook Form + Zod for ALL forms
- Use existing hooks in src/lib/hooks/ — never duplicate logic
- Clean, readable, well-commented code
- No dead code, no commented-out blocks
- Consistent naming: PascalCase components, camelCase functions, kebab-case files

## Design Rules — Non-Negotiable
- Read EVERY Pencil frame before writing any code
- Match Pencil designs PIXEL-PERFECT — nothing more, nothing less
- NEVER add UI elements not shown in Pencil
- NEVER guess any UI detail — if unclear STOP and ask
- NEVER improve or enhance from your own ideas
- If you have a suggestion or problem → STOP and tell the developer
- Wait for response before continuing
- The Pencil design file is the ONLY source of truth for UI
- Always read sidebar frames from Pencil before changing sidebar

## Role System — CRITICAL
This platform has 5 roles. Each role has completely different screens.
NEVER mix screens between roles.
ALWAYS read the frame name prefix to identify the role.

### Frame Name Prefixes:
- "Shared" or no prefix → all roles (Login, Notifications, Profile, Delegation)
- "DS ·" → Data Steward (requester)
- "DO ·" → Data Owner
- "DPO ·" → DPO
- "OA ·" → Org Admin
- "PA ·" → Platform Admin

### Test Users:
| Role | Email | Password |
|------|-------|----------|
| Data Steward | sara.fin@acme.local | Test123! |
| Data Owner | ahmed.do@acme.local | Test123! |
| DPO | nora.dpo@acme.local | Test123! |
| Org Admin | superadmin@datasharing.local | SuperAdmin123! |
| Platform Admin | superadmin@datasharing.local | SuperAdmin123! |

### Role Guards — every role-specific page MUST have this:
- Data Steward: useRoleGuard({ allow: ['requester', 'platform_admin'] })
- Data Owner: useRoleGuard({ allow: ['data_owner', 'platform_admin'] })
- DPO: useRoleGuard({ allow: ['dpo', 'platform_admin'] })
- Org Admin: useRoleGuard({ allow: ['org_admin', 'platform_admin'] })
- Platform Admin: useRoleGuard({ allow: ['platform_admin'] })

### Sidebar Per Role — EXACT from Pencil (NEVER change without reading Pencil):

DATA STEWARD:
  Header: DATARIX logo (standard)
  Main:
    My Requests (orange icon + orange count badge) → /data-sharing
    Raise New Request → /data-sharing/new
    Prepare & Upload → /prepare
  Bottom:
    All Products → /
    Notifications → /notifications
    Profile → /profile
  ⚠️ NO Delegation item

DATA OWNER:
  Header: DATARIX logo (standard)
  Main:
    Approvals Inbox (orange icon + orange count badge) → /approvals
    Request Detail + Actions → /approvals (highlights on /approvals/[id])
    My Department → /my-department
  Bottom:
    Product Portal → /
    Notifications → /notifications
    Profile → /profile
    Delegation → /delegation

DPO:
  Header: DATARIX logo (standard)
  Main:
    Organisation Request List → /dpo
    Request Detail + PDPL Review → /dpo/[id]
    Workflow Editor → /dpo/workflows
    Request Templates → /dpo/templates
    Audit Trail → /dpo/audit
  Bottom:
    Product Portal → /
    Notifications → /notifications
    Profile → /profile
    Delegation → /delegation

ORG ADMIN:
  Header: DATARIX logo (standard)
  Section "GOVERNANCE":
    Request List → /admin/requests
    Request Detail → /admin/requests/[id]
    Workflow Editor → /admin/workflows
    Request Templates → /admin/templates
    Audit Trail → /admin/audit
  Section "ADMINISTRATION":
    Departments → /admin/departments
    Users → /admin/users
    Database Connections → /admin/connections
    Business Holidays → /admin/holidays
    Retention Policy → /admin/retention
  Bottom:
    Product Portal → /
    Notifications → /notifications
    Profile → /profile
    Delegation → /delegation

PLATFORM ADMIN:
  Header: DATARIX logo + "PLATFORM ADMIN" text + orange "ADMIN" badge
  Main:
    Organisations → /platform/organisations
    Onboard Company → /platform/onboard
  Bottom:
    Platform Vendor name + avatar (no Product Portal link)

## Process — Follow for EVERY Screen
1. Read frame from Pencil MCP (screenshot + node details)
2. Identify role from frame name prefix
3. Check CHECKLIST.md — is it already done?
4. If done → compare with Pencil and fix differences only
5. If not done → implement pixel-perfect from Pencil
6. Add useRoleGuard for correct role
7. Connect to real API endpoint
8. Run: npx tsc --noEmit → must be 0 errors
9. Update CHECKLIST.md → mark as done
10. NEVER move to next screen until all 9 steps pass

## API Rules
- Base URL: http://localhost:8000
- All calls through src/lib/api/client.ts
- Bearer token handled automatically by interceptor
- On 401 → auto-refresh → on fail → redirect to /login
- Always show loading skeleton while fetching
- Always show error toast on failure

## Known Issues to Fix (in order):
1. DS /data-sharing/[id] → Changes Requested banner wrong condition
2. /prepare/[id] → Missing request info card + virus scan states
3. /approvals → Empty state missing buttons
4. /approvals/[id] → Flagged for Technical Review state missing
5. /dpo → Presets panel missing
6. /dpo → Export modal missing (direct CSV download instead)
7. /dpo/[id] → Data Minimisation tab shows wrong content
8. /dpo/[id] → DPIA tab shows wrong content
9. /dpo/[id] → Missing 4th PDPL checks summary tab
10. /my-department → Missing delegation-active banner
11. /my-department → Delegation pane layout wrong
12. /admin/departments → Delete-blocked modal shows wrong content + wrong button
13. /admin/users → Deactivate modal missing blocking requests list
14. /admin/holidays → Add Holiday should be full page not modal
15. /pickup/[token] → Complete stub only (returns null)
16. /prepare/[id] → Mode B (SQL structured data) flow not built
17. /admin/connections → Add Connection wizard step 2 missing

## Git Rules
- Branch: Frontend
- After every feature: git add -A && git commit -m "descriptive message"
- Push: git push origin Frontend
- Commit messages must describe what changed specifically
