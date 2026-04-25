import { Breadcrumb } from "@/components/shared/Breadcrumb";
import { FilterChip } from "@/components/features/notifications/FilterChip";
import { NotificationsEmpty } from "@/components/features/notifications/NotificationsEmpty";
import {
  NotificationRow,
  type NotificationItem,
} from "@/components/features/notifications/NotificationRow";

const demoNotifications: NotificationItem[] = [
  {
    id: "1",
    title: "Approval request · Fatima Al-Zahrani",
    subtitle: "Dataset access: HR Payroll Q4 — Review →",
    time: "2 min ago",
    unread: true,
  },
  {
    id: "2",
    title: "Request approved · HR Customer PII Export",
    subtitle: "Approved by Khaled Al-Mutairi",
    time: "1 hr ago",
    unread: false,
  },
  {
    id: "3",
    title: "SLA expiring soon · Finance Report Q3",
    subtitle: "Breach at 18:00 today — action required",
    time: "3 hrs ago",
    unread: true,
  },
  {
    id: "4",
    title: "Data ready to download",
    subtitle: "Marketing Survey 2024 · 2.3 GB — Download →",
    time: "5 hrs ago",
    unread: true,
  },
  {
    id: "5",
    title: "Approval authority delegated to you",
    subtitle: "By Khaled Al-Mutairi · Active until 1 Dec 2024",
    time: "Yesterday",
    unread: false,
  },
  {
    id: "6",
    title: "File deletion in 48 hours",
    subtitle: "Customer PII Export 2023 · Retention ends 24 Nov",
    time: "2 days ago",
    unread: false,
  },
];

const slaNotifications: NotificationItem[] = [
  {
    id: "s1",
    title: "SLA expiring soon · Finance Report Q3",
    subtitle: "Data Sharing · SLA expires in 2 hours",
    time: "1h ago",
    unread: true,
  },
  {
    id: "s2",
    title: "SLA expiring soon · HR Data Access Request",
    subtitle: "Data Sharing · SLA expires in 6 hours",
    time: "3h ago",
    unread: true,
  },
  {
    id: "s3",
    title: "SLA breached · Vendor Audit Export",
    subtitle: "Data Sharing · SLA deadline passed 24 Nov",
    time: "Yesterday",
    unread: false,
  },
];

interface NotificationsPageProps {
  searchParams: Promise<{ view?: string }>;
}

export default async function NotificationsPage({
  searchParams,
}: NotificationsPageProps) {
  const { view } = await searchParams;
  const isEmpty = view === "empty";
  const isFiltered = view === "filter";

  const items = isEmpty
    ? []
    : isFiltered
      ? slaNotifications
      : demoNotifications;

  return (
    <main className="flex-1 flex flex-col gap-5 px-[240px] py-8">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: "Notifications" },
        ]}
      />

      {isEmpty || isFiltered ? (
        <h1 className="text-lg font-bold text-auth-text">Notifications</h1>
      ) : (
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-bold text-auth-text">Notifications</h1>
          <button
            type="button"
            className="text-[13px] font-normal text-brand hover:underline"
          >
            Mark all read
          </button>
        </div>
      )}

      {isFiltered && (
        <div className="flex items-center gap-2">
          <FilterChip label="SLA Warning" onRemoveHref="/notifications" />
        </div>
      )}

      <div className="flex-1 rounded-lg border border-auth-border bg-white overflow-hidden">
        {items.length === 0 ? (
          <NotificationsEmpty />
        ) : (
          items.map((n, i) => (
            <NotificationRow
              key={n.id}
              item={n}
              last={i === items.length - 1}
            />
          ))
        )}
      </div>
    </main>
  );
}
