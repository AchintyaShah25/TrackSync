// Tooltip shell styled from tokens (works in both themes).
export function TooltipBox({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="rounded-md border px-3 py-2 text-xs shadow-none"
      style={{ background: "var(--chart-tooltip-bg)", borderColor: "var(--chart-tooltip-border)" }}
    >
      {children}
    </div>
  );
}
