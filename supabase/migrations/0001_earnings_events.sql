-- Run this in the Supabase SQL Editor (Database > SQL Editor > New query)
-- or via `supabase db push` if you're using the Supabase CLI locally.

-- 1. Table that persists every earnings event we've ever seen.
--    Rows are never deleted, so this naturally accumulates history.
create table if not exists earnings_events (
  uid           text primary key,        -- e.g. "PLTR-2026-08-03"
  ticker        text not null,
  report_date   date not null,
  report_time   text,                    -- 'pre' | 'after' | null
  eps_estimate  numeric,
  first_seen    timestamptz not null default now(),
  last_updated  timestamptz not null default now()
);

create index if not exists earnings_events_report_date_idx
  on earnings_events (report_date);

create index if not exists earnings_events_ticker_idx
  on earnings_events (ticker);

-- 2. Keep last_updated fresh automatically on every upsert.
create or replace function set_last_updated()
returns trigger as $$
begin
  new.last_updated = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_earnings_events_last_updated on earnings_events;
create trigger trg_earnings_events_last_updated
  before update on earnings_events
  for each row
  execute function set_last_updated();

-- 3. Row Level Security: lock the table down by default.
--    The script authenticates with the service_role key, which bypasses RLS,
--    so no policy is required for it to read/write. This just prevents the
--    anon/public key from touching the table if you ever expose it.
alter table earnings_events enable row level security;

-- 4. Storage bucket to host the generated .ics file publicly.
--    Safe to re-run: does nothing if the bucket already exists.
insert into storage.buckets (id, name, public)
values ('calendar', 'calendar', true)
on conflict (id) do nothing;

-- 5. Allow public read of objects in the "calendar" bucket (so the .ics URL
--    is subscribable from Google/Apple Calendar without auth), but restrict
--    writes to the service_role key (used by the GitHub Action).
drop policy if exists "Public read calendar bucket" on storage.objects;
create policy "Public read calendar bucket"
  on storage.objects for select
  using (bucket_id = 'calendar');
