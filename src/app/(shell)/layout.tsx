import { Topbar } from "@/components/shared/AppShell/Topbar";

export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-auth-bg">
      <Topbar />
      <div className="flex flex-1 flex-col">{children}</div>
    </div>
  );
}
