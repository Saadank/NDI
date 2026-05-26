/**
 * NDMO Compliance subtree layout.
 *
 * Scoped RTL wrapper.  The (dashboard) layout (Topbar + Sidebar) remains
 * LTR so the global shell stays consistent for users who switch between
 * products; only the NDMO page body flips to RTL + Arabic.
 *
 * Per the Phase-0 architectural decision and the Datarix-Mono convention
 * (admin pages today scope `dir="rtl"` to individual fields), we keep RTL
 * scoped to the NDMO subtree using a wrapper div.
 */
export default function NdmoComplianceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div dir="rtl" lang="ar" className="flex min-h-0 flex-1 flex-col">
      {children}
    </div>
  );
}
