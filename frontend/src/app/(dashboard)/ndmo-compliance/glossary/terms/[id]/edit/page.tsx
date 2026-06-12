import { TermForm } from "@/components/features/ndmo-compliance/Glossary/TermForm/TermForm";

export default async function EditTermRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TermForm mode="edit" termId={id} />;
}
