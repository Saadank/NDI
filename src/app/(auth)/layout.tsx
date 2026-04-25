import { Logo } from "@/components/shared/Logo";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 bg-auth-bg px-6 py-12">
      <Logo height={28} />
      {children}
    </div>
  );
}
