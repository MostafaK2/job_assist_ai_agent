# Job Assist AI Agent
An AI Agent that helps you apply for jobs. Describe the type of jobs you wnat and the agent finds matching greenhouse postings, drafts application answers, asks for approval (TODO) and fills in the application form in a real browser (TODO)

Current Status: Phase 2 prototype drafts the application and asks user question contents it cant answer. (this phase would be fully automated and model would make inference later on unsure ones as well). User would be given the opporchunity to approve or not approve/revise. 

# Tech stack
- **Backend**: Python 3.12 / 3.13 (not 3.14, which breaks some dependencies), LangGraph + LangChain, Google Gemini (langchain-google-genai), FastAPI, SQLAlchemy + Alembic, Playwright
- **Frontend**: Next.js 16 (JavaScript/JSX), Tailwind CSS, assistant-ui (Assistant Transport)
- **Database**: PostgreSQL 16
- **Packaging**: Docker Compose

# Configuration
Create an .env file in the project root
``` .env
# BACKEND ENVIRONMENTS
GOOGLE_API_KEY=paste-your-key-here
GEMINI_MODEL=gemini-3.5-flash
APP_DATABASE_URL=postgresql+psycopg://agent:agent@localhost:5432/agent

# SUMMARY CONFIGURATION
# SUMMARY_TRIGGER_TOKENS=100
# SUMMARY_TRIGGER_MESSAGES=10
# SUMMARY_KEEP_MESSAGES=2
# SUMMARY_TRIM_TOKEN=50

# DEVELOPMENT
STAND_IN_JOB=andurilindustries/5217113007

# BELONGS TO DATABASE
POSTGRES_USER=agent
POSTGRES_PASSWORD=agent
POSTGRES_DB=agent

# BELONGS TO FRONTEND
BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK=false

# HTTPS (CADDY)
DOMAIN=localhost
BIND_IP=127.0.0.1
```

Keep everything the same but update GOOGLE_API_KEY with your own and feel free to update other configurations like models summarizations and other contents

# Getting Started
## Option A (Docker -- caddy + everything in containers)
``` bash
docker compose up --build
```
Then open https://localhost
This would be the webapp

(Optional) If you like to remove the not safe run the below command and follow the steps in the comment
```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
# macOS: double-click caddy-root.crt, add it to the System keychain, then open it and set “Trust” to Always Trust.
# Windows: double-click it, choose Install Certificate → Local Machine → Trusted Root Certification Authorities.
```

## Option B (Local Development)

``` bash
# 1. Database only run root folder (only spins up database)
docker compose up -d db

# 2. Backend 
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium 
cd src/backend
alembic upgrade head
uvicorn app.api.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd src/frontend
npm install
npm run dev
```
Open http://localhost:3000/chat to start chatting

# Using it
- (SKIP STEP) Go to /onboarding and upload your resume (PDF). Answer the profile questions. (Onboarding is completed yet )
- Open /chat and describe the job you want, e.g. "Find me remote backend roles. 
- Pick a job from the results.
- Answer any questions the agent asks that your profile doesn't cover.
- Review the full draft and reply approve.
- A browser window opens and the form fills in. Check it, then submit it yourself if you're happy with it. A screenshot is saved to src/backend/data/screenshots/.

Note: 
- Currently stand in fake listings are used
- Currently one application link is used to fetch and draft applications for every other jobs