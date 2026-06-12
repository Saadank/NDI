import { TermDetailPage } from "@/components/features/ndmo-compliance/Glossary/TermDetail/TermDetailPage";

export default async function TermDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TermDetailPage termId={id} />;
}
