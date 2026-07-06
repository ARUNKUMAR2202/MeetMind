# Manual tasks

Things I can't do for you (restarting your terminals, running SQL in the Supabase
dashboard, setting real API keys/secrets) land here as they come up. Check this file
after each phase. Done items stay checked off with the date, not deleted, so there's
a record of what's already been handled.

## Open

- [ ] **Restart the backend on the new port (8010, not 8000)** and the frontend.
      Port 8000 has a stuck/orphaned entry in Windows' network stack (leftover from
      the Docker teardown) that keeps swallowing requests with a 404, even though no
      real process owns it anymore — couldn't clear it without admin rights, so we
      moved off it instead. `frontend/.env.local` already points at 8010.
      ```powershell
      cd D:\MeetMind\backend
      .\venv\Scripts\Activate.ps1
      uvicorn app.main:app --reload --port 8010
      ```
      ```powershell
      cd D:\MeetMind\frontend
      npm run dev
      ```

- [ ] **(Optional) Reclaim port 8000.** Not required — 8010 works fine — but if you
      want port 8000 back at some point, open PowerShell **as Administrator** and run:
      ```powershell
      net stop winnat
      net start winnat
      ```
      If the phantom listener is still there after that, a reboot will clear it.

## Done

- [x] (2026-07-06) **Backend venv was broken and has been rebuilt.** It had
      originally been created at `C:\Users\ARUNKUMAR\meetmind\backend\venv`, then the
      project moved to `D:\MeetMind` — every `.exe` launcher in `venv\Scripts`
      (`uvicorn.exe`, `pip.exe`, etc.) had that old path baked in, so all of them
      failed with "Fatal error in launcher". Deleted `backend\venv` and recreated it
      fresh at its current path, reinstalled `requirements.txt` (incl. the editable
      `ai-pipeline` package) and `pytest`. Verified: `uvicorn.exe --version` runs, and
      `pytest` passes (31 passed, 6 skipped — the 6 need a local Redis, expected).
      You don't need to do anything here — just use it as normal:
      ```powershell
      cd D:\MeetMind\backend
      .\venv\Scripts\Activate.ps1
      uvicorn app.main:app --reload --port 8000
      ```

- [x] (2026-07-06) Backend CORS fix — `backend/.env` now allows
      `http://localhost:3001`; confirmed picked up after the backend was restarted.

- [x] (2026-07-05) Phase 1 — nothing required in the Supabase dashboard yet: local
      SQLite is the default and needs no setup. Only when you're ready to point
      `DATABASE_URL` at a real Supabase project do you need to run
      `supabase/migrations/0001_rooms.sql` in the Supabase SQL Editor.
