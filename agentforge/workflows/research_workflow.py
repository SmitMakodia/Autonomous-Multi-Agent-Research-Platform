from crewai import Crew, Task, Process
from agentforge.agents.planner import PlannerAgent
from agentforge.agents.researcher import ResearcherAgent
from agentforge.agents.knowledge_agent import KnowledgeAgent
from agentforge.agents.critic import CriticAgent
from agentforge.monitoring.logger import get_logger

logger = get_logger("research_workflow")

class ResearchWorkflow:
    def __init__(self):
        import os
        os.environ["EMBEDDINGS_OLLAMA_MODEL_NAME"] = "nomic-embed-text"
        
        self.planner = PlannerAgent().create()
        self.researcher = ResearcherAgent().create()
        self.knowledge = KnowledgeAgent().create()
        self.critic = CriticAgent().create()

    def run(self, topic: str, use_knowledge_base: bool = True, reset_memory: bool = False):
        logger.info("starting_research_workflow", topic=topic, use_knowledge_base=use_knowledge_base, reset_memory=reset_memory)
        
        if reset_memory:
            import shutil
            import os
            import gc
            import time
            
            gc.collect()
            
            def clear_dir(dir_path):
                if os.path.exists(dir_path):
                    for _ in range(3):
                        try:
                            shutil.rmtree(dir_path)
                            logger.info("memory_cleared", path=dir_path)
                            return
                        except Exception as e:
                            logger.warning("memory_clear_retry", path=dir_path, error=str(e))
                            time.sleep(1)
                    logger.error("memory_clear_failed_final", path=dir_path)

            clear_dir("data")
            
            clear_dir("agentforge/data/vectordb")
            
            if os.path.exists("agentforge/data/episodic_memory.db"):
                try:
                    os.remove("agentforge/data/episodic_memory.db")
                    logger.info("episodic_memory_cleared")
                except Exception as e:
                    logger.error("episodic_memory_clear_failed", error=str(e))

        plan_task = Task(
            description=f"""
            Analyze the research request: '{topic}'.
            Break this down into 3-5 distinct, actionable research steps.
            Identify what information needs to be gathered from the web{' vs internal knowledge base' if use_knowledge_base else ''}.
            Output a clear, numbered execution plan.
            """,
            agent=self.planner,
            expected_output="A structured research plan with specific subtasks."
        )

        research_task = Task(
            description=f"""
            Follow the research plan to gather external information on: '{topic}'.
            Use web search, Wikipedia, and ArXiv tools.
            Focus on finding recent data, statistics, and academic references.
            If you find a specific URL that looks promising, use the scraper tool to read it.
            Summarize findings with citations.
            """,
            agent=self.researcher,
            context=[plan_task],
            expected_output="Detailed external research findings with source URLs."
        )

        agents = [self.planner, self.researcher]
        tasks = [plan_task, research_task]
        context_for_synthesis = [plan_task, research_task]

        if use_knowledge_base:
            knowledge_task = Task(
                description=f"""
                Based on the research plan, search the internal knowledge base for '{topic}'.
                Retrieve relevant context, historical data, or proprietary information.
                Provide specific excerpts and document references.
                """,
                agent=self.knowledge,
                context=[plan_task],
                expected_output="Internal knowledge base findings with document references."
            )
            agents.append(self.knowledge)
            tasks.append(knowledge_task)
            context_for_synthesis.append(knowledge_task)

        synthesis_task = Task(
            description=f"""
            Synthesize all gathered information into a comprehensive report on '{topic}'.
            
            Structure:
            1. Executive Summary
            2. Detailed Analysis (combine external{' and internal' if use_knowledge_base else ''} findings)
            3. Key Insights & Trends
            4. Conclusion
            5. References/Bibliography
            
            Quality Checks:
            - Ensure every claim is cited.
            - Highlight any contradictions between sources.
            - Maintain a professional, objective tone.
            """,
            agent=self.critic,
            context=context_for_synthesis,
            expected_output="A professional markdown research report."
        )
        
        agents.append(self.critic)
        tasks.append(synthesis_task)

        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=Process.sequential,
            memory=not reset_memory,
            embedder={
                "provider": "ollama",
                "config": {
                    "model": "nomic-embed-text"
                }
            }
        )

        result = crew.kickoff()
        logger.info("workflow_completed", result_length=len(str(result)))
        return result