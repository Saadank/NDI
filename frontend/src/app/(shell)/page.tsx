import Link from "next/link";
import {
  ArrowRight,
  Share2,
  Activity,
  ShieldCheck,
  UserCheck,
  type LucideIcon,
} from "lucide-react";

interface ProductCard {
  title: string;
  href: string;
  icon: LucideIcon;
}

const products: ProductCard[] = [
  { title: "Data Sharing Platform", href: "/data-sharing", icon: Share2 },
  { title: "NDMO Compliance", href: "/ndmo-compliance", icon: ShieldCheck },
  { title: "Data Quality Profiling", href: "/data-quality", icon: Activity },
  { title: "Data Subject Rights (DSR)", href: "/dsr", icon: UserCheck },
];

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
