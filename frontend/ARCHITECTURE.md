# Datarix Frontend — Architecture

## Tech Stack
| Technology | Purpose |
|------------|---------|
| Next.js 15 (App Router) | Framework |
| TypeScript strict | Type safety |
| Tailwind CSS | Styling |
| shadcn/ui | UI components |
| TanStack Query v5 | Server state |
| Zustand | Client state |
| Axios | HTTP client |
| React Hook Form + Zod | Forms & validation |

## Route Groups
| Group | Purpose | Auth Required | Sidebar |
|-------|---------|--------------|---------|
| (auth) | Login screens | No | No |
| (shell) | Profile, Notifications, Delegation | Yes | No (topbar only) |
| (dashboard) | All feature screens | Yes | Yes (role-based) |
| pickup | External recipient portal | No | No |

## Complete Route Map
```
/                               → Product Portal (role-based redirect)
/login                          → Login
/login/sso                      → SSO login
/login/totp                     → TOTP 2FA
/login/forgot-password          → Forgot password

/notifications                  → Notifications (all roles)
/profile                        → User profile
/profile/password               → Change password
/profile/notifications          → Notification preferences
/delegation                     → Delegation set up
/delegation/active              → Delegation active window
/delegation/expired             → Delegation expired

/data-sharing                   → DS: My Requests list
/data-sharing/new               → DS: Raise New Request Step 1
/data-sharing/new/step-2        → DS: Step 2 Data Selection
/data-sharing/new/step-3        → DS: Step 3 Review & Submit
/data-sharing/[id]              → DS: Request Detail

/prepare                        → DS: Prepare & Upload list
/prepare/[id]                   → DS: Prepare & Upload detail

/approvals                      → DO: Approvals Inbox
/approvals/[id]                 → DO: Approval Detail

/my-department                  → DO: My Department

/dpo                            → DPO: Org Request List
/dpo/[id]                       → DPO: Request Detail + PDPL Review
/dpo/workflows                  → DPO: Workflow Editor
/dpo/templates                  → DPO: Request Templates
/dpo/audit                      → DPO: Audit Trail
/dpo/recipients                 → DPO: External Recipients

/admin/departments              → OA: Departments
/admin/users                    → OA: Users
/admin/users/[userId]/delegation → OA: Set Delegation on Behalf
/admin/connections              → OA: Database Connections
/admin/holidays                 → OA: Business Holidays
/admin/retention                → OA: Retention Policy

/platform/organisations         → PA: Organisations list
/platform/onboard               → PA: Onboard Company wizard

/pickup/[token]                 → External: Accept Invitation
```

## Complete Folder Structure
```
src/
├── app/
│   ├── (auth)/                 ← Login screens (no sidebar)
│   │   └── login/
│   ├── (dashboard)/            ← Feature screens (with sidebar)
│   │   ├── layout.tsx          ← Sidebar + main content wrapper
│   │   ├── admin/              ← Org Admin screens
│   │   ├── approvals/          ← Data Owner approvals
│   │   ├── data-sharing/       ← Data Steward requests
│   │   ├── dpo/                ← DPO screens
│   │   ├── my-department/      ← Data Owner department mgmt
│   │   ├── platform/           ← Platform Admin screens
│   │   └── prepare/            ← Data Steward prepare & upload
│   ├── (shell)/                ← Profile/Notifications/Delegation (topbar only)
│   ├── pickup/                 ← External recipient portal
│   └── layout.tsx              ← Root layout with providers
│
├── components/
│   ├── features/               ← Feature-specific components
│   │   ├── data-sharing/       ← DS, DO, DPO shared DS components
│   │   ├── notifications/
│   │   └── profile/
│   ├── shared/                 ← Used by all roles
│   │   ├── AppShell/
│   │   │   ├── Sidebar.tsx     ← Role-based navigation
│   │   │   ├── Topbar.tsx      ← Notifications bell + user avatar
│   │   │   └── NavItem.tsx     ← Single nav item with active state
│   │   └── [shared components]
│   └── ui/                     ← shadcn/ui primitives
│
├── lib/
│   ├── api/
│   │   ├── client.ts           ← Axios instance, interceptors, wrappers
│   │   ├── platform/           ← Auth, users, groups, notifications, audit
│   │   └── products/
│   │       └── data-sharing/   ← Requests, steps, files, connections, etc.
│   ├── hooks/
│   │   ├── data-sharing/       ← useRequests, useRequestDetail, etc.
│   │   ├── platform/           ← useAuth, useGroups, useNotifications
│   │   └── useRoleGuard.ts
│   ├── store/
│   │   ├── auth.store.ts       ← Zustand: user, tokens, isAuthenticated
│   │   ├── ui.store.ts         ← Zustand: sidebarOpen, currentFeature
│   │   └── new-request.store.ts ← Zustand: multi-step form state
│   ├── types/
│   │   ├── common.types.ts
│   │   ├── data-sharing/
│   │   └── platform/
│   └── utils/
│       ├── constants.ts
│       ├── formatters.ts
│       └── validators.ts
│
└── styles/
    └── globals.css
```

