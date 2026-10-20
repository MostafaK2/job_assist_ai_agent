import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"))
print(llm.invoke("What is my name?").text)