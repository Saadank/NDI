import { RecipientDetail } from "@/components/features/data-sharing/Dpo/RecipientDetail";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function RecipientDetailPage({ params }: Props) {
  const { id } = await params;
  return <RecipientDetail id={id} />;
}
