import { PrepareAndUpload } from "@/components/features/data-sharing/Prepare/PrepareAndUpload";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PrepareAndUploadPage({ params }: Props) {
  const { id } = await params;
  return <PrepareAndUpload id={id} />;
}
