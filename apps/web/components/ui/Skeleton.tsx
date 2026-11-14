import { cn } from "./cn";

export function Skeleton({ className, label = "Loading" }: { className?: string; label?: string }) {
  return (
    <div
      role="status"
      aria-label={label}
      className={cn("animate-pulse rounded-md bg-surface-muted", className)}
    />
  );
}
