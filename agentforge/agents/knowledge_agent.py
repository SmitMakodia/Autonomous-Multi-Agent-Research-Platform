from agentforge.agents.base_agent import BaseAgent
from agentforge.tools.rag_tools import RAGTools
from crewai import Agent

class KnowledgeAgent(BaseAgent):
    def create(self) -> Agent:
        tools = [
            RAGTools.search_knowledge_base
        ]
        return self.create_agent("knowledge", tools=tools)
