-- Phase 1 — video conferencing room metadata.
--
-- host_id / participants.user_id are plain text guest identifiers for now (a
-- client-generated UUID stored in localStorage — see frontend/app/lib/guest.ts).
-- There is no auth yet, so these do NOT reference auth.users and Row Level
-- Security is intentionally left OFF here: with no logged-in user, RLS has no
-- identity to check against, and the backend talks to Postgres with a full
-- connection-string role anyway. Phase 2 adds a migration that repoints these
-- columns at auth.users(id) and turns RLS on with real policies.
--
-- Run this in the Supabase SQL Editor (or `psql "$DATABASE_URL" -f this-file`
-- against any Postgres instance, including the local docker-compose `db` service).

create table if not exists rooms (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    host_id text not null,
    status text not null default 'live' check (status in ('scheduled', 'live', 'ended')),
    created_at timestamptz not null default now(),
    ended_at timestamptz
);

create index if not exists rooms_code_idx on rooms (code);

create table if not exists participants (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references rooms (id) on delete cascade,
    user_id text not null,
    display_name text not null,
    joined_at timestamptz not null default now(),
    left_at timestamptz
);

create index if not exists participants_room_id_idx on participants (room_id);
