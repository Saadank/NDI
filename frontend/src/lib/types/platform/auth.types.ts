export interface LoginRequest {
  username: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

// The backend's authentication_service.login() returns numeric ids for
// id/tenant_id/group_id (they're integer surrogate keys in t_users / t_tenants
// / t_groups). Earlier this type used `string`, which kept tsc happy but
// produced subtle runtime mismatches whenever we compared receiver group ids.
// All optional fields below match the backend's /users/me response, which can
// omit `first_name`/`last_name` for invited-but-not-yet-completed users and may
// return `email` as null only in degenerate states. Treat every text field as
// nullable so the profile UI never crashes on `user.email[0]`.
export interface CurrentUser {
  // Backend returns `user_id` from /users/me + login (its AuthUser
  // Pydantic model uses that field name). The auth store normalizes
  // to `id` in `setUser` and `onRehydrateStorage` so every consumer
  // can read `user.id` unconditionally. Both keys are typed here so
  // older persisted state (which only has `user_id`) doesn't trip
  // TypeScript after a `localStorage` rehydrate.
  id: number;
  user_id?: number;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  platform_role: string;
  product_role: string | null;
  group_id: number | null;
  tenant_id: number;
}

export interface LoginResponse extends AuthTokens {
  user: CurrentUser;
  expires_in: number;
  token_type: string;
}
