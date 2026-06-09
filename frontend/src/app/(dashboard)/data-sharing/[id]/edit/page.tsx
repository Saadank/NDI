import { EditRequest } from "@/components/features/data-sharing/RequestDetail/EditRequest";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function EditDataSharingRequestPage({ params }: Props) {
  const { id } = await params;
  return <EditRequest id={id} />;
}
