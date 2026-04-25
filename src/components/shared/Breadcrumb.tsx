import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
}

interface BreadcrumbProps {
  items: Crumb[];
  className?: string;
}

export function Breadcrumb({ items, className }: BreadcrumbProps) {
  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center gap-[6px] text-xs", className)}
    >
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <span key={i} className="flex items-center gap-[6px]">
            {item.href && !isLast ? (
              <Link
                href={item.href}
                className="font-normal text-auth-text-subtle hover:text-auth-text-muted"
              >
                {item.label}
              </Link>
            ) : (
              <span
                className={cn(
                  "font-normal text-auth-text-subtle",
                  isLast && "font-medium text-[#515157]",
                )}
              >
                {item.label}
              </span>
            )}
            {!isLast && (
              <ChevronRight
                className="h-3 w-3"
                style={{ color: "#BABABA" }}
                aria-hidden
              />
            )}
          </span>
        );
      })}
    </nav>
  );
}
