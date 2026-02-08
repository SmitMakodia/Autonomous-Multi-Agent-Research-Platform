from crewai.tools import tool
from duckduckgo_search import DDGS
import wikipedia
import arxiv
from typing import List, Dict
import json

class SearchTools:
    
    @tool("Web Search")
    def search_web(query: str) -> str:
        """
        Search the web for current information using DuckDuckGo.
        Useful for finding recent events, news, and general information.
        """
        try:
            with DDGS() as ddgs:
                # Try text search first
                results = list(ddgs.text(query, max_results=5))
                
                # Fallback to news if text is empty (common with DDG rate limiting)
                if not results:
                    results = list(ddgs.news(query, max_results=5))
                
                if not results:
                    return "No results found."
                return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error searching web: {str(e)}"

    @tool("Wikipedia Search")
    def search_wikipedia(query: str) -> str:
        """
        Search Wikipedia for a topic.
        Useful for getting a comprehensive overview, history, and definitions.
        """
        try:
            wikipedia.set_lang("en")
            page_summary = wikipedia.summary(query, sentences=5)
            return page_summary
        except wikipedia.exceptions.DisambiguationError as e:
            return f"Ambiguous term. Possible options: {e.options[:5]}"
        except wikipedia.exceptions.PageError:
            return "Page not found on Wikipedia."
        except Exception as e:
            return f"Error searching Wikipedia: {str(e)}"

    @tool("ArXiv Search")
    def search_arxiv(query: str) -> str:
        """
        Search ArXiv for academic papers.
        Useful for finding scientific research, technical papers, and deep dives.
        Returns a list of papers with titles, authors, and summaries.
        """
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=5,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for result in client.results(search):
                results.append({
                    "title": result.title,
                    "authors": [author.name for author in result.authors],
                    "published": result.published.strftime("%Y-%m-%d"),
                    "summary": result.summary,
                    "pdf_url": result.pdf_url
                })
            
            if not results:
                return "No academic papers found."
                
            return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error searching ArXiv: {str(e)}"
