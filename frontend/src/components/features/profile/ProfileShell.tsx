import { Breadcrumb } from "@/components/shared/Breadcrumb";

interface ProfileShellProps {
  title?: string;
  currentLabel?: string;
  children: React.ReactNode;
}

export function ProfileShell({
  title = "User Profile",
  currentLabel = "Profile",
  children,
}: ProfileShellProps) {
  return (
    <main className="flex-1 flex flex-col gap-6 px-[240px] py-10">
      <Breadcrumb
        items={[
          { label: "Products", href: "/" },
          { label: currentLabel },
        ]}
      />
      <h1 className="text-lg font-bold text-auth-text">{title}</h1>
      {children}
    </main>
  );
}

export function ProfileCard({ children }: { children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-7 rounded-lg border border-auth-border bg-white p-8">
      {children}
    </section>
  );
}

export function ProfileDivider() {
  return <div className="h-px w-full bg-auth-border" />;
}

interface IdentityProps {
  initials: string;
  name: string;
  email: string;
}

export function Identity({ initials, name, email }: IdentityProps) {
  return (
    <div className="flex items-center gap-4">
      <div
        className="flex h-[60px] w-[60px] items-center justify-center rounded-full text-lg font-bold text-brand"
        style={{ backgroundColor: "rgba(215, 103, 54, 0.15)" }}
      >
        {initials}
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-base font-semibold text-auth-text">{name}</p>
        <p className="text-[13px] font-normal" style={{ color: "#616161" }}>
          {email}
        </p>
      </div>
    </div>
  );
}

interface ProfileFieldProps {
  label: string;
  children: React.ReactNode;
}

export function ProfileField({ label, children }: ProfileFieldProps) {
  return (
    <div className="flex flex-col gap-[6px]">
      <label className="text-xs font-medium" style={{ color: "#616161" }}>
        {label}
      </label>
      {children}
    </div>
  );
}

interface ProfileLinkRowProps {
  label: string;
  href: string;
  last?: boolean;
}

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export function ProfileLinkRow({ label, href, last }: ProfileLinkRowProps) {
  return (
    <Link
      href={href}
      className={cn(
        "flex h-[52px] items-center justify-between",
        !last && "border-b border-auth-border",
      )}
    >
      <span className="text-sm font-normal text-auth-text">{label}</span>
      <ChevronRight className="h-4 w-4" style={{ color: "#BABABA" }} />
    </Link>
  );
}
