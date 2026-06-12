/**
 * Business Glossary subtree layout.
 *
 * The parent NDMO layout flips the product body to RTL/Arabic.  Per the
 * design handoff, the Business Glossary renders LTR/English, so this layout
 * re-flips direction back for the glossary routes only.  Bilingual content
 * (name_ar / definition_ar) is still captured per term and rendered in
 * dir="rtl" blocks where shown.
 */
export default function GlossaryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      dir="ltr"
      lang="en"
      className="min-h-0 flex-1"
      style={{ backgroundColor: "#FAFAF8", color: "#171717" }}
    >
      <div className="mx-auto max-w-[1280px] px-7 py-7">{children}</div>
    </div>
  );
}
