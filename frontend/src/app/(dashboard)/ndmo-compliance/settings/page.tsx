"use client";

import { ShieldCheck } from "lucide-react";

/**
 * NDMO Compliance — Settings (placeholder).
 *
 * The project spec lists `settings` as a sub-route alongside the 5
 * detailed screens.  Concrete settings (cycle management, role mapping,
 * notification preferences) are out of MVP scope.  Stubbed for now so the
 * sidebar link doesn't 404.
 */
export default function NdmoSettingsRoute() {
  return (
    <div className="flex flex-1 flex-col" style={{ backgroundColor: "#FFFFF9" }}>
      <div
        className="flex h-16 shrink-0 items-center px-8"
        style={{ backgroundColor: "#FFFFFF", borderBottom: "1px solid #EEEEEE" }}
      >
        <div>
          <h1 className="text-lg font-bold" style={{ color: "#070709" }}>الإعدادات</h1>
          <p className="text-[12px]" style={{ color: "#616161" }}>
            إعدادات الجهة، إدارة الدورات، تفضيلات الإشعارات
          </p>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center">
        <div
          className="flex max-w-md flex-col items-center gap-3 rounded-xl p-8 text-center"
          style={{ backgroundColor: "#FFFFFF", border: "1px solid #EEEEEE" }}
        >
          <ShieldCheck className="h-10 w-10" style={{ color: "#D76736" }} />
          <p className="text-[14px] font-bold" style={{ color: "#070709" }}>
            صفحة الإعدادات قيد التطوير
          </p>
          <p className="text-[12px]" style={{ color: "#616161" }}>
            ستتضمن إدارة دورات التقييم، تخصيص الأدوار، وإعدادات الإشعارات في إصدار قادم.
          </p>
        </div>
      </div>
    </div>
  );
}
