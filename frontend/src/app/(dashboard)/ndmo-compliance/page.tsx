import { NdmoDashboard } from "@/components/features/ndmo-compliance/Dashboard/Dashboard";

/**
 * NDMO Compliance — landing page (Dashboard).
 *
 * Thin server-component shell that delegates to the client-side feature
 * component.  Matches the data-sharing pattern (e.g. /data-sharing/[id]
 * delegates to <RequestDetail />).
 */
export default function NdmoCompliancePage() {
  return <NdmoDashboard />;
}
