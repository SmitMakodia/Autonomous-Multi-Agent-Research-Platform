from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agentforge.workflows.research_workflow import ResearchWorkflow
import uvicorn
import asyncio

app = FastAPI(title="AgentForge API")

class ResearchRequest(BaseModel):
    topic: str

@app.post("/research")
async def conduct_research(request: ResearchRequest):
    try:
        workflow = ResearchWorkflow()
        result = await asyncio.to_thread(workflow.run, request.topic)
        return {"result": str(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("agentforge.api.main:app", host="0.0.0.0", port=8000, reload=True)
