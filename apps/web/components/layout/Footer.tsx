export function Footer() {
  return (
    <footer className="mt-16 border-t border-border">
      <div className="mx-auto flex max-w-[var(--content-max)] flex-col gap-2 px-[var(--gutter)] py-8 text-xs text-subtle">
        <p>
          TrackSync is an unofficial fan project. It is not affiliated with, endorsed by, or
          connected to Formula 1, the FIA, or any team. F1 and related marks are trademarks of
          their owners.
        </p>
        <p>
          Data:{" "}
          <a className="underline hover:text-fg" href="https://openf1.org" rel="noreferrer">
            OpenF1
          </a>{" "}
          (CC BY-NC-SA 4.0) and{" "}
          <a className="underline hover:text-fg" href="https://github.com/jolpica/jolpica-f1" rel="noreferrer">
            Jolpica-F1
          </a>
          . Circuit info via MultiViewer. For non-commercial use.
        </p>
      </div>
    </footer>
  );
}
