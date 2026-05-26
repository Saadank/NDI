// Shape returned by GET /api/v1/platform/groups/.
export interface Group {
  id: number;
  tenant_id: number;
  name: string;
  name_ar: string | null;
  slug: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  data_owner_id: number | null;
  data_owner_name: string | null;
  member_count?: number;
}
