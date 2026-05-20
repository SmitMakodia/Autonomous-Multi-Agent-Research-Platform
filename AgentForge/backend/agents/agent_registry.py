from typing import Dict, Type
from .base_agent import BaseAgent
from .web_search_agent import WebSearchAgent
from .web_scrape_agent import WebScrapeAgent
from .ocr_agent import OCRAgent
from .file_read_agent import FileReadAgent
class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self.register(WebSearchAgent())
        self.register(WebScrapeAgent())
        self.register(OCRAgent())
        self.register(FileReadAgent())
    def register(self, agent: BaseAgent):
        self._agents[agent.name] = agent
    def get_agent(self, name: str) -> BaseAgent:
        return self._agents.get(name)
agent_registry = AgentRegistry()