import { IncomingDetail } from "@/components/features/data-sharing/Approvals/IncomingDetail";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function IncomingApprovalPage({ params }: Props) {
  const { id } = await params;
  return <IncomingDetail id={id} />;
}
