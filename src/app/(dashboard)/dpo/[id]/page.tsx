import { DpoRequestDetail } from "@/components/features/data-sharing/Dpo/DpoRequestDetail";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function DpoRequestDetailPage({ params }: Props) {
  const { id } = await params;
  return <DpoRequestDetail id={id} />;
}
