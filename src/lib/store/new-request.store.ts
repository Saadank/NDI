import { create } from "zustand";
import { persist } from "zustand/middleware";

import type {
  DataClassification,
  DataType,
  LegalBasis,
  SelectedTableItem,
  SelectionMode,
  SharingType,
} from "@/lib/types/data-sharing/request.types";

// Form state shared across the 3-step "Raise New Request" wizard. Persisted
// in sessionStorage so reloading any step page doesn't drop user input.
export interface NewRequestForm {
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
