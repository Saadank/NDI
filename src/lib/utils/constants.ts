import type {
  DataClassification,
  LegalBasis,
  RequestStatus,
} from "@/lib/types/data-sharing/request.types";

export const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  in_review: "Under Review",
  approved: "Approved",
  rejected: "Rejected",
  changes_requested: "Changes Requested",
  cancelled: "Cancelled",
  completed: "Completed",
  expired: "Expired",
};

export const REQUEST_STATUS_COLORS: Record<RequestStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  submitted: "bg-blue-100 text-blue-800",
  in_review: "bg-amber-100 text-amber-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  changes_requested: "bg-amber-100 text-amber-800",
  cancelled: "bg-gray-100 text-gray-800",
  completed: "bg-green-100 text-green-800",
  expired: "bg-gray-100 text-gray-500",
};

export const FEATURES = ["data-sharing", "ndi", "data-quality", "dsr"] as const;
export type Feature = (typeof FEATURES)[number];

// Mirrors backend `DataClassification` enum — exact strings sent to the API.
export const DATA_CLASSIFICATIONS: { value: DataClassification; label: string }[] =
  [
    { value: "public", label: "Public" },
    { value: "internal", label: "Internal" },
    { value: "confidential", label: "Confidential" },
    { value: "sensitive", label: "Sensitive" },
  ];

// Mirrors backend `LegalBasis` enum.
export const LEGAL_BASIS_OPTIONS: { value: LegalBasis; label: string }[] = [
  { value: "consent", label: "Consent" },
  { value: "contract", label: "Contract" },
  { value: "legal_obligation", label: "Legal obligation" },
  { value: "vital_interest", label: "Vital interest" },
  { value: "public_interest", label: "Public interest" },
  { value: "legitimate_interest", label: "Legitimate interest" },
];
