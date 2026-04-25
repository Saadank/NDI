import { Bell } from "lucide-react";

export function NotificationsEmpty() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 py-24">
      <Bell className="h-9 w-9" style={{ color: "#E8E8E8" }} strokeWidth={1.5} />
      <p className="text-base font-medium" style={{ color: "#515157" }}>
        You&apos;re all caught up
      </p>
      <p className="text-sm font-normal text-auth-text-subtle">
        New notifications will appear here.
      </p>
    </div>
  );
}
