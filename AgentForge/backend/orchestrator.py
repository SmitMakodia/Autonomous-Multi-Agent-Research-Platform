import asyncio
import json
import logging
import time
from typing import AsyncGenerator
from mcp_layer.tool_router import route_prompt
from mcp_layer.mcp_server import execute_tool_plan
from rag.vector_store import vector_store
from rag.retriever import retriever
from rag.context_builder import context_builder
from llm.memory_manager import memory_manager
from llm.llama_client import llama_client
import metrics
async def process_query(session_id: str, query: str, files: list = None, query_id: str = "") -> AsyncGenerator[str, None]:
    metrics.set_run(query_id=query_id, session_id=session_id)
    query_started = time.perf_counter()
    memory_manager.add_message(session_id, "user", query)

    if files:
        import os
        from mcp_layer.tool_router import ToolCallPlan, ToolCall
        from agents.agent_registry import agent_registry
        
        for file_info in files:
            file_path = file_info.get("path")
            filename = file_info.get("name")
            if file_path and filename:
                yield json.dumps({"event": "status", "data": f"Extracting context from {filename}..."})
                
                ext = os.path.splitext(filename)[1].lower()
                tool_name = "ocr_image" if ext in ['.png', '.jpg', '.jpeg', '.webp'] else "read_local_file"
                
                agent = agent_registry.get_agent(tool_name)
                if agent:
                    plan = ToolCallPlan(tools=[ToolCall(name=tool_name, arguments={"file_path": file_path})])
                    with metrics.stage("file_ingest", tool=tool_name, ext=ext) as f:
                        chunks = await execute_tool_plan(plan)
                        f["chunks"] = len(chunks)
                    if chunks:
                        with metrics.stage("index", source="file") as f:
                            vector_store.add_chunks(session_id, chunks)
                            f["chunks"] = len(chunks)
                        yield json.dumps({"event": "status", "data": f"Indexed {len(chunks)} chunks from {filename}."})

    yield json.dumps({"event": "status", "data": "Planning tool execution..."})

    history = memory_manager.get_history(session_id)
    with metrics.stage("route") as f:
        plan = await route_prompt(history)
        f["tools"] = [t.name for t in plan.tools]

    if plan.tools:
        yield json.dumps({"event": "status", "data": f"Executing tools: {[t.name for t in plan.tools]}..."})
        with metrics.stage("tools", tools=[t.name for t in plan.tools]) as f:
            chunks = await execute_tool_plan(plan)
            f["chunks"] = len(chunks)
        if chunks:
            yield json.dumps({"event": "status", "data": f"Gathered {len(chunks)} chunks. Indexing..."})
            with metrics.stage("index", source="tools") as f:
                vector_store.add_chunks(session_id, chunks)
                f["chunks"] = len(chunks)

    yield json.dumps({"event": "status", "data": "Retrieving context..."})
    with metrics.stage("retrieve", top_k=10) as f:
        top_chunks = retriever.retrieve_and_rerank(session_id, query, top_k=10)
        context_str = context_builder.build_context_string(top_chunks)
        f["chunks"] = len(top_chunks)
        f["context_chars"] = len(context_str)
    
    # Sizes only. Printing the assembled context, reasoning and answer in full teed every
    # scraped page and every uploaded document - including third-party PII - into
    # logs/log.log, which is append-only and never rotated.
    print(f"[{session_id}] Assembled RAG context: {len(top_chunks)} chunks, {len(context_str)} chars")
    
    system_prompt = (
        "You are AgentForge, an advanced Autonomous Multi-Agent Research & Analysis Platform. "
        "You orchestrate a swarm of specialized agents capable of web searching, scraping, OCR, and reading files to gather context and assist the user. "
        "Your primary goal is to provide accurate, comprehensive, and well-structured answers. "
        "When asked factual questions, rely heavily on the provided context. If the context lacks the necessary information, state clearly that the provided context does not contain the answer. "
        "Format your response cleanly using Markdown, employing bullet points, bold text, italics, notes, code snippets, and tables where appropriate to make it look beautiful. "
        "Do NOT use emojis unless mandatorily needed. "
        # The tag contract that used to live here (<think>.../<response>...) is gone. This
        # llama.cpp build splits the model's thinking out server-side into
        # reasoning_content, so asking for the tags as well made the model emit its answer
        # twice: once plainly and once wrapped in <response>. Keep the reasoning short,
        # and let the server do the splitting.
        "Keep your internal reasoning brief - one or two sentences - then give the answer directly. "
        "Do not prefix the answer with headers like 'Response:' or 'Final Answer:'.\n\n"
        f"--- CONTEXT ---\n{context_str}\n--- END CONTEXT ---"
    )
    
    messages = [{"role": "system", "content": system_prompt}] + history
    yield json.dumps({"event": "status", "data": "Generating response..."})
    full_response = ""
    full_reasoning = ""
    gen_started = time.perf_counter()
    ttft_ms = None
    first_answer_token_ms = None
    async for chunk_data in llama_client.generate_stream(messages):
        if ttft_ms is None:
            ttft_ms = round((time.perf_counter() - gen_started) * 1000, 2)
        if chunk_data["type"] == "reasoning":
            full_reasoning += chunk_data["content"]
            yield json.dumps({"event": "reasoning", "data": chunk_data["content"]})
        elif chunk_data["type"] == "content":
            if first_answer_token_ms is None:
                first_answer_token_ms = round((time.perf_counter() - gen_started) * 1000, 2)
            full_response += chunk_data["content"]
            yield json.dumps({"event": "token", "data": chunk_data["content"]})

    gen_ms = round((time.perf_counter() - gen_started) * 1000, 2)
    metrics.emit(
        "generate",
        duration_ms=gen_ms,
        # TTFT is time to the first streamed token of any kind; the model always opens
        # with <think>, so the first user-visible answer token lands later.
        ttft_ms=ttft_ms,
        first_answer_token_ms=first_answer_token_ms,
        reasoning_chars=len(full_reasoning),
        response_chars=len(full_response),
    )

    print(f"[{session_id}] Generated {len(full_reasoning)} chars reasoning, {len(full_response)} chars response")
    sources = list({c["metadata"]["source"] for c in top_chunks if "source" in c.get("metadata", {})})
    memory_manager.add_message(
        session_id, "assistant", full_response, full_reasoning,
        sources=json.dumps(sources), context=context_str
    )
    metrics.emit(
        "query_complete",
        duration_ms=round((time.perf_counter() - query_started) * 1000, 2),
        sources=len(sources),
    )
    yield json.dumps({"event": "done", "data": {"sources": sources, "context": context_str}})