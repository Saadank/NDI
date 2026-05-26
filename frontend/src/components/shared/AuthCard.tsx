import { cn } from "@/lib/utils";

interface AuthCardProps {
  children: React.ReactNode;
  className?: string;
}

export function AuthCard({ children, className }: AuthCardProps) {
  return (
    <div
      className={cn(
        "w-[440px] max-w-full rounded-xl border border-auth-border bg-auth-card p-10",
        "shadow-[0_8px_32px_0_rgba(0,0,0,0.07)]",
        "flex flex-col gap-7",
        className,
      )}
    >
      {children}
    </div>
  );
}

interface AuthCardHeaderProps {
  title: string;
  description: string;
  centered?: boolean;
}

export function AuthCardHeader({
  title,
  description,
  centered,
}: AuthCardHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2",
        centered && "items-center text-center",
      )}
    >
      <h1 className="text-[22px] font-bold text-auth-text leading-tight">
        {title}
      </h1>
      <p className="text-sm font-normal leading-[1.5] text-auth-text-muted">
        {description}
      </p>
    </div>
  );
}
