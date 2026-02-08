from agentforge.agents.base_agent import BaseAgent
from crewai import Agent

class CriticAgent(BaseAgent):
    def create(self) -> Agent:
        return self.create_agent("critic", tools=[])
