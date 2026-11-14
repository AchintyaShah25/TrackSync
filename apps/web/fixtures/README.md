# Showcase fixtures

`api/` holds API responses recorded during a real build, so CI can build the static
showcase pages without a live API (decision 0010).

Re-record after the data or the showcase list (`lib/showcase.ts`) changes, with the local
API running on :8000:

```sh
rm -rf fixtures/api
NEXT_PUBLIC_API_URL=http://localhost:8000 SHOWCASE_RECORD=1 pnpm build
```

CI builds with `SHOWCASE_FIXTURES=1`; a missing snapshot behaves like a 404.
