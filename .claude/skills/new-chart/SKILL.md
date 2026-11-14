---
name: new-chart
description: Use when building or changing a data chart or chart page in apps/web. Covers Recharts usage, design tokens, team colors, loading/empty states, and mobile layout.
---

# Building a chart

1. **Data hook.** Fetch with TanStack Query in `apps/web/lib/queries/`. Typed response
   types mirror the API's Pydantic schemas.
2. **Component.** Place in `apps/web/components/charts/<ChartName>.tsx`. Use Recharts
   only. Wrap in `ResponsiveContainer`.
3. **Styling.** Axis, grid, tooltip, and text colors come from CSS variables in
   `apps/web/styles/tokens.css` so dark mode works automatically. Series use team colors
   from the API; when two drivers share a team, the second gets a dashed line.
   Minimalist: light gridlines, no chart borders, no gradients, no 3D.
4. **States.** Every chart has a skeleton loading state (the API may be cold-starting),
   an empty state with a short explanation, and an error state with a retry button.
5. **Controls.** Selectors (season, event, drivers) live above the chart and sync to the
   URL query string so every chart view is shareable. Respect the user's default season
   and units from preferences.
6. **Mobile.** Check at 375 px width: legends move below the chart, tooltips work on tap.
7. **Accessibility.** Give the chart a text summary (`aria-label` or a visually hidden
   caption) describing what it shows.
