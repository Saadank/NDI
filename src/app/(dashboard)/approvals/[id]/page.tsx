import { ApprovalDetail } from "@/components/features/data-sharing/Approvals/ApprovalDetail";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ApprovalDetailPage({ params }: Props) {
  const { id } = await params;
  return <ApprovalDetail id={id} />;
}
