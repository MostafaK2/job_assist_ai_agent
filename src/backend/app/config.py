import os
from pathlib import Path

from dotenv import load_dotenv

# Using the os.environ variable makes it so that the application fails if it does not exist

ROOT_DIR = Path(__file__).resolve().parents[3]   # app → backend → src → root
load_dotenv(ROOT_DIR / ".env")

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# SQLAlchemy format: postgresql+psycopg://user:password@host:port/dbname
APP_DATABASE_URL = os.environ["APP_DATABASE_URL"]


# --- Chat summarization (long chats get condensed for the agent; the user still sees everything) ---
# Summarize when the conversation reaches EITHER this many tokens or this many messages.
SUMMARY_TRIGGER_TOKENS = int(os.getenv("SUMMARY_TRIGGER_TOKENS", "12000"))
SUMMARY_TRIGGER_MESSAGES = int(os.getenv("SUMMARY_TRIGGER_MESSAGES", "80"))
# How many of the most recent messages stay word for word after summarizing.
SUMMARY_KEEP_MESSAGES = int(os.getenv("SUMMARY_KEEP_MESSAGES", "20"))
# How much of the old history the summarizer reads.
SUMMARY_TRIM_TOKENS = int(os.getenv("SUMMARY_TRIM_TOKENS", "6000"))
##### You don’t need to add anything to .env, because the defaults work. ADDD LATER

# After a summary the agent holds 1 summary + KEEP messages. If that's close to TRIGGER,
# the very next turn summarizes again. Each turn adds at least 2 (your message + the reply).
if SUMMARY_TRIGGER_MESSAGES - SUMMARY_KEEP_MESSAGES < 4:
    raise ValueError("SUMMARY_TRIGGER_MESSAGES must be at least SUMMARY_KEEP_MESSAGES + 4")