## Data Flow
```
Component
  → useQuery / useMutation  (TanStack Query)
    → Hook (src/lib/hooks/)
      → API function (src/lib/api/)
        → apiClient (src/lib/api/client.ts)
          → Backend (http://localhost:8000)
```

## Auth Flow
```
/login form submit
  → POST /api/v1/platform/auth/login
    → success: store tokens in auth.store (Zustand)
      → redirect to /
    → 401 on any subsequent request
      → POST /api/v1/platform/auth/refresh
        → success: retry original request
        → fail: clear auth.store → redirect to /login
```

## Role System
| Role value | Guard | Main Routes |
|------------|-------|-------------|
| requester | ['requester', 'platform_admin'] | /data-sharing/*, /prepare/* |
| data_owner | ['data_owner', 'platform_admin'] | /approvals/*, /my-department/* |
| dpo | ['dpo', 'platform_admin'] | /dpo/* |
| org_admin | ['org_admin', 'platform_admin'] | /admin/* |
| platform_admin | ['platform_admin'] | /platform/* |

Role is resolved from `user.product_role` (data_owner, dpo, requester) and `user.platform_role` (org_admin, platform_admin). Platform role takes precedence.

## State Management
- **Server state**: TanStack Query — all API data, caching, background refetching
- **Auth state**: Zustand `auth.store` — tokens, user profile, isAuthenticated
- **UI state**: Zustand `ui.store` — sidebar, feature context
- **Form state**: Zustand `new-request.store` — multi-step form draft

## API Layer
```
src/lib/api/
├── client.ts                       ← Single Axios instance
│                                      Bearer token interceptor
│                                      401 → auto-refresh → retry
│                                      Exports: get/post/put/patch/del wrappers
├── platform/
│   ├── auth.api.ts                 ← login, refresh, logout
│   ├── users.api.ts                ← me, list users, update
│   ├── groups.api.ts               ← departments, members CRUD
│   ├── notifications.api.ts        ← list, mark-read
│   ├── audit.api.ts                ← audit trail, export
│   └── delegation.api.ts           ← setMyDelegation, clearMyDelegation, history
└── products/
    └── data-sharing/
        ├── requests.api.ts         ← CRUD, submit, cancel
        ├── steps.api.ts            ← act on step (approve/reject/changes)
        ├── files.api.ts            ← initiate, upload PUT, download URL, delete
        ├── connections.api.ts      ← DB connections CRUD + test
        ├── schemas.api.ts          ← schema browse, preview
        └── workflows.api.ts        ← workflow templates CRUD
```

## Design Tokens (from globals.css)
| Token | Value | Usage |
|-------|-------|-------|
| --brand | #D76736 | Primary orange — buttons, active nav, links |
| --auth-bg | #FFFFF9 | Page background |
| --auth-card | #FFFFFF | Card/panel background |
| --auth-border | #EEEEEE | Borders, dividers |
| --auth-text | #1A1A1A | Primary text |
| --auth-text-muted | #515157 | Secondary text |
| --auth-text-subtle | #9E9E9E | Tertiary text |
| --auth-text-placeholder | #BABABA | Input placeholders |

## Adding a New Feature
1. Add types: `src/lib/types/[feature]/`
2. Add API: `src/lib/api/products/[feature]/`
3. Add hooks: `src/lib/hooks/[feature]/`
4. Add components: `src/components/features/[feature]/`
5. Add pages: `src/app/(dashboard)/[feature]/`
6. Add sidebar items in `Sidebar.tsx` for correct roles only
7. Add `useRoleGuard` to every page
8. Add rows to `CHECKLIST.md`

## Environment Variables
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Datarix
```
