import { ApprovalDetail } from "@/components/features/data-sharing/Approvals/ApprovalDetail";

interface Props {
  params: Promise<{ id: string }>;
}

// DPO request detail reuses the same Approval/Decision UI as Data Owners —
// the backend's `can_act` flag on each step decides whether the DPO sees
// action buttons.
export default async function DpoRequestDetailPage({ params }: Props) {
  const { id } = await params;
  return <ApprovalDetail id={id} />;
}
