"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { setQueryClient } from "@/lib/api/queryClient";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: 1, staleTime: 30_000 },
      },
    });
    // Expose the client via a module-level ref so the auth/logout flow can
    // wipe the cache without needing access to React context.
    setQueryClient(client);
    return client;
  });

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Global toast outlet — required for sonner's toast() helper to
          render anywhere. Position bottom-right keeps it clear of the
          left sidebar and avoids covering sticky footers in detail
          screens. */}
      <Toaster position="bottom-right" richColors closeButton />
    </QueryClientProvider>
  );
}
