# Manual tasks

Things I can't do for you (restarting your terminals, running SQL in the Supabase
dashboard, setting real API keys/secrets) land here as they come up. Check this file
after each phase. Done items stay checked off with the date, not deleted, so there's
a record of what's already been handled.

## Open

- [ ] **Restart the backend** so it picks up the CORS fix (`backend/.env` now allows
      `http://localhost:3001` — it only takes effect on process start, not on save).
      In the backend terminal: Ctrl+C, then
      ```bash
      cd backend
      ./venv/Scripts/uvicorn app.main:app --reload
      ```
      Do this any time you edit `backend/.env` while the server is already running.

## Done

- [x] (2026-07-05) Phase 1 — nothing required in the Supabase dashboard yet: local
      SQLite is the default and needs no setup. Only when you're ready to point
      `DATABASE_URL` at a real Supabase project do you need to run
      `supabase/migrations/0001_rooms.sql` in the Supabase SQL Editor.
