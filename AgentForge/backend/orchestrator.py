import asyncio
import json
import logging
from typing import AsyncGenerator
from mcp_layer.tool_router import route_prompt
from mcp_layer.mcp_server import execute_tool_plan
from rag.vector_store import vector_store
from rag.retriever import retriever
from rag.context_builder import context_builder
from llm.memory_manager import memory_manager
from llm.llama_client import llama_client
async def process_query(session_id: str, query: str, files: list = None) -> AsyncGenerator[str, None]:
    memory_manager.add_message(session_id, "user", query)
    
    if files:
        import os
        from mcp_layer.tool_router import ToolCallPlan, ToolCall
        from agents.agent_registry import agent_registry
        
        for file_info in files:
            file_path = file_info.get("path")
            filename = file_info.get("name")
            if file_path and filename:
                yield json.dumps({"event": "status", "data": f"Extracting context from {filename}..."}) + "\n"
                
                ext = os.path.splitext(filename)[1].lower()
                tool_name = "ocr_image" if ext in ['.png', '.jpg', '.jpeg', '.webp'] else "read_local_file"
                
                agent = agent_registry.get_agent(tool_name)
                if agent:
                    plan = ToolCallPlan(tools=[ToolCall(name=tool_name, arguments={"file_path": file_path})])
                    chunks = await execute_tool_plan(plan)
                    if chunks:
                        vector_store.add_chunks(session_id, chunks)
                        yield json.dumps({"event": "status", "data": f"Indexed {len(chunks)} chunks from {filename}."}) + "\n"

    yield json.dumps({"event": "status", "data": "Planning tool execution..."}) + "\n"
    
    history = memory_manager.get_history(session_id)
    plan = await route_prompt(history)
    
    if plan.tools:
        yield json.dumps({"event": "status", "data": f"Executing tools: {[t.name for t in plan.tools]}..."}) + "\n"
        chunks = await execute_tool_plan(plan)
        if chunks:
            yield json.dumps({"event": "status", "data": f"Gathered {len(chunks)} chunks. Indexing..."}) + "\n"
            vector_store.add_chunks(session_id, chunks)
            
    yield json.dumps({"event": "status", "data": "Retrieving context..."}) + "\n"
    top_chunks = retriever.retrieve_and_rerank(session_id, query, top_k=10)
    context_str = context_builder.build_context_string(top_chunks)
    
    print(f"[{session_id}] Assembled RAG Context String:\n{context_str}\n")
    
    system_prompt = (
        "You are AgentForge, an advanced Autonomous Multi-Agent Research & Analysis Platform. "
        "You orchestrate a swarm of specialized agents capable of web searching, scraping, OCR, and reading files to gather context and assist the user. "
        "Your primary goal is to provide accurate, comprehensive, and well-structured answers. "
        "When asked factual questions, rely heavily on the provided context. If the context lacks the necessary information, state clearly that the provided context does not contain the answer. "
        "Format your response cleanly using Markdown, employing bullet points, bold text, italics, notes, code snippets, and tables where appropriate to make it look beautiful. "
        "Do NOT use emojis unless mandatorily needed. "
        "CRITICAL INSTRUCTION: You must strictly follow this exact 2-step format for EVERY single response:\n"
        "1. Start with `<think>` and write a very brief 1-2 sentence thought process, then close with `</think>`.\n"
        "2. Immediately after, open with `<response>` and write your beautifully formatted final Markdown answer, then close with `</response>`.\n"
        "Do not output anything outside of these two blocks. Do not use headers like 'Thought Process' or 'Response:'.\n\n"
        f"--- CONTEXT ---\n{context_str}\n--- END CONTEXT ---"
    )
    
    messages = [{"role": "system", "content": system_prompt}] + history
    yield json.dumps({"event": "status", "data": "Generating response..."}) + "\n"
    full_response = ""
    full_reasoning = ""
    async for chunk_data in llama_client.generate_stream(messages):
        if chunk_data["type"] == "reasoning":
            full_reasoning += chunk_data["content"]
            yield json.dumps({"event": "reasoning", "data": chunk_data["content"]}) + "\n"
        elif chunk_data["type"] == "content":
            full_response += chunk_data["content"]
            yield json.dumps({"event": "token", "data": chunk_data["content"]}) + "\n"
    
    print(f"[{session_id}] Generated Reasoning:\n{full_reasoning}\n")
    print(f"[{session_id}] Generated Response:\n{full_response}\n")
    sources = list({c["metadata"]["source"] for c in top_chunks if "source" in c.get("metadata", {})})
    memory_manager.add_message(
        session_id, "assistant", full_response, full_reasoning,
        sources=json.dumps(sources), context=context_str
    )
    yield json.dumps({"event": "done", "data": {"sources": sources, "context": context_str}}) + "\n"