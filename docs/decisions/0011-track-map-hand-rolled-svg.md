# 0011: Track map as a hand-rolled SVG component

- **Status:** Accepted (approved by owner during M1 planning)
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
The track map colors each of the ~300 segments of a lap by speed and overlays the circuit
outline and corner numbers. CLAUDE.md allows only Recharts as a chart library unless
approved otherwise.

## Options considered
1. **Recharts ScatterChart** with dense colored dots: stays within the rule, but looks
   dotted, and aspect ratio and orientation are awkward.
2. **Another chart library** (d3, visx): flexible, but adds a dependency for one view.
3. **Plain React SVG**: about 150 lines, no new dependency, exact control over aspect
   ratio, stroke and labels.

## Decision
Option 3 (`apps/web/components/charts/TrackMap.tsx`). Coordinates arrive already
normalized from the ETL (decision 0007). The component flips y for SVG, draws the outline
as a wide neutral stroke, and draws one colored line per segment from a sequential ramp
(dark blue → teal → yellow, monotonic in lightness). Corner labels are offset along the
MultiViewer angle. The `<svg>` has a text summary (`role="img"` + `aria-label`).

## Consequences
- No new dependency. Recharts remains the only chart library.
- Hover readouts per segment are not implemented (the speed legend and text summary cover
  it). They could be added later with a nearest-point lookup.
