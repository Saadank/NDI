import { Topbar } from "@/components/shared/AppShell/Topbar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-auth-bg">
      <Topbar />
      {children}
    </div>
  );
}
