import { create } from "zustand";

import { FEATURES, type Feature } from "@/lib/utils/constants";

interface UIState {
  sidebarOpen: boolean;
  currentFeature: Feature;
  toggleSidebar: () => void;
  setCurrentFeature: (feature: Feature) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  currentFeature: FEATURES[0],
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setCurrentFeature: (currentFeature) => set({ currentFeature }),
}));
