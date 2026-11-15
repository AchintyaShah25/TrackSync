"use client";

import type { DryCompound, StintIn } from "@/lib/api/types";
import {
  DRY,
  MAX_STINTS,
  MAX_STRATEGIES,
  oneStop,
  STRATEGY_COLORS,
  strategyErrors,
  strategyLabel,
  twoStop,
} from "@/lib/charts/forecast";
import { compoundColor, compoundLabel } from "@/lib/charts/strategy";

import { Button } from "../ui/Button";
import { cn } from "../ui/cn";

/** Editable list of up to three strategies (each a list of dry stints). Controlled. */
export function StrategyBuilder({
  strategies,
  totalLaps,
  actual,
  onChange,
}: {
  strategies: StintIn[][];
  totalLaps: number;
  actual: StintIn[] | null;
  onChange: (next: StintIn[][]) => void;
}) {
  const set = (i: number, stints: StintIn[]) => onChange(strategies.map((s, k) => (k === i ? stints : s)));
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 lg:grid-cols-3">
        {strategies.map((stints, i) => (
          <StrategyCard
            key={i}
            index={i}
            stints={stints}
            totalLaps={totalLaps}
            actual={actual}
            onChange={(next) => set(i, next)}
            onRemove={strategies.length > 1 ? () => onChange(strategies.filter((_, k) => k !== i)) : undefined}
          />
        ))}
      </div>
      {strategies.length < MAX_STRATEGIES && (
        <Button
          size="sm"
          variant="ghost"
          className="self-start"
          onClick={() => onChange([...strategies, strategies.length % 2 ? twoStop(totalLaps) : oneStop(totalLaps)])}
        >
          + Add strategy
        </Button>
      )}
    </div>
  );
}

function StrategyCard({
  index,
  stints,
  totalLaps,
  actual,
  onChange,
  onRemove,
}: {
  index: number;
  stints: StintIn[];
  totalLaps: number;
  actual: StintIn[] | null;
  onChange: (s: StintIn[]) => void;
  onRemove?: () => void;
}) {
  const label = strategyLabel(index);
  const errors = strategyErrors(stints, totalLaps);
  const used = stints.reduce((n, s) => n + s.laps, 0);
  const update = (k: number, patch: Partial<StintIn>) =>
    onChange(stints.map((s, j) => (j === k ? { ...s, ...patch } : s)));

  return (
    <fieldset className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-3">
      <legend className="sr-only">{label}</legend>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium">
          <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STRATEGY_COLORS[index] }} />
          {label}
        </span>
        {onRemove && (
          <Button size="sm" variant="ghost" onClick={onRemove} aria-label={`Remove ${label}`}>
            Remove
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-1" aria-label={`${label} presets`}>
        <Preset onClick={() => onChange(oneStop(totalLaps))}>1-stop</Preset>
        <Preset onClick={() => onChange(twoStop(totalLaps))}>2-stop</Preset>
        {actual && <Preset onClick={() => onChange(actual.map((s) => ({ ...s })))}>Real</Preset>}
      </div>

      <ol className="flex flex-col gap-2">
        {stints.map((s, k) => (
          <li key={k} className="flex items-center gap-2">
            <span className="w-12 shrink-0 text-xs text-subtle">Stint {k + 1}</span>
            <CompoundPicker
              label={`${label}, stint ${k + 1} compound`}
              value={s.compound}
              onChange={(compound) => update(k, { compound })}
            />
            <LapStepper
              label={`${label}, stint ${k + 1} laps`}
              value={s.laps}
              max={totalLaps}
              onChange={(laps) => update(k, { laps })}
            />
            {stints.length > 1 && (
              <button
                type="button"
                onClick={() => onChange(stints.filter((_, j) => j !== k))}
                aria-label={`Remove ${label} stint ${k + 1}`}
                className="ml-auto h-8 w-8 shrink-0 rounded-md text-muted hover:bg-surface-muted hover:text-fg"
              >
                ×
              </button>
            )}
          </li>
        ))}
      </ol>

      <div className="flex items-center justify-between gap-2 text-xs">
        {stints.length < MAX_STINTS ? (
          <button
            type="button"
            className="text-accent hover:underline"
            onClick={() => onChange([...stints, { compound: stints.at(-1)?.compound === "HARD" ? "MEDIUM" : "HARD", laps: Math.max(1, totalLaps - used) }])}
          >
            + Add stint
          </button>
        ) : (
          <span />
        )}
        <span className={cn("tabular-nums", used === totalLaps ? "text-subtle" : "font-medium text-fg")}>
          {used} / {totalLaps} laps
        </span>
      </div>
      {errors.length > 0 && (
        <ul className="flex flex-col gap-0.5 text-xs text-danger" aria-live="polite">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}

function Preset({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="h-7 rounded-md border border-border px-2 text-xs text-muted transition-colors hover:bg-surface-muted hover:text-fg"
    >
      {children}
    </button>
  );
}

function CompoundPicker({ label, value, onChange }: { label: string; value: DryCompound; onChange: (c: DryCompound) => void }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-border p-0.5">
      {DRY.map((c) => (
        <button
          key={c}
          type="button"
          role="radio"
          aria-checked={c === value}
          title={compoundLabel(c)}
          onClick={() => onChange(c)}
          className={cn(
            "inline-flex h-7 w-8 items-center justify-center gap-1 rounded-[calc(var(--radius-md)-2px)] text-xs",
            c === value ? "bg-surface-muted font-medium text-fg" : "text-muted hover:text-fg",
          )}
        >
          <span
            aria-hidden
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: compoundColor(c), boxShadow: c === "HARD" ? "inset 0 0 0 1px var(--tyre-hard-stroke)" : undefined }}
          />
          {c[0]}
        </button>
      ))}
    </div>
  );
}

function LapStepper({ label, value, max, onChange }: { label: string; value: number; max: number; onChange: (n: number) => void }) {
  const clamp = (n: number) => Math.min(max, Math.max(1, Math.round(n) || 1));
  return (
    <div className="inline-flex items-center rounded-md border border-border">
      <button type="button" aria-label={`${label}: one fewer`} onClick={() => onChange(clamp(value - 1))} className="h-8 w-7 text-muted hover:text-fg">
        −
      </button>
      <input
        type="number"
        inputMode="numeric"
        min={1}
        max={max}
        value={value}
        aria-label={label}
        onChange={(e) => onChange(clamp(Number(e.target.value)))}
        className="h-8 w-10 border-x border-border bg-transparent text-center text-sm tabular-nums [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
      />
      <button type="button" aria-label={`${label}: one more`} onClick={() => onChange(clamp(value + 1))} className="h-8 w-7 text-muted hover:text-fg">
        +
      </button>
    </div>
  );
}
