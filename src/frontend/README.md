# Job Assist: frontend (Next.js, JavaScript)

## Run
```bash
cd src/frontend
npm install
cp .env.local.example .env.local   # points at the Python backend
npm run dev                        # http://localhost:3000
```

## Layout
- `app/`: pages (`/`, `/onboarding`, `/chat`, `/jobs`, `/review`, `/profile`) and the root layout
- `components/`: shared UI (`Sidebar`, `PageHeader`)
- `lib/api.js`: every call to the backend goes through `apiFetch()`
- `next.config.mjs`: security headers sent with every page

The frontend never talks to Gemini or the database directly; only the backend does.
