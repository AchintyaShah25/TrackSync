-- Milestone 3: knowledge base for the chat agent, durable usage counters, and user-owned
-- preferences and saved items (decisions 0027, 0030, 0032).

create extension if not exists vector with schema extensions;

-- ---------------------------------------------------------------- knowledge base (RAG)

create table public.rag_documents (
  id            bigint generated always as identity primary key,
  source        text not null check (source in ('fia', 'wikipedia', 'summary')),
  source_key    text not null unique,          -- stable id, e.g. 'wikipedia:2024_Italian_Grand_Prix'
  title         text not null,
  url           text,
  license       text not null,                 -- shown with every citation
  season        smallint,
  event_id      integer references public.events (id) on delete set null,
  content_hash  text not null,                 -- skip re-chunking/embedding when unchanged
  updated_at    timestamptz not null default now()
);

create table public.rag_chunks (
  id           bigint generated always as identity primary key,
  document_id  bigint not null references public.rag_documents (id) on delete cascade,
  ord          integer not null,
  section      text,                           -- e.g. 'Article B5.13 Safety Car (SC)' or 'Race'
  heading      text not null default '',       -- document title + section, weighted highest
  content      text not null,
  embedding    extensions.vector(768),         -- null if embedding failed; full-text still works
  tsv          tsvector generated always as (
                 setweight(to_tsvector('english', heading), 'A')
                 || setweight(to_tsvector('english', content), 'D')
               ) stored,
  unique (document_id, ord)
);

create index rag_chunks_embedding_idx on public.rag_chunks
  using hnsw (embedding extensions.vector_cosine_ops);
create index rag_chunks_tsv_idx on public.rag_chunks using gin (tsv);

-- ---------------------------------------------------------------- usage counters
-- Daily chat limits must survive restarts of the free API (decision 0032). Server only.

create table public.usage_counters (
  key    text not null,                        -- 'chat:guest:<ip>', 'chat:user:<uuid>', 'chat:all'
  day    date not null,
  count  integer not null default 0 check (count >= 0),
  primary key (key, day)
);

-- ---------------------------------------------------------------- user-owned data

create table public.user_preferences (
  user_id             uuid primary key references auth.users (id) on delete cascade,
  favorite_driver_id  text references public.drivers (id) on delete set null,
  favorite_team_id    text,
  theme               text check (theme in ('light', 'dark', 'system')),
  units               text not null default 'metric' check (units in ('metric', 'imperial')),
  chat_level          text not null default 'beginner' check (chat_level in ('beginner', 'expert')),
  home_widgets        jsonb not null default '[]',  -- saved_items ids pinned to the landing page
  updated_at          timestamptz not null default now()
);

create table public.saved_items (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  kind        text not null check (kind in ('chart', 'strategy')),
  title       text not null check (char_length(title) between 1 and 120),
  path        text not null check (path like '/%' and char_length(path) <= 500),
  created_at  timestamptz not null default now()
);
create index saved_items_user_idx on public.saved_items (user_id, created_at desc);

-- ---------------------------------------------------------------- row-level security

alter table public.rag_documents enable row level security;
alter table public.rag_chunks enable row level security;
create policy "public read" on public.rag_documents for select to anon, authenticated using (true);
create policy "public read" on public.rag_chunks for select to anon, authenticated using (true);

-- RLS on, no policy: invisible to anon and authenticated; only the API/ETL owner role.
alter table public.usage_counters enable row level security;

alter table public.user_preferences enable row level security;
create policy "own preferences" on public.user_preferences
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

alter table public.saved_items enable row level security;
create policy "own saved items" on public.saved_items
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

-- Explicit grants (Supabase's default privileges would add these; being explicit keeps the
-- intent visible and makes fresh test databases behave like production).
grant select on public.rag_documents, public.rag_chunks to anon, authenticated;

-- Anonymous visitors get no access at all to user data or usage counters (stronger than
-- RLS returning zero rows; the anon key is public).
revoke all on public.user_preferences, public.saved_items, public.usage_counters from anon;
revoke all on public.usage_counters from authenticated;

-- The API runs /me queries as `authenticated` (set local role) so RLS applies to it too.
grant select, insert, update, delete on public.user_preferences, public.saved_items to authenticated;
