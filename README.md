# job_assist_agent

To run both:

# terminal 1, after the other chat adds the endpoint
cd src/backend && uvicorn app.api.main:app --reload --port 8000

# terminal 2
cd src/frontend && npm run dev