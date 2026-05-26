export function OrDivider() {
  return (
    <div className="flex items-center gap-3">
      <div className="h-px flex-1 bg-auth-border" />
      <span className="text-xs font-normal text-auth-text-subtle">or</span>
      <div className="h-px flex-1 bg-auth-border" />
    </div>
  );
}
