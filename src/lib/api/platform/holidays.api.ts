import { del, get, post } from "@/lib/api/client";

const BASE = "/api/v1/platform/holidays/";

// Backend row shape (t_business_holidays):
//   id (int), tenant_id (int), holiday_date (YYYY-MM-DD), name, name_ar,
//   created_by (int), created_at (ISO).
// The backend does NOT yet store an `is_recurring` flag. The Pencil design
// shows a toggle, so we keep it in the UI but it's a no-op until the backend
// adds the column.
export interface HolidayRecord {
  id: number;
  tenant_id: number;
  holiday_date: string;
  name: string;
  name_ar: string | null;
  created_by: number;
  created_at: string;
}

export interface CreateHolidayBody {
  holiday_date: string; // YYYY-MM-DD
  name: string;
  name_ar?: string;
}

export function listHolidays(year?: number): Promise<HolidayRecord[]> {
  return get<HolidayRecord[]>(BASE, year ? { params: { year } } : undefined);
}

export function createHoliday(body: CreateHolidayBody): Promise<HolidayRecord> {
  return post<HolidayRecord, CreateHolidayBody>(BASE, body);
}

export function deleteHoliday(holidayId: number): Promise<{ deleted: number }> {
  return del<{ deleted: number }>(`${BASE}${holidayId}`);
}
