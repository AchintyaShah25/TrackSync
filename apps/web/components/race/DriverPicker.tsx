"use client";

import type { DriverRef } from "@/lib/api/types";

import { cn } from "../ui/cn";

/** Toggle chips for choosing up to `max` drivers; keeps selection order (it sets colors). */
export function DriverPicker({
  drivers,
  selected,
  max,
  onChange,
  label = "Drivers",
}: {
  drivers: DriverRef[];
  selected: string[];
  max: number;
  onChange: (codes: string[]) => void;
  label?: string;
}) {
  const toggle = (code: string) => {
    if (selected.includes(code)) {
      if (max === 1) return;
      onChange(selected.filter((c) => c !== code));
    } else if (max === 1) {
      onChange([code]);
    } else {
      onChange([...selected, code].slice(-max));
    }
  };
  return (
    <fieldset>
      <legend className="mb-2 text-xs text-subtle">
        {label} {max > 1 && `(pick up to ${max})`}
      </legend>
      <div className="flex flex-wrap gap-1.5">
        {drivers.map((d) => {
          const on = selected.includes(d.code);
          return (
            <button
              key={d.id}
              type="button"
              aria-pressed={on}
              title={d.full_name}
              onClick={() => toggle(d.code)}
              className={cn(
                "inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs transition-colors",
                on ? "border-border-strong bg-surface-muted font-medium text-fg" : "border-border text-muted hover:text-fg",
              )}
            >
              <span
                aria-hidden
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: d.color_hex ?? "var(--chart-fallback-series)" }}
              />
              {d.code}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
