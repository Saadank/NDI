"use client";

import { useAuthStore } from "@/lib/store/auth.store";

interface RoleBadgeProps {
  /** Override label — if omitted, derived from the auth store */
  label?: string;
}

function deriveLabel(
  productRole: string | null,
  platformRole: string | null,
  groupName?: string | null,
): string {
  if (platformRole === "platform_admin") return "Platform Admin";
  if (platformRole === "org_admin") return "Org Admin";
  const roleLabel =
    productRole === "data_owner"
      ? "Data Owner"
      : productRole === "dpo"
        ? "DPO"
        : "Data Steward";
  return groupName ? `${roleLabel} · ${groupName}` : roleLabel;
}

export function RoleBadge({ label }: RoleBadgeProps) {
  const user = useAuthStore((s) => s.user);

  const text =
    label ??
    deriveLabel(
      user?.product_role ?? null,
      user?.platform_role ?? null,
      null,
    );

  return (
    <span
      className="rounded px-2.5 py-1 text-[13px] font-medium"
      style={{ backgroundColor: "#FFF5F0", color: "#D76736" }}
    >
      {text}
    </span>
  );
}
