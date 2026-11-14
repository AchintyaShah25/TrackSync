# 0006: Fastest-lap traces as 300-point columnar jsonb

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
The telemetry comparison overlays two drivers' fastest laps (speed, throttle, brake,
gear) and the track map colors the lap by speed. Supabase free has 500 MB in total, and
Render free has ~5 GB/month of bandwidth. OpenF1 samples car data at ~3.7 Hz (about
300 samples on an 80 s lap).

## Options considered
1. **Row per sample** (`trace_points` table): queryable, but ~10x the storage with
   per-row overhead, and slow to return.
2. **jsonb array of objects** (`[{"d":..,"speed":..}, ...]`): simple, but repeats every
   key 300 times.
3. **Columnar jsonb** (`{"d":[...],"speed":[...],...}`) on a uniform distance grid:
   compact (TOAST-compressed), one row per driver-lap, maps directly to chart data.

## Decision
Option 3. Each trace is resampled onto 300 points spaced evenly from 0 to a reference
lap length. The reference is the median integrated distance of that session's fastest
laps, and each driver's distance is scaled onto it, so all drivers share the same
x-axis. Continuous channels (speed, throttle, x, y) are linearly interpolated, and
discrete ones (gear, brake) use the nearest sample. x/y are stored in the circuit's
normalized frame (docs/decisions/0007). Stored for Q and R.

## Consequences
- About 10–15 KB per trace. For ~95 events × 2 sessions × 20 drivers, that is roughly
  30–60 MB (measured after backfill with `make db-size`).
- A two-driver API response is ~25 KB before gzip.
- 300 points is near OpenF1's native resolution, so little is lost. Very short braking
  spikes can be smoothed slightly.
- Scaling to a common length hides small line differences between drivers. That is
  acceptable for comparing driving style; it is not a racing-line analysis.
