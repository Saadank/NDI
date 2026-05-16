import { create } from "zustand";
import { persist } from "zustand/middleware";

import type {
  DataClassification,
  DataType,
  LegalBasis,
  RequestDirection,
  SelectedTableItem,
  SelectionMode,
  SharingType,
} from "@/lib/types/data-sharing/request.types";

// Form state shared across the 3-step "Raise New Request" wizard. Persisted
// in sessionStorage so reloading any step page doesn't drop user input.
export interface NewRequestForm {
  // Step 1 — direction (PULL = ask FOR data, PUSH = send data) chosen
  // before anything else. Drives Step 2's branching and the workflow's
  // source/receiver dept resolution.
  request_direction: RequestDirection;
  // Step 1 — details
  title: string;
  purpose: string;
  sharing_type: SharingType;
  receiver_group_id: number | null;
  data_classification: DataClassification;
  legal_basis: LegalBasis;
  personal_data_involved: boolean;
  estimated_data_subjects: number | null;
  data_subject_categories: string[];
  retention_period: 30 | 60 | 90 | 180 | null;
  dpia_confirmed: boolean;
  source_description: string;

  // Step 2 — data source
  data_type: DataType;
  // file mode
  staged_files: { name: string; size: number; type: string }[];
  // structured mode
  connection_id: string | null;
  selection_mode: SelectionMode | null;
  selected_items: SelectedTableItem[];
  custom_sql: string;

  // PUSH/EXTERNAL — recipient details when sharing_type==="external".
  // Inline so the wizard can call /requests/ with the embedded payload
  // and the backend's upsert_by_email handles find-or-create of the
  // t_external_recipients + t_recipient_contacts rows.
  external_org_name: string;
  external_contact_email: string;
  external_contact_name: string;
  external_dsa_text: string;

  // Step 3 — delivery
  delivery_channel: "portal" | "email" | "api";

  // Persisted draft id so re-uploading files doesn't recreate the request.
  draft_request_id: string | null;
}

interface NewRequestActions {
  set: <K extends keyof NewRequestForm>(key: K, value: NewRequestForm[K]) => void;
  patch: (patch: Partial<NewRequestForm>) => void;
  reset: () => void;
}

const INITIAL: NewRequestForm = {
  request_direction: "pull",
  title: "",
  purpose: "",
  sharing_type: "internal",
  receiver_group_id: null,
  data_classification: "internal",
  legal_basis: "",
  personal_data_involved: false,
  estimated_data_subjects: null,
  data_subject_categories: [],
  retention_period: 90,
  dpia_confirmed: false,
  source_description: "",
  data_type: "file",
  staged_files: [],
  connection_id: null,
  selection_mode: null,
  selected_items: [],
  custom_sql: "",
  external_org_name: "",
  external_contact_email: "",
  external_contact_name: "",
  external_dsa_text:
    "By accepting this Data Sharing Agreement, you confirm:\n" +
    "1. The shared data will only be used for the stated purpose.\n" +
    "2. You will not redistribute the data to third parties.\n" +
    "3. You will delete the data within the agreed retention period.\n" +
    "4. You will protect the data with reasonable security measures.\n" +
    "5. Any breach must be reported within 72 hours.",
  delivery_channel: "portal",
  draft_request_id: null,
};

// SSR-safe storage. Falls back to a noop on the server so importing the store
// in a server file (during type analysis) doesn't blow up.
function getSessionStorage(): Storage | undefined {
  if (typeof window === "undefined") return undefined;
  return window.sessionStorage;
}

export const useNewRequestStore = create<NewRequestForm & NewRequestActions>()(
  persist(
    (set) => ({
      ...INITIAL,
      set: (key, value) => set({ [key]: value } as Partial<NewRequestForm>),
      patch: (patch) => set(patch),
      reset: () => set({ ...INITIAL }),
    }),
    {
      name: "datarix-new-request",
      storage: {
        getItem: (name) => {
          const s = getSessionStorage();
          if (!s) return null;
          const raw = s.getItem(name);
          return raw ? JSON.parse(raw) : null;
        },
        setItem: (name, value) => {
          const s = getSessionStorage();
          s?.setItem(name, JSON.stringify(value));
        },
        removeItem: (name) => {
          const s = getSessionStorage();
          s?.removeItem(name);
        },
      },
      partialize: (state) => {
        // Strip the actions before serializing — they aren't useful at rest
        // and Zustand's `persist` typing happily widens to the slice type.
        const {
          set: _set,
          patch: _patch,
          reset: _reset,
          ...rest
        } = state;
        return rest as NewRequestForm & NewRequestActions;
      },
    },
  ),
);
