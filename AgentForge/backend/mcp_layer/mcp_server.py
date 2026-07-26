import asyncio
from typing import List
from .tool_router import ToolCallPlan
from agents.agent_registry import agent_registry
from agents.base_agent import ContextChunk
import metrics


async def _run_timed(agent, tool_call) -> List[ContextChunk]:
    """Single choke point for per-agent timing - every tool dispatch passes through here."""
    with metrics.stage(f"agent.{tool_call.name}") as f:
        chunks = await agent.run(**tool_call.arguments)
        f["chunks"] = len(chunks) if isinstance(chunks, list) else 0
        return chunks


async def execute_tool_plan(plan: ToolCallPlan) -> List[ContextChunk]:
    """
    Executes a tool call plan concurrently and gathers results.
    """
    tasks = []
    for tool_call in plan.tools:
        agent = agent_registry.get_agent(tool_call.name)
        if agent:
            tasks.append(_run_timed(agent, tool_call))
        else:
            print(f"[MCP Server] No agent found for tool: {tool_call.name}")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_chunks = []
    for res in results:
        if isinstance(res, Exception):
            print(f"[MCP Server] Agent task failed: {res}")
        elif isinstance(res, list):
            all_chunks.extend(res)
    return all_chunks