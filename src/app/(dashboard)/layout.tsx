import { Sidebar } from "@/components/shared/AppShell/Sidebar";
import { Topbar } from "@/components/shared/AppShell/Topbar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-auth-bg">
      {/* Identity widget + logout sit in the Topbar so they're visible on
          every dashboard page across all 5 roles. */}
      <Topbar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">{children}</div>
      </div>
    </div>
  );
}
