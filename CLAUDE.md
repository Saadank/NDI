Read the Pencil design file to understand the design system (colors, 
typography, spacing), then scaffold the complete Next.js frontend 
structure for the Datarix project. Do NOT build any screens yet — 
only set up the foundation.

## Tasks:

1. Run: npx create-next-app@latest . --typescript --tailwind --app --src-dir --eslint
   (we are already inside ~/Desktop/Datarix-Frontend)

2. Install dependencies:
   npm install @tanstack/react-query @tanstack/react-query-devtools
   npm install axios zustand
   npm install react-hook-form zod @hookform/resolvers
   npm install next-intl
   npx shadcn@latest init
   npx shadcn@latest add button input label dialog select badge 
       toast tabs separator card avatar dropdown-menu skeleton
       alert progress sheet tooltip

3. Read the Pencil design file using MCP tools and extract:
   - Primary color, background color, border color, text colors
   - Font family and sizes
   - Border radius values
   - Any design tokens or variables defined

4. Create this EXACT folder structure (empty files with correct exports):

src/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   ├── login/sso/page.tsx
│   │   ├── login/totp/page.tsx
│   │   └── login/forgot-password/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   └── data-sharing/
│   │       ├── page.tsx
│   │       ├── new/page.tsx
│   │       └── [id]/page.tsx
│   ├── pickup/
│   │   └── [token]/page.tsx
│   └── middleware.ts
│
├── components/
│   ├── shared/
│   │   ├── AppShell/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Topbar.tsx
│   │   │   └── NavItem.tsx
│   │   ├── DataTable/
│   │   │   ├── DataTable.tsx
│   │   │   └── DataTable.types.ts
│   │   ├── StepWizard/
│   │   │   ├── StepWizard.tsx
│   │   │   ├── StepIndicator.tsx
│   │   │   └── StepWizard.types.ts
│   │   ├── StatusBadge.tsx
│   │   ├── PageHeader.tsx
│   │   ├── ConfirmDialog.tsx
│   │   ├── EmptyState.tsx
│   │   └── ErrorBoundary.tsx
│   └── features/
│       ├── data-sharing/
│       │   ├── RequestsTable.tsx
│       │   ├── RequestStatusBadge.tsx
│       │   ├── RequestDetail/
│       │   │   ├── RequestDetail.tsx
│       │   │   ├── WorkflowTimeline.tsx
│       │   │   └── FileAttachments.tsx
│       │   └── NewRequest/
│       │       ├── Step1_BasicInfo.tsx
│       │       ├── Step2_DataSelection.tsx
│       │       └── Step3_Review.tsx
│       ├── ndi/
│       │   └── .gitkeep
│       ├── data-quality/
│       │   └── .gitkeep
│       └── dsr/
│           └── .gitkeep
│
├── lib/
│   ├── api/
│   │   ├── client.ts
│   │   ├── platform/
│   │   │   ├── auth.api.ts
│   │   │   ├── users.api.ts
│   │   │   ├── notifications.api.ts
│   │   │   └── audit.api.ts
│   │   └── products/
│   │       └── data-sharing/
│   │           ├── requests.api.ts
│   │           ├── steps.api.ts
│   │           ├── files.api.ts
│   │           ├── connections.api.ts
│   │           ├── schemas.api.ts
│   │           └── workflows.api.ts
│   ├── hooks/
│   │   ├── platform/
│   │   │   ├── useAuth.ts
│   │   │   └── useNotifications.ts
│   │   └── data-sharing/
│   │       ├── useRequests.ts
│   │       ├── useRequestDetail.ts
│   │       ├── useApprovalSteps.ts
│   │       ├── useFiles.ts
│   │       ├── useConnections.ts
│   │       └── useSchemas.ts
│   ├── types/
│   │   ├── platform/
│   │   │   ├── auth.types.ts
│   │   │   └── user.types.ts
│   │   ├── data-sharing/
│   │   │   ├── request.types.ts
│   │   │   ├── step.types.ts
│   │   │   ├── file.types.ts
│   │   │   └── connection.types.ts
│   │   └── common.types.ts
│   ├── store/
│   │   ├── auth.store.ts
│   │   └── ui.store.ts
│   └── utils/
│       ├── formatters.ts
│       ├── validators.ts
│       └── constants.ts
│
└── styles/
    └── globals.css

