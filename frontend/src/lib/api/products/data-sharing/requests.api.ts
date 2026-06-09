import { get, patch, post } from "@/lib/api/client";
import type { PaginatedResponse } from "@/lib/types/common.types";
import type {
  CreateShareRequestBody,
  ShareRequest,
  UpdateShareRequestBody,
} from "@/lib/types/data-sharing/request.types";

// Backend router is mounted at `/requests` and exposes routes at `/`. With
// trailing slashes here we avoid Starlette's 307 redirect dance, which
// browsers/axios handle but in some flows can drop the POST body.
const BASE = "/api/v1/products/data-sharing/requests";

export function getRequests(params: {
  page?: number;
  limit?: number;
  status?: string;
}): Promise<PaginatedResponse<ShareRequest>> {
  return get<PaginatedResponse<ShareRequest>>(`${BASE}/`, { params });
}

export function createRequest(
  body: CreateShareRequestBody,
): Promise<ShareRequest> {
  return post<ShareRequest, CreateShareRequestBody>(`${BASE}/`, body);
}

export function getRequest(id: string): Promise<ShareRequest> {
  return get<ShareRequest>(`${BASE}/${id}`);
}

export function updateRequest(
  id: string,
  body: UpdateShareRequestBody,
): Promise<ShareRequest> {
  return patch<ShareRequest, UpdateShareRequestBody>(`${BASE}/${id}`, body);
}

export function submitRequest(id: string): Promise<ShareRequest> {
  return post<ShareRequest>(`${BASE}/${id}/submit`);
}

export function cancelRequest(id: string): Promise<ShareRequest> {
  return post<ShareRequest>(`${BASE}/${id}/cancel`);
}
