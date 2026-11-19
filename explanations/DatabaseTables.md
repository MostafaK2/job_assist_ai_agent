Column	Type	Notes
id	UUID, primary key	
email	text, unique	Stored lowercase
username	text, unique	
password_hash	text	Argon2 later; never the password itself
display_name	text, optional	
is_active	boolean, default true	Lets you disable an account without deleting it
created_at, updated_at, last_login_at	timestamps	

conversations: one row per chat in the sidebar:

Column	Type	Notes
id	UUID, primary key	This is also the agent’s thread_id, so one ID links everything
user_id	UUID → users.id, optional for now	Becomes required when login is added (see decision 2)
title	text	From your first message, like the sidebar does now
created_at / updated_at	timestamps	updated_at changes with each message, so the sidebar can sort by most recent
archived_at	timestamp, optional	Empty = not archived

chat_messages: the transcript:

Column	Type	Notes
id	auto-increment, primary key	Also gives the order
conversation_id	UUID → conversations.id, deleted with the conversation	
message_id	text	LangChain’s message ID; unique per conversation, so nothing is saved twice
role	text: user / assistant / tool	
content	JSONB	The full LangChain message, in the same format the chat screen already displays, so no conversion is needed
created_at	timestamp	


sqlalchemy	Defines our tables as Python classes and queries them
alembic	Creates and updates tables over time (Step 2)
psycopg[binary,pool]	The Postgres driver plus a connection pool; used by both SQLAlchemy and LangGraph
langgraph-checkpoint-postgres	Saves the agent’s memory in Postgres (Step 3)





## ------------------ ##
Companies 
    id, name, board_token, last_synced_at
    companies.append({
        "id": index,
        "name": company_name,
        "board_token": board_token,
        "last_synced_at": get_timestamp()
    })

jobs
    Structured job listing information (including descriptions and stuff)
    
    id, company_id, title, location, department, team, url, date_posted, updated_at, deadline, is_active
    description_html, description_text, raw_json, last_fetched_at

    job_record = {
        # Identification Information
        "job_id": raw_json.get("id"),
        "company_id": index,
        "company_name": company_name,
        "board_token": board_token,
        "location": raw_json.get("location", {}).get("name"),
        "title": raw_json.get("title"),


        # Timing information
        "date_posted": raw_json.get("first_published"),
        "updated_at": raw_json.get("updated_at"),
        "application_deadline": raw_json.get("application_deadline"),
        "last_fetched_at": get_timestamp(),
        
        # For later administrative use, 
        "requisition_id": raw_json.get("requisition_id"),
        "internal_job_id": raw_json.get("internal_job_id"),

        # internal usage only
        "is_active": True,

        ## ADDITONAL DETAILS WILL BE ADDED -- description_text will be fixed later on
        "description_html": raw_json.get("content", ""),
        "description_markdown": html_to_text(raw_json.get("content", ""), markdown=True),
        "departments": [dept.get("name") for dept in raw_json.get("departments", [])],
    }


    CREATE TABLE companies (
  id             SERIAL PRIMARY KEY,
  board_token    TEXT UNIQUE NOT NULL,
  name           TEXT NOT NULL,
  last_synced_at TIMESTAMPTZ,
  last_status    TEXT,          -- 'ok' / 'error: ...'
  last_job_count INT
);

CREATE TABLE jobs (
  company_id   INT    NOT NULL REFERENCES companies(id),
  job_id       BIGINT NOT NULL,            -- Greenhouse id
  title        TEXT   NOT NULL,
  location     TEXT,
  absolute_url TEXT   NOT NULL,
  departments  JSONB,
  date_posted  TIMESTAMPTZ,                -- first_published
  gh_updated_at TIMESTAMPTZ,
  application_deadline TIMESTAMPTZ,
  requisition_id TEXT, internal_job_id BIGINT,
  description_html TEXT, description_markdown TEXT, description_text TEXT,
  raw          JSONB,
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at     TIMESTAMPTZ,
  PRIMARY KEY (company_id, job_id)
);


