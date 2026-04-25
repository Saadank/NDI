import type { CurrentUser } from "./auth.types";

export type User = CurrentUser;

export interface UserListItem {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  is_active: boolean;
}
