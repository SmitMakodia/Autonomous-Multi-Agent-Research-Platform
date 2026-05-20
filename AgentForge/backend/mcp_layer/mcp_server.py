import asyncio
from typing import List
from .tool_router import ToolCallPlan
from agents.agent_registry import agent_registry
from agents.base_agent import ContextChunk
async def execute_tool_plan(plan: ToolCallPlan) -> List[ContextChunk]:
    """
    Executes a tool call plan concurrently and gathers results.
    """
    tasks = []
    for tool_call in plan.tools:
        agent = agent_registry.get_agent(tool_call.name)
        if agent:
            tasks.append(agent.run(**tool_call.arguments))
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