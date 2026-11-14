// Sequential color ramp for the speed-colored track map. Stops run dark-to-light in
// lightness with a hue sweep (blue → teal → yellow), so the order reads even for
// color-vision deficiencies and in both themes.
const STOPS: [number, number, number][] = [
  [49, 54, 149],
  [69, 117, 180],
  [38, 166, 154],
  [171, 211, 96],
  [253, 231, 37],
];

export function speedColor(t: number): string {
  const x = Math.min(Math.max(t, 0), 1) * (STOPS.length - 1);
  const i = Math.min(Math.floor(x), STOPS.length - 2);
  const f = x - i;
  const [a, b] = [STOPS[i], STOPS[i + 1]];
  const c = a.map((v, k) => Math.round(v + (b[k] - v) * f));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

export function speedDomain(speed: number[]): [number, number] {
  return [Math.min(...speed), Math.max(...speed)];
}

export const SPEED_LEGEND_STOPS = [0, 0.25, 0.5, 0.75, 1].map((t) => ({ t, color: speedColor(t) }));
