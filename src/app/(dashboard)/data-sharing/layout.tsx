import { DataStewardSidebar } from "@/components/features/data-sharing/DataStewardSidebar";

export default function DataSharingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-1 overflow-hidden">
      <DataStewardSidebar />
      {children}
    </div>
  );
}