5. Implement these foundation files with REAL content (not placeholders):

### .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=Datarix

### tailwind.config.ts
Extract actual values from Pencil design variables and set:
- colors.primary → main brand color from Pencil
- colors.sidebar → sidebar background color
- All other design tokens found in Pencil

### src/lib/types/common.types.ts
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
}
export interface ApiError {
  detail: string
  status: number
}

### src/lib/types/platform/auth.types.ts
export interface LoginRequest { username: string; password: string }
export interface AuthTokens { access_token: string; refresh_token: string }
export interface LoginResponse extends AuthTokens { user: CurrentUser }
export interface CurrentUser {
  id: number
  email: string
  first_name: string
  last_name: string
  roles: string[]
  tenant_id: number
}

### src/lib/types/data-sharing/request.types.ts
export type SharingType = 'internal' | 'external'
export type DataType = 'file' | 'structured'
export type SelectionMode = 'tables' | 'query'
export type DeliveryChannel = 'portal' | 'email' | 'api'
export type RequestStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'cancelled'
export interface ShareRequest {
  id: number
  title: string
  purpose: string
  legal_basis: string
  sharing_type: SharingType
  data_classification: string
  personal_data_involved: boolean
  estimated_data_subjects: number
  data_subject_categories: string[]
  source_description: string
  receiving_tenant_id?: number
  receiver_group_id?: number
  dpia_confirmed: boolean
  data_type: DataType
  connection_id?: number
  selection_mode?: SelectionMode
  selected_items?: string[]
  custom_sql?: string
  delivery_channel: DeliveryChannel
  status: RequestStatus
  created_at: string
  updated_at: string
}
export type CreateShareRequestBody = Omit<ShareRequest, 'id' | 'status' | 'created_at' | 'updated_at'>

### src/lib/types/data-sharing/step.types.ts
export type StepStatus = 'pending' | 'approved' | 'rejected' | 'changes_requested'
export interface WorkflowStep {
  id: number
  request_id: number
  order: number
  assignee_id: number
  assignee_name: string
  status: StepStatus
  comment?: string
  can_act: boolean
  acted_at?: string
}

### src/lib/api/client.ts
- Single Axios instance reading NEXT_PUBLIC_API_URL
- Request interceptor: attach Bearer token from auth.store
- Response interceptor: on 401 → auto-refresh using POST /api/v1/platform/auth/refresh
- On refresh failure: clear auth.store + redirect to /login
- Export: apiClient (default), and typed get/post/put/delete/patch wrappers

### src/lib/store/auth.store.ts
Zustand store with:
- state: user (CurrentUser | null), accessToken, refreshToken, isAuthenticated
- actions: setTokens, setUser, logout, initialize

### src/lib/store/ui.store.ts
Zustand store with:
- state: sidebarOpen (boolean), currentFeature (string)
- actions: toggleSidebar, setCurrentFeature

### src/lib/api/platform/auth.api.ts
import { apiClient } from '../client'
- login(body: LoginRequest): Promise<LoginResponse>
- refresh(refreshToken: string): Promise<AuthTokens>
- logout(refreshToken: string): Promise<{ success: boolean }>

### src/lib/api/products/data-sharing/requests.api.ts
- getRequests(params: { page?: number; limit?: number; status?: string }): Promise<PaginatedResponse<ShareRequest>>
- createRequest(body: CreateShareRequestBody): Promise<ShareRequest>
- getRequest(id: number): Promise<ShareRequest>
- submitRequest(id: number): Promise<ShareRequest>
- cancelRequest(id: number): Promise<ShareRequest>

### src/lib/utils/constants.ts
export const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = { ... }
export const REQUEST_STATUS_COLORS: Record<RequestStatus, string> = { ... }
export const FEATURES = ['data-sharing', 'ndi', 'data-quality', 'dsr'] as const
export type Feature = typeof FEATURES[number]

### src/middleware.ts
Protect all (dashboard) routes — redirect to /login if no valid token in store

6. After creating all files, run:
   npx tsc --noEmit
   
   Fix ALL TypeScript errors before finishing.

7. Final check — confirm:
   ✓ npx tsc --noEmit passes with 0 errors
   ✓ All folders exist
   ✓ No any types used
   ✓ All API functions are typed
   ✓ Tailwind colors match Pencil design tokens