Copy .env.example to .env

API Usage found here: https://www.earningsapi.com/dashboard

## Supabase setup

This project stores earnings events in a Supabase Postgres table (so history
accumulates instead of being overwritten) and publishes the generated
`earnings.ics` to Supabase Storage (so nothing gets committed back to git).

1. Create a Supabase project.
2. In the SQL Editor, run `supabase/migrations/0001_earnings_events.sql`.
   This creates the `earnings_events` table and a public `calendar` storage
   bucket.
3. From Project Settings > API, copy your project URL and `service_role` key
   into `.env` as `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.
4. If running via GitHub Actions, add `API_KEY`, `SUPABASE_URL`, and
   `SUPABASE_SERVICE_KEY` as repo secrets (Settings > Secrets and variables >
   Actions).
5. After the first run, your subscribable calendar URL will be:
   `https://YOUR-PROJECT-REF.supabase.co/storage/v1/object/public/calendar/earnings.ics`
