import type { Inline } from "@/lib/chat/markdown";
import { parseMarkdown } from "@/lib/chat/markdown";

function Inlines({ items, idPrefix }: { items: Inline[]; idPrefix: string }) {
  return (
    <>
      {items.map((it, i) => {
        if (it.kind === "bold") return <strong key={i}>{it.text}</strong>;
        if (it.kind === "code")
          return (
            <code key={i} className="rounded bg-surface-muted px-1 text-[0.9em]">
              {it.text}
            </code>
          );
        if (it.kind === "cite")
          return (
            <a
              key={i}
              href={`#${idPrefix}-src-${it.n}`}
              className="ml-0.5 align-super text-[0.7em] font-medium text-accent hover:underline"
              aria-label={`Source ${it.n}`}
            >
              [{it.n}]
            </a>
          );
        return <span key={i}>{it.text}</span>;
      })}
    </>
  );
}

/** Renders an assistant answer. Model text only ever becomes React text nodes. */
export function Markdown({ text, idPrefix }: { text: string; idPrefix: string }) {
  return (
    <div className="flex flex-col gap-2 text-sm leading-relaxed">
      {parseMarkdown(text).map((b, i) =>
        b.kind === "p" ? (
          <p key={i}>
            <Inlines items={b.inlines} idPrefix={idPrefix} />
          </p>
        ) : b.kind === "ul" ? (
          <ul key={i} className="list-disc pl-5">
            {b.items.map((item, j) => (
              <li key={j}>
                <Inlines items={item} idPrefix={idPrefix} />
              </li>
            ))}
          </ul>
        ) : (
          <ol key={i} className="list-decimal pl-5">
            {b.items.map((item, j) => (
              <li key={j}>
                <Inlines items={item} idPrefix={idPrefix} />
              </li>
            ))}
          </ol>
        ),
      )}
    </div>
  );
}
