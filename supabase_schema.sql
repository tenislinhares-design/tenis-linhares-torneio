-- Tênis Linhares — Módulo de Torneios
-- Rode este arquivo no SQL Editor do Supabase.
-- As tabelas usam prefixo tl_ para não misturar com o antigo projeto de gols.

create table if not exists public.tl_tournaments (
  id bigint generated always as identity primary key,
  name text not null,
  start_date date not null,
  end_date date not null,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.tl_categories (
  id bigint generated always as identity primary key,
  tournament_id bigint not null references public.tl_tournaments(id) on delete cascade,
  name text not null,
  max_players integer not null default 16,
  created_at timestamptz not null default now(),
  unique (tournament_id, name)
);

create table if not exists public.tl_players (
  id bigint generated always as identity primary key,
  name text not null,
  whatsapp text,
  city text,
  is_outside boolean not null default false,
  unavailable text,
  created_at timestamptz not null default now()
);

create unique index if not exists tl_players_whatsapp_unique
on public.tl_players (whatsapp)
where whatsapp is not null and whatsapp <> '';

create table if not exists public.tl_registrations (
  id bigint generated always as identity primary key,
  tournament_id bigint not null references public.tl_tournaments(id) on delete cascade,
  category_id bigint not null references public.tl_categories(id) on delete cascade,
  player_id bigint not null references public.tl_players(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (tournament_id, category_id, player_id)
);

create table if not exists public.tl_matches (
  id bigint generated always as identity primary key,
  tournament_id bigint not null references public.tl_tournaments(id) on delete cascade,
  category_id bigint not null references public.tl_categories(id) on delete cascade,
  round_num integer not null,
  round_name text not null,
  position integer not null,
  player1_id bigint references public.tl_players(id) on delete set null,
  player2_id bigint references public.tl_players(id) on delete set null,
  source1_match_id bigint references public.tl_matches(id) on delete set null,
  source2_match_id bigint references public.tl_matches(id) on delete set null,
  winner_id bigint references public.tl_players(id) on delete set null,
  score text,
  status text not null default 'pendente',
  scheduled_date date,
  scheduled_time text,
  court integer,
  created_at timestamptz not null default now()
);

create index if not exists tl_categories_tournament_idx on public.tl_categories(tournament_id);
create index if not exists tl_registrations_tournament_category_idx on public.tl_registrations(tournament_id, category_id);
create index if not exists tl_matches_tournament_category_idx on public.tl_matches(tournament_id, category_id);
create index if not exists tl_matches_schedule_idx on public.tl_matches(scheduled_date, scheduled_time, court);

-- App teste usa SUPABASE_SERVICE_ROLE_KEY no servidor.
-- Para teste, deixamos RLS desativado nestas tabelas tl_.
alter table public.tl_tournaments disable row level security;
alter table public.tl_categories disable row level security;
alter table public.tl_players disable row level security;
alter table public.tl_registrations disable row level security;
alter table public.tl_matches disable row level security;
