Backend Docker File (To build the image)
    - Builds a small python 3.13 image for the backend 
    - installs dependencies first
        - adds chromium only if playwrights is a dependency otherwise not
    - Creates working directory /code
        - Copies /src/backend into /code
    - Moves into the backend folder where alembic.ini and app/ are. 
    - Exposes port 8000 as the apps port
    - health check every 10 sec
    - Runs the startup script 
        - calls 'alembic upgrade head' runs any migration (updates and also creates new tables on fresh db if doesnt exists)
        - Executes the uvicorn starts the FastAPI app with port 8000 with proxy headers. 


Frontend Docker File (to build the image)
    This Dockerfile builds your Next.js frontend in three stages, so the final image holds only what’s needed to run it.

    1. deps
    Installs node_modules exactly as listed in package-lock.json (npm ci).
    This step is cached until the package files change.

    2. build
    Copies the code and runs npm run build.
    BACKEND_URL and NEXT_PUBLIC_USE_MOCK are set at build time. To change them you have to rebuild the image, not just restart the container.
    Makes sure a public/ folder exists so the final stage’s copy doesn’t fail.

    3. run
    Copies only Next.js’s standalone server, the static files and public/. This keeps the image small.
    Runs as the non-root node user on port 3000.
    Checks the home page regularly to confirm the app is working.
    Starts with node server.js.

    The standalone files only exist if next.config sets output: "standalone". Without it, the build stage won’t create .next/standalone and the image won’t build.


Docker compose spins up all of these services
The way the application works is that wihtout caddy, nextjs is handling api/* routing to the backend
    - Localhost:3000/api/* nextjs would route to localhost:8000/api/*
    - everything else would be frontend
    - Basically  Browser ──http──► Next.js :3000 ──http──► FastAPI :8000
                  (pages + forwards /api/*)


Caddy would take this out of nextjs hand and do this process itself. it sits on top of next js
    - Caddy is a small web server and reverse proxy: it sits in front of your app, receives every request, and passes it to the right container. What sets it apart is automatic HTTPS:
        - works with a real domain
        - localhost as well
    - basicllay: Browser ──https──► Caddy :443 ─┬─ /api/* ──http──► FastAPI :8000   (direct, no Node hop)
                                                └─ /*     ──http──► Next.js :3000

