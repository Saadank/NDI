import { cn } from "@/lib/utils";

export interface NotificationItem {
  id: string;
  title: string;
  subtitle: string;
  time: string;
  unread: boolean;
}

interface NotificationRowProps {
  item: NotificationItem;
  last?: boolean;
}

export function NotificationRow({ item, last }: NotificationRowProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 px-5 py-4",
        !last && "border-b border-auth-border",
        item.unread ? "bg-auth-card" : "bg-white",
      )}
    >
      <span
        className={cn(
          "h-2 w-2 shrink-0 rounded-[2px]",
          item.unread ? "bg-brand" : "bg-auth-border",
        )}
        aria-hidden
      />
      <div className="flex flex-1 flex-col gap-[3px] min-w-0">
        <p
          className={cn(
            "truncate text-[13px]",
            item.unread
              ? "font-semibold text-auth-text"
              : "font-medium text-[#515157]",
          )}
        >
          {item.title}
        </p>
        <p className="truncate text-[11px] font-normal text-auth-text-subtle">
          {item.subtitle}
        </p>
      </div>
      <span className="shrink-0 text-[11px] font-normal text-auth-text-placeholder">
        {item.time}
      </span>
    </div>
  );
}
