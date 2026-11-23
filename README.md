# Job Assist AI Agent
An AI agent that helps you apply for jobs. You describe the jobs you want. The agent finds matching Greenhouse postings and drafts your application answers. After you approve the draft, it fills in the real application form in your own Chrome tab. You press Submit yourself. The agent never submits.

Limitations right now:
- Job listings are stand-in data loaded by the ingest step at setup. Therefore job listing could be out of date.
- Onboarding (resume upload + profile questions at `/onboarding`) is not finished. Skip it.

## Table of Contents

- [Project Overview](#job-assist-ai-agent)
- [Tech Stack & Requirements](#tech-stackrequirements)
- [Configuration](#configuration)
- [Option A: Docker + Caddy Setup](#option-a-running-with-docker--caddy-recommended)
  - [Docker Commands](#1-docker-commands-to-run-the-project)
  - [Chrome Extension Setup](#2-setting-up-chrome-extension)
  - [Browser Certificate Warning](#3-browser-certificate-warning-optional)
  - [Useful Commands](#4-useful-commands-to-know)
- [Option B: Local Development Setup](#option-b-run-locally-development)
- [Option C: Linux Server Deployment](#option-c-deploy-on-a-linux-web-server-virtualbox)
- [Additional Information](#additional-information)
  - [Install Chrome Extension](#install-the-chrome-extension)
  - [Application Usage](#usage)
- [Help & Troubleshooting](#help-or-troubleshoot)
  - [Database Migrations](#database-migrations-commands)
  - [Extension Troubleshooting](#problems-with-extension-not-working)

## Tech stack/Requirements
 
- **Backend:** Python 3.12 / 3.13 (not 3.14, which breaks some dependencies), LangGraph + LangChain, Google Gemini (`langchain-google-genai`), FastAPI, SQLAlchemy + Alembic
- **Frontend:** Next.js 16 (JSX), Tailwind CSS, assistant-ui (Assistant Transport)
- **Extension:** Chrome MV3 (`src/extension`) 
- **Database:** PostgreSQL 16
- **Packaging:** Docker Compose + Caddy (HTTPS)
- **Browser:** Chrome (For extension to work)

Note: The extension is required for filling out the forms. 

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
DOMAIN=<CUSTOM_DOMAIN>
BIND_IP=<set to 127.0.0.1 for localhost>
DEFAULT_SNI=<set empty or ip-addr of server hosting>
```
Only `GOOGLE_API_KEY` is required. Change the model and summarization settings if you want to.

`localhost` in `APP_DATABASE_URL` is for local development. Inside Docker, the backend reaches the database at host `db`: `postgresql+psycopg://agent:agent@db:5432/agent`.

Note: `DEFAULT_SNI` can be set to none if you dont want to deploy and just want to run the application

For deployment in webserver, change `DOMAIN`, `BIND_IP`, `DEFAULT_SNI`.. More instruction -> [Click Here](#7-configure-env)

## Option A: Running with Docker + Caddy (recommended)
### 1. Docker commands to run the project

From the project's `root` directory run these docker commands to setup up frontend, backend, database and caddy. 
```bash
docker compose up -d --build
docker compose logs -f ingest   # Check jobs "SYNC SUMMARY"
docker compose ps -a            # verify if the services are running
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

In order for the manifest.json to recognize your new domains; add them in `manifest.json` in `src/extension`, like so: 

```json
"externally_connectable": {
  "matches": [
    "https://<CUSTOM_DOMAIN>/*",
    "https://<SERVER_IP>/*"
  ]
}
```

Then follow these steps in order: 

- Download or clone the git repo and locate src/extension
- In the url type: `chrome://extensions/` and turn on *Developer Mode*
- Click Load unpacked.
- Select the src/extension folder.


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
 
### 1. Setup Database
```bash
# 1. Database only
docker compose up -d db
```

### 2. Setup Backend

It is recommended to set up a virtual enviroment and install its requirements in the enviroment
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Then head over to `src/backend`, initialize database, perform the one time ingestion of jobs from predefined greenhouse jobs and run the backend application.
```bash
cd src/backend
alembic upgrade head
python -m app.ingest.sync_greenhouse          # load jobs (run once)
uvicorn app.api.main:app --reload --port 8000
```

(Optional) Run the backend application with `DEBUG_TOOLS=1` to check tool calls in the application
```bash
DEBUG_TOOLS=1 uvicorn app.api.main:app --reload --port 8000
```

### 3. Frontend (create a new terminal)
Now run the frontend 

```bash
cd src/frontend
npm install
npm run dev
```
 
Open **http://localhost:3000/chat** to start chatting with the AI Agent.

## Option C: Deploy on a Linux web server (VirtualBox)

Runs the Docker setup from Option A on an Ubuntu Server VM, so other machines on your network can reach the app.
### REQUIREMENTS
- **Virtual Box** 
- **Ubuntu Server** 

### 1. Check your network range (host machine)

```bash
ip addr     # your IP, e.g. inet 192.168.x.x
ip route    # your gateway and routes
```

Note the subnet. The VM will get an address in this range when it uses a bridged adapter.

### 2. Create the VM

1. Open VirtualBox and click **New**. Set the VM name, folder, and ISO image (**Ubuntu 26.04.1 live server amd64**).
2. Set a username and password (e.g. `vboxuser`). Use a strong password, not a default.
3. Set the hardware:

   | Setting | Value |
   |---|---|
   | Base memory | 4096 MB |
   | CPUs | 2 |
   | Virtual hard disk | 30 GB |

4. Click **Finish** and complete the Ubuntu install.

### 3. Configure networking

Go to **Settings → Network → Attached to** and pick one:

- **Bridged Adapter** (recommended): the VM gets its own IP on your LAN (e.g. `192.168.1.213`), reachable by other machines.
- **NAT Network**: the VM sits on a private network (e.g. `10.0.2.0/24`). Use this if you only need access from the host.

Click **OK** to save.

**Optional: SSH from the host (NAT Network only).** Saves a lot of time, since you can copy and paste into a real terminal.

1. **Tools → Network Manager → NAT Networks → RangeNet → Port Forwarding → +**
   - Name `ssh`, Protocol `TCP`, Host Port `2222`, Guest IP `10.0.2.200`, Guest Port `22`
2. From the host (PowerShell or terminal):
   ```bash
   ssh -p 2222 vboxuser@127.0.0.1
   ```

With a bridged adapter, skip port forwarding and run `ssh vboxuser@<VM_IP>`.

### 4. Verify the install (run on the server)

```bash
ip -4 a show enp0s3        # inet 10.0.2.200/24 (NAT) or 192.168.x.x/21 (bridged)
ip route                   # default via your gateway
ping -c2 google.com        # 2 received
systemctl is-active ssh    # active
sudo whoami                # root
df -h /                    # ~28 GB
```

If SSH is inactive:

```bash
sudo apt update && sudo apt install -y openssh-server
sudo systemctl enable --now ssh
systemctl is-active ssh    # active
```

### 5. Install Docker and open the firewall

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo systemctl enable docker
sudo ufw allow 22,80,443/tcp && sudo ufw enable     # answer y
exit                                                # log back in so the docker group applies
```

After logging back in verify that docker runs:

```bash
docker run --rm hello-world    # "Hello from Docker!"
docker compose version
```

### 6. Get the code

```bash
git clone https://github.com/MostafaK2/job_assist_ai_agent
cd job_assist_ai_agent
grep -n "tls internal" Caddyfile    # must show the line
```

### 7. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Edit these values:

```env
GOOGLE_API_KEY=<your real key>
POSTGRES_PASSWORD=<strong password>
APP_DATABASE_URL=postgresql+psycopg://agent:<same password>@db:5432/agent
DOMAIN=jobassist.range.test, <SERVER_IP>, <CUSTOM_DOMAIN>
BIND_IP=0.0.0.0
DEFAULT_SNI=<SERVER_IP>
```

- `DOMAIN` takes a comma-separated list. Include every name or IP users will type in the browser.
- `BIND_IP=0.0.0.0` lets other machines connect (the default `127.0.0.1` is local only).
- `DEFAULT_SNI` lets Caddy serve HTTPS when users browse by IP address, since browsers send no hostname in that case.

To save in nano: **Ctrl+O**, **Enter**, then **Ctrl+X**.

### 8. Allow the new addresses in the extension

```bash
nano src/extension/manifest.json
```

Add each domain and IP from `DOMAIN`:

```json
"externally_connectable": {
  "matches": [
    "https://localhost/*",
    "https://<CUSTOM_DOMAIN>/*",
    "https://<SERVER_IP>/*"
  ]
}
```

Without this, the web app can't talk to the extension. Each tester must load (or reload) this updated extension in Chrome.

### 9. Start everything

```bash
docker compose up -d --build
```

### 10. Check it's running

```bash
docker compose ps -a                 # db/backend/frontend/caddy healthy, ingest Exited (0)
docker compose logs ingest | tail    # SYNC SUMMARY
curl -k https://<SERVER_IP>/api/health
# or, by hostname:
curl -k --resolve jobassist.range.test:443:127.0.0.1 https://jobassist.range.test/api/health
```

### 11. Share the certificate with testers

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ~/root.crt
```

Copy `root.crt` to each tester's machine (e.g. `scp vboxuser@<SERVER_IP>:~/root.crt .`) and trust it as described in [Browser certificate warning](#3-browser-certificate-warning-optional).

### 12. Reaching the server by name

To use `jobassist.range.test` or a `CUSTOM DOMAIN` without public DNS, add a line to a tester's hosts file (`/etc/hosts` on macOS/Linux, `C:\Windows\System32\drivers\etc\hosts` on Windows):

```
<SERVER_IP>  jobassist.range.test
```

If you change `DOMAIN` or the server's IP later, update `.env` and `manifest.json`, then run `docker compose up -d` and reload the extension.

These should setup everything.

# Additional Information
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

### Problems with Extension not working

Make sure that your new ip address or domain is reflected in manifest.json, especially in `externally_connectable` in `matches` and add those hosts. If you are running locally, make sure your local ip address is reflected in the that array list. [Click Here for additional details](#install-the-chrome-extension)


Note unsolvable errors or issues: please email [mostafajunayed20@gmail.com](mailto:mostafajunayed20@gmail.com) or [mostafa.kamal@student.uml.edu](mailto:mostafa.kamal@student.uml.edu)
