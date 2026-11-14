# 0007: Circuit outline from the pole lap, in a shared normalized frame

- **Status:** Accepted
- **Date:** 2026-11-14
- **Milestone:** 1

## Context
The track map needs a clean circuit outline with corner labels. The v2 game will reuse
the same X/Y outlines. Raw OpenF1 location samples are noisy at ~3.7 Hz, and the native
coordinate system is rotated relative to official track maps.

## Options considered
1. **Static SVGs per circuit**: pretty, but licensing is unclear, and they don't line up
   with telemetry X/Y.
2. **Raw fastest-lap X/Y**: aligned with telemetry, but jagged, and oriented arbitrarily.
3. **Processed pole lap**: Savitzky-Golay smoothing and arc-length resampling, with
   rotation and corners from MultiViewer (via `fastf1.mvapi`).

## Decision
Option 3. For each event, the overall fastest qualifying lap is resampled to 400 points
by arc length, smoothed with a periodic Savitzky-Golay filter (window 15, order 3), then
rotated by MultiViewer's `rotation` (FastF1's track-map convention). Finally it is
normalized so the longest side spans [0, 1], keeping the aspect ratio. The same `Frame`
(rotation, origin, scale) maps that event's traces and the MultiViewer corner markers.
The circuit row keeps the outline from the newest event (`outline_event_id`), so layout
changes are picked up automatically.

## Consequences
- The frontend draws outline, speed-colored trace and corner labels in one SVG viewBox,
  with no math in the client.
- Traces from an older event at the same circuit use their own event's frame, which
  differs very slightly from the stored outline. This is invisible at map scale.
- If the MultiViewer API disappeared, rotation would default to 0 and corners would be
  empty. The map would still render, unrotated.
