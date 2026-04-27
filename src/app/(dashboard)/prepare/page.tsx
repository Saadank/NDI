"use client";

import Link from "next/link";
import { CircleCheck, UploadCloud } from "lucide-react";

import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { formatRelativeTime } from "@/lib/utils/formatters";

export default function PrepareUploadIndexPage() {
  const { isReady } = useRoleGuard({
    allow: ["requester", "data_owner"],
  });
  // Approved requests are the ones the steward needs to act on (upload files
  // or execute the structured query).
  const approvedQuery = useRequests({ page: 1, limit: 50, status: "approved" });

  if (!isReady) return null;

  const rows = approvedQuery.data?.data ?? [];

  return (
    <main className="flex flex-1 flex-col gap-5 px-12 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-auth-text">Prepare &amp; Upload</h1>
      </div>

      <div
        className="flex flex-col overflow-hidden rounded-lg"
        style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
      >
        <div
          className="flex h-10 shrink-0 items-center px-5"
          style={{
            backgroundColor: "#FAFAFA",
            borderBottom: "1px solid #EEEEEE",
          }}
        >
          <span
            className="flex-1 text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            REQUEST
          </span>
          <span
            className="w-[120px] text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            DATA TYPE
          </span>
          <span
            className="w-[140px] text-[11px] font-semibold tracking-[0.6px]"
            style={{ color: "#9E9E9E" }}
          >
            UPDATED
          </span>
        </div>

        {approvedQuery.isLoading ? (
          <div className="flex items-center justify-center py-20 text-sm text-auth-text-subtle">
            Loading…
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-20 text-sm text-auth-text-subtle">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full"
              style={{ backgroundColor: "#FFF5F0" }}
            >
              <UploadCloud className="h-5 w-5" style={{ color: "#D76736" }} />
            </div>
            No approved requests waiting for delivery.
          </div>
        ) : (
          rows.map((r, i) => (
            <Link
              key={r.id}
              href={`/prepare/${r.id}`}
              className="flex h-16 items-center px-5 hover:bg-[#FFFBF9]"
              style={{
                borderBottom:
                  i < rows.length - 1 ? "1px solid #EEEEEE" : undefined,
              }}
            >
              <div className="flex flex-1 flex-col gap-1">
                <span className="text-[13px] font-semibold text-auth-text">
                  {r.title}
                </span>
                <span className="text-[11px] text-auth-text-subtle">
                  {r.request_number} · {r.data_classification}
                </span>
              </div>
              <span className="w-[120px] text-xs" style={{ color: "#515157" }}>
                <span className="inline-flex items-center gap-1.5">
                  {r.data_type === "file" ? (
                    <>
                      <UploadCloud
                        className="h-3.5 w-3.5"
                        style={{ color: "#D76736" }}
                      />
                      File upload
                    </>
                  ) : (
                    <>
                      <CircleCheck
                        className="h-3.5 w-3.5"
                        style={{ color: "#449235" }}
                      />
                      Structured query
                    </>
                  )}
                </span>
              </span>
              <span className="w-[140px] text-xs" style={{ color: "#9E9E9E" }}>
                {formatRelativeTime(r.updated_at)}
              </span>
            </Link>
          ))
        )}
      </div>
    </main>
  );
}
