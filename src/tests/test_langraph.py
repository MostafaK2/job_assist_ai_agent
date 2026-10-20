import os
from typing import TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

load_dotenv()
llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"))

class State(TypedDict):
    job_title: str
    verdict: str

def screen_job(state: State):
    msg = llm.invoke(f"In one line: is '{state['job_title']}' a plausible real job posting?")
    return {"verdict": msg.text}

graph = StateGraph(State)
graph.add_node("screen", screen_job)
graph.add_edge(START, "screen")
graph.add_edge("screen", END)
app = graph.compile()

print(app.invoke({"job_title": "Software Engineer Intern"}))