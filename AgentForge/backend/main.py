import logger_setup
import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import aiofiles
import uuid
from orchestrator import process_query
from config import UPLOADS_DIR
from agents.agent_registry import agent_registry
from fastapi.responses import JSONResponse, FileResponse

app = FastAPI(title="AgentForge Backend")

from llm.model_manager import model_manager

@app.on_event("startup")
async def startup_event():
    model_manager.start_llm()

@app.on_event("shutdown")
async def shutdown_event():
    model_manager.stop_llm()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOADS_DIR, exist_ok=True)
query_queues = {}

# Mount static and frontend files
app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")

@app.get("/")
async def root():
    return FileResponse("../frontend/index.html")

@app.get("/app.js")
async def get_app_js():
    return FileResponse("../frontend/app.js")

@app.get("/style.css")
async def get_style_css():
    return FileResponse("../frontend/style.css")

from typing import List

@app.post("/api/query")
async def handle_query(
    prompt: str = Form(...),
    session_id: str = Form(None),
    files: List[UploadFile] = File(None)
):
    if not session_id:
        session_id = str(uuid.uuid4())
    query_id = str(uuid.uuid4())
    
    saved_files = []
    if files:
        for file in files:
            if file.filename:
                file_path = os.path.join(UPLOADS_DIR, file.filename)
                async with aiofiles.open(file_path, 'wb') as out_file:
                    content = await file.read()
                    await out_file.write(content)
                saved_files.append({"path": file_path, "name": file.filename})
            
    query_queues[query_id] = {
        "session_id": session_id,
        "prompt": prompt,
        "files": saved_files
    }
    return JSONResponse(content={"query_id": query_id, "session_id": session_id})

@app.get("/api/stream/{query_id}")
async def stream_query(query_id: str):
    if query_id not in query_queues:
        raise HTTPException(status_code=404, detail="Query ID not found")
    data = query_queues.pop(query_id)
    async def event_generator():
        try:
            async for sse_event in process_query(
                data["session_id"], 
                data["prompt"],
                files=data.get("files", [])
            ):
                yield sse_event
        except Exception as e:
            yield '{"event": "error", "data": "' + str(e) + '"}\n'
    return EventSourceResponse(event_generator())
@app.get("/api/sessions")
async def get_sessions():
    from llm.memory_manager import memory_manager
    return JSONResponse(content={"sessions": memory_manager.get_sessions()})

@app.get("/api/sessions/{session_id}")
async def get_session_history(session_id: str):
    from llm.memory_manager import memory_manager
    messages = memory_manager.get_all_messages(session_id)
    return JSONResponse(content={"messages": messages})

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    from llm.memory_manager import memory_manager
    memory_manager.clear_session(session_id)
    return JSONResponse(content={"success": True})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=False)