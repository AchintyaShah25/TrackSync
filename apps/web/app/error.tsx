"use client";

import { ErrorState } from "@/components/ui/States";

// Error boundaries must be Client Components; Next 16 passes `retry`.
export default function RouteError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <div className="py-12">
      <ErrorState message="We couldn't load this page." onRetry={retry} />
    </div>
  );
}
