import json
import httpx
from pydantic import BaseModel
from typing import List, Dict, Any
from .tool_schemas import TOOL_SCHEMAS
from config import LLAMA_SERVER_URL, LLM_MODEL
class ToolCall(BaseModel):
    name: str
    arguments: Dict[str, Any]
class ToolCallPlan(BaseModel):
    tools: List[ToolCall]
async def route_prompt(history: List[Dict[str, str]]) -> ToolCallPlan:
    system_prompt = (
        "You are the AgentForge MCP Router. Your ONLY job is to analyze the user's input and decide which tools to call. "
        "You have access to tools for web searching, scraping URLs, reading files, and OCR. "
        "Rules: "
        "1. If the user asks a factual question, asks about a specific entity (e.g., 'What is Nvidia', 'Who is the president'), or asks for news, you MUST call the 'web_search' tool with a relevant search query. "
        "2. If the user asks you to read or summarize a specific URL, you MUST call the 'web_scrape_url' tool. "
        "3. If the user asks about an uploaded file, use 'read_local_file' or 'ocr_image'. "
        "4. If it is a simple greeting ('Hello') or asking about your capabilities, do NOT call any tools. "
        "Return ONLY a valid JSON object containing the tool calls. Do not explain your reasoning."
    )
    
    messages = [{"role": "system", "content": system_prompt}] + history
    
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "tool_choice": "auto",
        "temperature": 0.0,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{LLAMA_SERVER_URL}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            tool_calls = data["choices"][0]["message"].get("tool_calls", [])
            plan = []
            for tc in tool_calls:
                func = tc["function"]
                plan.append(ToolCall(
                    name=func["name"],
                    arguments=json.loads(func["arguments"])
                ))
            return ToolCallPlan(tools=plan)
        except Exception as e:
            print(f"Tool routing failed: {e}")
            return ToolCallPlan(tools=[])