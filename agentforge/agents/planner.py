from agentforge.agents.base_agent import BaseAgent
from crewai import Agent

class PlannerAgent(BaseAgent):
    def create(self) -> Agent:
        return self.create_agent("planner", tools=[])
