import { post } from "@/lib/api/client";
import type {
  AuthTokens,
  LoginRequest,
  LoginResponse,
} from "@/lib/types/platform/auth.types";

const BASE = "/api/v1/platform/auth";

export function login(body: LoginRequest): Promise<LoginResponse> {
  return post<LoginResponse, LoginRequest>(`${BASE}/login`, body);
}

export function refresh(refreshToken: string): Promise<AuthTokens> {
  return post<AuthTokens, { refresh_token: string }>(`${BASE}/refresh`, {
    refresh_token: refreshToken,
  });
}

export function logout(
  refreshToken: string,
): Promise<{ success: boolean }> {
  return post<{ success: boolean }, { refresh_token: string }>(
    `${BASE}/logout`,
    { refresh_token: refreshToken },
  );
}
