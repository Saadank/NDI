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
export interface CurrentUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
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
