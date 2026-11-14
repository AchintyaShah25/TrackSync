"use client";

import { Button } from "./Button";

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-border p-6 text-center">
      <p className="font-medium">{title}</p>
      {children && <p className="max-w-md text-sm text-muted">{children}</p>}
    </div>
  );
}

export function ErrorState({
  message = "Something went wrong loading this data.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex min-h-48 flex-col items-center justify-center gap-3 rounded-lg border border-border p-6 text-center"
    >
      <p className="text-sm text-muted">{message}</p>
      <p className="text-xs text-subtle">
        The free API sleeps when idle and can take up to a minute to wake up.
      </p>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
