Database connection: 
    Username: agent
    pass: agent
    database: agent
    
Database migration steps (MUST RUN FROM )
    Initialization (Sets up the database if you got none)
        alembic upgrade head
    Revision/Upgrade (once you made changes to a file)
        alembic revision --autogenerate -m "add companies jobs job_applications"

    Upgrading (If you edited the databse -- this applies the revision)
        alebic upgrade head

Ingestion Pipeline (replaces entire job section -- for now -- RUN THIS ONCE During initialization)
    python -m app.ingest.sync_greenhouse

    - Add this later in the docker entry point bash sciript to preload the jobs with random jobs from 10 different companies


In a real world settings that ingestion pipeline would be more sophisticated (this approach was chosen to )
