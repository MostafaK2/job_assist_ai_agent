Database connection: 
    Username: agent
    pass: agent
    database: agent
    
Database migration steps (MUST RUN FROM )
    Initialization
        alembic xxxx
    Revision/Upgrade (once you made changes to a file)
        alembic revision --autogenerate -m "add companies jobs job_applications"

    Upgrading 
        alebic upgrade head

Ingestion Pipeline (replaces entire job section -- for now)
    python -m app.ingest.sync_greenhouse

