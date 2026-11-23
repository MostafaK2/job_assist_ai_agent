# Job Assist AI Agent
An AI agent that helps you apply for jobs. You describe the jobs you want. The agent finds matching Greenhouse postings and drafts your application answers. After you approve the draft, it fills in the real application form in your own Chrome tab. You press Submit yourself. The agent never submits.

Limitations right now:
- Job listings are stand-in data loaded by the ingest step at setup. Therefore job listing could be out of date.
- Onboarding (resume upload + profile questions at `/onboarding`) is not finished. Skip it.

## Tech stack/Requirements
 
- **Backend:** Python 3.12 / 3.13 (not 3.14, which breaks some dependencies), LangGraph + LangChain, Google Gemini (`langchain-google-genai`), FastAPI, SQLAlchemy + Alembic
- **Frontend:** Next.js 16 (JSX), Tailwind CSS, assistant-ui (Assistant Transport)
- **Extension:** Chrome MV3 (`src/extension`) 
- **Database:** PostgreSQL 16
- **Packaging:** Docker Compose + Caddy (HTTPS)

The extension is required for filling out the forms. 

## Configuration

Create an .env file in the project root

```env
# BACKEND
GOOGLE_API_KEY=paste-your-key-here
GEMINI_MODEL=gemini-3.5-flash
APP_DATABASE_URL=postgresql+psycopg://agent:agent@localhost:5432/agent
 
# SUMMARIZATION (optional)
# SUMMARY_TRIGGER_TOKENS=100
# SUMMARY_TRIGGER_MESSAGES=10
# SUMMARY_KEEP_MESSAGES=2
# SUMMARY_TRIM_TOKEN=50
 
# DEVELOPMENT
STAND_IN_JOB=andurilindustries/5217113007
 
# DATABASE
POSTGRES_USER=agent
POSTGRES_PASSWORD=agent
POSTGRES_DB=agent
 
# FRONTEND
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK=false
 
# HTTPS (CADDY)
DOMAIN=localhost
BIND_IP=127.0.0.1
```
Only `GOOGLE_API_KEY` is required. Change the model and summarization settings if you want to.

`localhost` in `APP_DATABASE_URL` is for local development. Inside Docker, the backend reaches the database at host `db`: `postgresql+psycopg://agent:agent@db:5432/agent`.

For Deployment change `DOMAIN` and `BIND_IP`

## Option A: Running with Docker + Caddy (recommended)
### 1. Docker commands to run the project

From the project's `root` directory run these docker commands to setup up frontend, backend, database and caddy. 
```bash
docker compose up -d --build
docker compose logs -f ingest   # Check jobs "SYNC SUMMARY"
docker compose ps -a            # verify if its running
```

Open https://localhost or `https://<DOMAIN>` to open the application
### Services spun up by docker
 
| Service | Role | Depends on |
|---|---|---|
| `db` | PostgreSQL | none |
| `backend` | FastAPI + agent | `db` |
| `ingest` | One-off job: loads jobs into the DB, then exits | `db`, `backend` |
| `frontend` | Next.js app | `db`, `backend`, `ingest` |
| `caddy` | HTTPS reverse proxy | `frontend` |

### 2. Setting Up Chrome Extension 
The job filling portion of the application requires installing the chrome extension. This involves adding the domain to `manifest.json` if you are editing locally or have a differnet domain setup



### 3. Browser certificate warning (optional)
 
Caddy signs its own certificate for `localhost`, so the browser shows "Your connection is not private." Click **Advanced → Proceed**, or trust Caddy's root certificate so the warning stops:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./root.crt
```

- **macOS:** double-click `caddy-root.crt` and add it to the System keychain. Then open it and set **Trust** to **Always Trust**.
- **Windows:** double-click it and choose **Install Certificate → Local Machine → Trusted Root Certification Authorities**.

### 4. Useful Commands to Know
These docker commands are useful to know
```bash
docker compose run --rm ingest       # refresh jobs (replaces the whole jobs table)
docker compose down                  # stop everything
docker compose down -v --rmi all     # remove everything: containers, volumes (DB data), images
```

## Option B: Run locally (development)
 
```bash
# 1. Database only
docker compose up -d db
 
# 2. Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd src/backend
alembic upgrade head
python -m app.ingest.sync_greenhouse          # load jobs (run once)
uvicorn app.api.main:app --reload --port 8000
# with debug tools:
DEBUG_TOOLS=1 uvicorn app.api.main:app --reload --port 8000
 
# 3. Frontend (new terminal)
cd src/frontend
npm install
npm run dev
```
 
Open **http://localhost:3000/chat**.

## Install the Chrome extension
 
1. Open `chrome://extensions` and turn on **Developer mode**.
2. Click **Load unpacked** and select `src/extension`.
3. The extension ID is fixed: `nkkmkjenpmkclkbephgefeajnomcfmgp`. The web app uses it to talk to the extension.
The extension only opens Greenhouse `https` tabs. Private values (email, phone, address, self-ID answers) go only to your browser, never to the model.


If you changed the `DOMAIN` environment variable, add the new domain to `externally_connectable.matches` in `src/extension/manifest.json`, then reload the extension. Otherwise the web app can't reach it:
 
```json
"externally_connectable": {
  "matches": ["https://localhost/*", "https://your-domain.com/*"]
}
```

## Usage
 
1. Open `/chat` and describe the job you want, e.g. *"Find me remote backend roles."*
2. Pick one or more jobs from the results. They form a queue.
3. Answer any questions the agent asks that your profile doesn't cover.
4. Review the draft: **approve**, **request changes**, or **skip**.
5. After you approve, the fill card in chat opens the Greenhouse form in a new tab and fills it in while you watch.
6. Check the form, fix anything, and press **Submit** yourself.
7. Click **"I submitted it"** (or **"Skip this job"**) in chat. The queue moves to the next job.


## Help or Troubleshoot
### Database migrations Commands
 
Run these from `src/backend`. DB credentials: user `agent`, password `agent`, database `agent`.
 
```bash
alembic upgrade head                                  # apply migrations / set up a new DB
alembic revision --autogenerate -m "describe change"  # create a migration after model changes
alembic upgrade head                                  # apply it
```

