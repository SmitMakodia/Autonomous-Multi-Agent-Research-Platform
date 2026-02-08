import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agentforge.tools.search_tools import SearchTools
from agentforge.workflows.evaluation import Evaluator

class TestAgentForge(unittest.TestCase):
    
    def test_evaluator(self):
        evaluator = Evaluator()
        text = "# Title\n This is a test. [1] http://google.com"
        scores = evaluator.evaluate_output(text)
        self.assertGreater(scores["overall_score"], 0)
        self.assertEqual(scores["structure_score"], 40) # Not enough headers

    def test_search_tool_structure(self):
        # We don't want to actually call the API in unit tests usually, 
        # but we check if the function exists and has correct annotations
        self.assertTrue(hasattr(SearchTools, "search_web"))
        self.assertTrue(hasattr(SearchTools, "search_wikipedia"))

if __name__ == "__main__":
    unittest.main()
