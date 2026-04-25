import Link from "next/link";
import { ListFilter, X } from "lucide-react";

interface FilterChipProps {
  label: string;
  onRemoveHref: string;
}

export function FilterChip({ label, onRemoveHref }: FilterChipProps) {
  return (
    <span className="inline-flex h-8 items-center gap-[6px] rounded-2xl border border-brand bg-brand px-3 text-white">
      <ListFilter className="h-3 w-3" />
      <span className="text-xs font-medium">{label}</span>
      <Link
        href={onRemoveHref}
        aria-label={`Remove ${label} filter`}
        className="flex h-3 w-3 items-center justify-center"
      >
        <X className="h-3 w-3" />
      </Link>
    </span>
  );
}
