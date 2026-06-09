"use client";

import Link from "next/link";
import {
  ArrowRight,
  Share2,
  Activity,
  ShieldCheck,
  UserCheck,
  type LucideIcon,
} from "lucide-react";

import { useAuthStore } from "@/lib/store/auth.store";

interface ProductCard {
  title: string;
  href: string;
  icon: LucideIcon;
}

// The Data Sharing Platform is one product, but each role's home inside it is
// a different page — the one that appears as the first item in that role's
// sidebar.  Sending a role to a page that ISN'T in their sidebar (e.g. a DPO
// to /data-sharing "My Requests") strands them with no nav item to return to.
// Keep this in sync with PRIMARY_NAV in AppShell/Sidebar.tsx.
function dataSharingHome(
  productRole: string | null,
  platformRole: string | null,
): string {
  if (platformRole === "platform_admin") return "/platform/organisations";
  if (platformRole === "org_admin") return "/dpo";
  if (productRole === "data_owner") return "/approvals";
  if (productRole === "dpo") return "/dpo";
  return "/data-sharing"; // requester
}

function buildProducts(dsHref: string): ProductCard[] {
  return [
    { title: "Data Sharing Platform", href: dsHref, icon: Share2 },
    { title: "NDMO Compliance", href: "/ndmo-compliance", icon: ShieldCheck },
    { title: "Data Quality Profiling", href: "/data-quality", icon: Activity },
    { title: "Data Subject Rights (DSR)", href: "/dsr", icon: UserCheck },
  ];
}

function ProductTile({ title, href, icon: Icon }: ProductCard) {
  return (
    <Link
      href={href}
      className="group flex h-[220px] w-[320px] flex-col gap-4 rounded-xl border border-auth-border bg-auth-card p-7 shadow-[0_4px_20px_0_rgba(0,0,0,0.07)] transition-transform hover:-translate-y-0.5"
    >
      <div className="flex w-full items-center justify-between">
        <div
          className="flex h-12 w-12 items-center justify-center rounded-[10px]"
          style={{ backgroundColor: "rgba(215, 103, 54, 0.15)" }}
        >
          <Icon className="h-5 w-5 text-brand" />
        </div>
        <ArrowRight className="h-5 w-5 text-brand transition-transform group-hover:translate-x-0.5" />
      </div>
      <h2 className="mt-auto text-[17px] font-bold leading-tight text-auth-text">
        {title}
      </h2>
    </Link>
  );
}

export default function ProductPortalPage() {
  const user = useAuthStore((s) => s.user);
  const products = buildProducts(
    dataSharingHome(user?.product_role ?? null, user?.platform_role ?? null),
  );

  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-5 px-8 py-10">
      <span className="text-[13px] font-medium uppercase tracking-[1px] text-auth-text-subtle">
        Products
      </span>
      <div className="grid grid-cols-2 gap-6">
        {products.map((p) => (
          <ProductTile key={p.title} {...p} />
        ))}
      </div>
    </main>
  );
}
