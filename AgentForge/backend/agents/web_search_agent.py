import asyncio
from typing import List
from .base_agent import BaseAgent, ContextChunk
from net_guard import UnsafeURLError, assert_public_url
from crawl4ai import AsyncWebCrawler
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import httpx

class WebSearchAgent(BaseAgent):
    name = "web_search"
    description = "Searches the web using DuckDuckGo/Google and deeply scrapes the top results using Crawl4AI."
    
    async def run(self, query: str, **kwargs) -> List[ContextChunk]:
        print(f"[WebSearchAgent] Searching: {query}")
        
        def sync_search():
            chunks = []
            top_urls = []
            
            # Primary: DuckDuckGo (Reliable API-free search)
            try:
                try:
                    from ddgs import DDGS
                except ImportError:
                    from duckduckgo_search import DDGS
                ddgs = DDGS()
                print(f"[WebSearchAgent] Trying DuckDuckGo Search...")
                results = list(ddgs.text(query, max_results=3))
                for res in results:
                    content = f"Title: {res.get('title', '')}\nSnippet: {res.get('body', '')}"
                    chunks.append(
                        ContextChunk(
                            text=content,
                            source=res.get("href", "Search Result"),
                            agent_name=self.name,
                            relevance_score=0.8
                        )
                    )
                    top_urls.append(res.get("href"))
                
                if chunks:
                    print(f"[WebSearchAgent] Found {len(chunks)} search snippets from DuckDuckGo.")
                    return chunks, top_urls
                else:
                    raise Exception("DuckDuckGo returned 0 results.")
            except Exception as e:
                print(f"[WebSearchAgent] DuckDuckGo Search failed: {e}.")
            
            return chunks, []
            
        chunks, top_urls = await asyncio.to_thread(sync_search)
        
        if top_urls:
            print(f"[WebSearchAgent] Deep scraping top {len(top_urls)} URLs via Crawl4AI...")
            
            async def fetch_and_parse(url):
                scraped_chunks = []

                # Search results are third-party controlled, so these hrefs get the same
                # guard as an LLM-supplied URL.
                try:
                    assert_public_url(url)
                except UnsafeURLError as e:
                    print(f"[WebSearchAgent] Refused unsafe result URL {url!r}: {e}")
                    return scraped_chunks

                def make_chunks(text, max_size=2000):
                    c = []
                    paragraphs = text.split('\n\n')
                    curr = ""
                    for p in paragraphs:
                        if len(curr) + len(p) < max_size:
                            curr += p + "\n\n"
                        else:
                            if curr: c.append(curr.strip())
                            if len(p) >= max_size:
                                for i in range(0, len(p), max_size): c.append(p[i:i+max_size])
                                curr = ""
                            else:
                                curr = p + "\n\n"
                    if curr: c.append(curr.strip())
                    return c

                try:
                    # Pure Local Crawl4AI Scraping
                    async with AsyncWebCrawler(verbose=False) as crawler:
                        result = await crawler.arun(
                            url=url,
                            magic=True,
                            bypass_cache=True,
                            delay_before_return_html=1.5
                        )
                        if result.success and result.markdown:
                            markdown_content = result.markdown
                            chunks_text = make_chunks(markdown_content)
                            for text in chunks_text:
                                scraped_chunks.append(
                                    ContextChunk(
                                        text=text,
                                        source=url,
                                        agent_name=self.name,
                                        relevance_score=1.0 
                                    )
                                )
                            print(f"[WebSearchAgent] Crawl4AI scraped {len(markdown_content)} characters from {url}")
                            return scraped_chunks
                        else:
                            print(f"[WebSearchAgent] Crawl4AI failed for {url}: {result.error_message}")
                except Exception as e:
                    print(f"[WebSearchAgent] Crawl4AI encountered an exception for {url}: {e}")
                
                # Fallback to pure Python BS4
                try:
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "aside"]):
                            element.decompose()
                        markdown_content = md(str(soup.body if soup.body else soup), heading_style="ATX", strip=['a', 'img'])
                        lines = [line.strip() for line in markdown_content.splitlines() if line.strip()]
                        markdown_content = "\n".join(lines)
                        if markdown_content:
                            chunks_text = make_chunks(markdown_content)
                            for text in chunks_text:
                                scraped_chunks.append(
                                    ContextChunk(
                                        text=text,
                                        source=url,
                                        agent_name=self.name,
                                        relevance_score=0.9 
                                    )
                                )
                            print(f"[WebSearchAgent] BS4 Fallback scraped {len(markdown_content)} characters from {url}")
                except Exception as e:
                    print(f"[WebSearchAgent] BS4 Fallback scraper also failed for {url}: {e}")

                return scraped_chunks
                
            tasks = [fetch_and_parse(url) for url in top_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    chunks.extend(res)
                    
        return chunks
