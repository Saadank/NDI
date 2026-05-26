import { SpecDetailPage } from "@/components/features/ndmo-compliance/Specs/SpecDetailPage";

export default async function NdmoSpecDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SpecDetailPage id={id} />;
}
