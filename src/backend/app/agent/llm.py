from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import GEMINI_MODEL, GOOGLE_API_KEY


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.2,
    )