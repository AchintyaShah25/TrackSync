import { describe, expect, it } from "vitest";

import { chartRows } from "@/components/chat/ChatChart";
import type { ChatChartSpec } from "@/lib/api/types";
import { parseInline, parseMarkdown } from "@/lib/chat/markdown";
import { inUnits } from "@/lib/charts/telemetry";
import { safeNext } from "@/lib/auth/supabase";

describe("chat markdown", () => {
  // Why: model output is rendered as React text; markup in it must stay inert text.
  it("keeps HTML as plain text and parses bold, code and citations", () => {
    expect(parseInline('<img src=x onerror="alert(1)"> **Leclerc** won [2] with `M-H`')).toEqual([
      { kind: "text", text: '<img src=x onerror="alert(1)"> ' },
      { kind: "bold", text: "Leclerc" },
      { kind: "text", text: " won " },
      { kind: "cite", n: 2 },
      { kind: "text", text: " with " },
      { kind: "code", text: "M-H" },
    ]);
  });

  // Why: the system prompt allows short paragraphs and lists only; headings degrade to text.
  it("groups paragraphs and lists, and drops heading markers", () => {
    const blocks = parseMarkdown("## Result\nLeclerc won.\nNorris third.\n\n- one\n- two\n\n1. first\n2. second");
    expect(blocks.map((b) => b.kind)).toEqual(["p", "ul", "ol"]);
    expect(blocks[0]).toEqual({ kind: "p", inlines: [{ kind: "text", text: "Result Leclerc won. Norris third." }] });
    expect(blocks[1].kind === "ul" && blocks[1].items.length).toBe(2);
  });
});

describe("chat charts", () => {
  // Why: multi-series charts align by x; line charts must be ordered by x.
  it("merges series into rows keyed by x", () => {
    const spec: ChatChartSpec = {
      type: "line",
      title: "t",
      x_label: "Round",
      y_label: "Position",
      series: [
        { name: "NOR", points: [[2, 1], [1, 3]] },
        { name: "PIA", points: [[1, 2]] },
      ],
    };
    expect(chartRows(spec)).toEqual([
      { x: 1, s0: 3, s1: 2 },
      { x: 2, s0: 1 },
    ]);
  });
});

describe("preferences", () => {
  // Why: the units preference must convert speeds, not just relabel them.
  it("converts telemetry speeds to mph", () => {
    const trace = { points: { speed: [100, 340] } } as unknown as Parameters<typeof inUnits>[0][number];
    expect(inUnits([trace], "metric")[0]).toBe(trace);
    expect(inUnits([trace], "imperial")[0].points.speed.map(Math.round)).toEqual([62, 211]);
  });

  // Why: the sign-in redirect target comes from the URL; it must stay on this site.
  it("only allows same-site redirects after sign-in", () => {
    expect(safeNext("/races/2024/16/forecast?d=PIA")).toBe("/races/2024/16/forecast?d=PIA");
    for (const bad of ["https://evil.example", "//evil.example", "/\\evil", null, ""]) expect(safeNext(bad)).toBe("/");
  });
});
