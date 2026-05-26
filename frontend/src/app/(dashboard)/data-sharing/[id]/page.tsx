import { RequestDetail } from "@/components/features/data-sharing/RequestDetail/RequestDetail";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function DataSharingRequestDetailPage({ params }: Props) {
  const { id } = await params;
  return <RequestDetail id={id} />;
}
