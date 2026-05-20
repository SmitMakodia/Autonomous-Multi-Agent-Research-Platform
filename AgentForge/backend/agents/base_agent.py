from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import time
class ContextChunk(BaseModel):
    text: str
    source: str
    agent_name: str
    relevance_score: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
class BaseAgent:
    name: str = "BaseAgent"
    description: str = "A base agent for the AgentForge system."
    async def run(self, query: str, **kwargs) -> List[ContextChunk]:
        """
        Executes the agent's core task and returns a list of context chunks.
        """
        raise NotImplementedError("Each agent must implement the run method.")