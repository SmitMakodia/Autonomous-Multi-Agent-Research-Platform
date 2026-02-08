import sys
import os
import argparse

# Ensure path is set
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agentforge.workflows.research_workflow import ResearchWorkflow
from agentforge.workflows.evaluation import Evaluator

def run_evaluation(num_runs=1):
    print(f"Starting Evaluation Run (n={num_runs})...")
    
    test_topics = [
        "Impact of Quantum Computing on Cryptography",
        "Sustainable Energy Storage Solutions 2024",
        "AI Agents in Software Engineering"
    ]
    
    workflow = ResearchWorkflow()
    evaluator = Evaluator()
    results = []
    
    for i, topic in enumerate(test_topics[:num_runs]):
        print(f"
--- Running Test Case {i+1}: {topic} ---")
        try:
            output = str(workflow.run(topic))
            scores = evaluator.evaluate_output(output)
            print(f"Scores: {scores}")
            results.append(scores)
        except Exception as e:
            print(f"Error executing test case: {e}")
            
    if results:
        final_report = evaluator.generate_report(results)
        print("
" + "="*30)
        print(final_report)
        print("="*30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, help="Number of test cases to run")
    args = parser.parse_args()
    
    run_evaluation(args.runs)
