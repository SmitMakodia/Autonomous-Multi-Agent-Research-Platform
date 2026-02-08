from agentforge.agents.base_agent import BaseAgent
from agentforge.tools.search_tools import SearchTools
from agentforge.tools.scraper_tools import ScraperTools
from crewai import Agent

class ResearcherAgent(BaseAgent):
    def create(self) -> Agent:
        tools = [
            SearchTools.search_web,
            SearchTools.search_wikipedia,
            SearchTools.search_arxiv,
            ScraperTools.scrape_website
        ]
        return self.create_agent("researcher", tools=tools)