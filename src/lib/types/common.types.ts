export interface Pagination {
  total_pages: number;
  total?: number;
  next_page: number | null;
  previous_page: number | null;
  page: number;
  limit: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface ApiError {
  detail: string;
  status: number;
}
