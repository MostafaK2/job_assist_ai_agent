# job_assist_agent

To run both:

# terminal 1, after the other chat adds the endpoint
cd src/backend && uvicorn app.api.main:app --reload --port 8000

# terminal 2
cd src/frontend && npm run dev



Step 6: Remove the browser warning locally (optional)

Copy Caddy’s local root certificate out of the container and trust it on your machine:

bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
macOS: double-click caddy-root.crt, add it to the System keychain, then open it and set “Trust” to Always Trust.
Windows: double-click it, choose Install Certificate → Local Machine → Trusted Root Certification Authorities.

Restart your browser and the warning is gone. Don’t commit caddy-root.crt; add it to .gitignore.