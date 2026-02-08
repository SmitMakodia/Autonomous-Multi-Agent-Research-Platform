import json
import statistics
from typing import Dict, List, Any

class Evaluator:
    def __init__(self):
        pass

    def evaluate_output(self, output: str, criteria: List[str] = None) -> Dict[str, Any]:
        """
        Evaluate the research output based on basic heuristics.
        In a real scenario, this would use an LLM-as-a-Judge.
        """
        if criteria is None:
            criteria = ["citation_coverage", "completeness", "structure"]

        scores = {}
        
        citation_count = output.count("http") + output.count("[") 
        scores["citation_score"] = min(citation_count * 10, 100) 
        
        word_count = len(output.split())
        scores["completeness_score"] = min(word_count / 10, 100) 
        
        has_headers = output.count("#") > 3
        scores["structure_score"] = 100 if has_headers else 40

        scores["overall_score"] = statistics.mean(scores.values())
        
        return scores

    def generate_report(self, results: List[Dict]) -> str:
        avg_score = statistics.mean([r["overall_score"] for r in results])
        return f"Evaluation complete. Average Score: {avg_score:.2f}/100"
