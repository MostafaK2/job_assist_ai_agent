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


    
