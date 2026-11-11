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