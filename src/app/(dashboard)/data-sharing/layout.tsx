// The dashboard's root layout (`src/app/(dashboard)/layout.tsx`) already
// renders the global role-aware Sidebar. This nested layout previously
// rendered a second `DataStewardSidebar` which produced two stacked
// sidebars on every /data-sharing/* page. We collapse it to a passthrough
// so children render directly inside the dashboard frame.
export default function DataSharingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
