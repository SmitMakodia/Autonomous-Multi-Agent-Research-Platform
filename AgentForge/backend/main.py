import logger_setup
import json
import os
import time
from collections import OrderedDict
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import aiofiles
import uuid
from orchestrator import process_query
from config import UPLOADS_DIR
from paths import MAX_UPLOAD_BYTES, UnsafePathError, safe_upload_name
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

# AgentForge is a single-user local tool and has no authentication, so a wildcard origin
# with credentials would let any page the operator visits drive the whole API - enumerate
# sessions, read history, delete data, upload files.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOADS_DIR, exist_ok=True)

# Pending queries live here between POST /api/query and GET /api/stream/{id}. A client that
# never opens the stream used to leak its entry forever, so the map is bounded both ways.
MAX_PENDING_QUERIES = 64
PENDING_QUERY_TTL_SECONDS = 600
query_queues: "OrderedDict[str, dict]" = OrderedDict()


def _evict_stale_queries():
    now = time.monotonic()
    for query_id in [
        qid for qid, entry in query_queues.items()
        if now - entry["created_at"] > PENDING_QUERY_TTL_SECONDS
    ]:
        query_queues.pop(query_id, None)
    while len(query_queues) > MAX_PENDING_QUERIES:
        query_queues.popitem(last=False)

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
            if not file.filename:
                continue
            try:
                name = safe_upload_name(file.filename)
            except UnsafePathError as e:
                raise HTTPException(status_code=400, detail=str(e))

            file_path = os.path.join(UPLOADS_DIR, name)
            # Streamed with a running total: reading the whole body into memory first made
            # a multi-GB POST an OOM, and the cap has to be enforced during the write.
            written = 0
            try:
                async with aiofiles.open(file_path, 'wb') as out_file:
                    while chunk := await file.read(1024 * 1024):
                        written += len(chunk)
                        if written > MAX_UPLOAD_BYTES:
                            raise HTTPException(
                                status_code=413,
                                detail=f"{name} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB upload limit",
                            )
                        await out_file.write(chunk)
            except HTTPException:
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise

            saved_files.append({"path": file_path, "name": name})

    _evict_stale_queries()
    query_queues[query_id] = {
        "session_id": session_id,
        "prompt": prompt,
        "files": saved_files,
        "created_at": time.monotonic(),
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
                files=data.get("files", []),
                query_id=query_id,
            ):
                yield sse_event
        except Exception as e:
            # json.dumps, not concatenation: an exception message containing a quote or a
            # newline used to emit malformed JSON that the client's JSON.parse threw on.
            yield json.dumps({"event": "error", "data": str(e)})
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
    # Loopback only. There is no authentication on any endpoint, so a 0.0.0.0 bind exposed
    # session enumeration, history read, and session delete to the whole LAN.
    uvicorn.run("main:app", host="127.0.0.1", port=8081, reload=False)