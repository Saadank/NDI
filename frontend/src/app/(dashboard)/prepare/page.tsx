"use client";

import Link from "next/link";
import { CircleCheck, UploadCloud } from "lucide-react";
import { useMemo } from "react";

import { useRequests } from "@/lib/hooks/data-sharing/useRequests";
import { useRoleGuard } from "@/lib/hooks/useRoleGuard";
import { useAuthStore } from "@/lib/store/auth.store";
import { formatRelativeTime } from "@/lib/utils/formatters";

export default function PrepareUploadIndexPage() {
  // ─── Hooks (unconditional, top of component) ──────────────────────────
  // React enforces a stable hook-call order: every hook used by this
  // component must be invoked on every render, before any conditional
  // return. The previous version called useMemo AFTER the
  // `if (!isReady) return null;` early-exit, which produced a
  // "change in the order of Hooks" runtime error on the render
  // following the role-guard becoming ready.
  const { isReady } = useRoleGuard({ allow: ["requester", "data_owner"] });
  const requestsQuery = useRequests({ page: 1, limit: 100 });
  const myUserId = useAuthStore((s) => s.user?.id ?? null);

  // The Prepare & Upload page is for stewards who need to act on a
  // workflow step they're assigned to — typically the Source Steward
  // Upload step (assignee_role="source") or the final Requester
  // Steward Delivery step (assignee_role="requester"). The previous
  // filter (request.status="approved") was a red herring: it gated
  // on REQUEST status instead of per-user step assignment, so a
  // steward whose step was pending but whose request was still
  // in_review never saw their work.
  //
  // The backend's find_for_user query already returns the user's
  // visible requests and annotates each with current_step. We just
  // bucket locally to the steward-actionable subset.
  const rows = useMemo(() => {
    if (myUserId === null) return [];
    const all = requestsQuery.data?.data ?? [];
    return all.filter((r) => {
      const step = r.current_step;
      if (!step) return false;
      if (step.assignee_user_id !== myUserId) return false;
      const role = (step.assignee_role ?? "").toLowerCase();
      return role === "source" || role === "requester";
    });
  }, [requestsQuery.data, myUserId]);

  // ─── Conditional rendering (after every hook has been called) ──────────
  if (!isReady) return null;

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

        {requestsQuery.isLoading ? (
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
            Nothing to prepare right now — you&rsquo;ll see requests here when a
            Source Steward Upload or final Delivery step is assigned to you.
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
