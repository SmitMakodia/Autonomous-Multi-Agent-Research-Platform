from crewai import Agent, LLM
from agentforge.config.config_loader import ConfigLoader
import os

class BaseAgent:
    def __init__(self):
        self.model_config = ConfigLoader.load_model_config()
        self.agent_config = ConfigLoader.load_agent_config()
        self.llm = self._setup_llm()

    def _setup_llm(self):
        llm_config = self.model_config.get("llm", {})
        model_name = llm_config.get("model", "qwen2.5:3b")
        
        if not model_name.startswith("ollama/"):
            model_name = f"ollama/{model_name}"

        return LLM(
            model=model_name,
            base_url=llm_config.get("base_url", "http://localhost:11434"),
            temperature=llm_config.get("temperature", 0.7)
        )

    def create_agent(self, agent_type: str, tools: list = None) -> Agent:
        if agent_type not in self.agent_config:
            raise ValueError(f"Agent type '{agent_type}' not found in configuration.")
        
        config = self.agent_config[agent_type]
        
        return Agent(
            role=config['role'],
            goal=config['goal'],
            backstory=config['backstory'],
            verbose=config.get('verbose', True),
            allow_delegation=config.get('allow_delegation', False),
            llm=self.llm,
            tools=tools or []
        )
