import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from typing import List
from .base_agent import BaseAgent, ContextChunk
from crawl4ai import AsyncWebCrawler

class WebScrapeAgent(BaseAgent):
    name = "web_scrape_url"
    description = "Scrapes a given URL and returns the content as markdown using Crawl4AI."
    
    async def run(self, url: str, **kwargs) -> List[ContextChunk]:
        print(f"[WebScrapeAgent] Deep scraping URL via Crawl4AI: {url}")
        chunks = []
        
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
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(
                    url=url,
                    magic=True,
                    bypass_cache=True
                )
                if result.success and result.markdown:
                    markdown_content = result.markdown
                    chunks_text = make_chunks(markdown_content)
                    for text in chunks_text:
                        chunks.append(
                            ContextChunk(
                                text=text,
                                source=url,
                                agent_name=self.name,
                                relevance_score=1.0 
                            )
                        )
                    print(f"[WebScrapeAgent] Crawl4AI scraped {len(markdown_content)} characters from {url}")
                    return chunks
                else:
                    print(f"[WebScrapeAgent] Crawl4AI failed for {url}: {result.error_message}")
        except Exception as e:
            print(f"[WebScrapeAgent] Crawl4AI encountered an exception for {url}: {e}")

        # Fallback to BS4
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for element in soup(["script", "style", "nav", "footer", "header", "noscript", "aside"]):
                    element.decompose()
                
                markdown_content = md(str(soup.body if soup.body else soup), heading_style="ATX", strip=['a', 'img'])
                
                lines = [line.strip() for line in markdown_content.splitlines() if line.strip()]
                markdown_content = "\n".join(lines)
                
                if markdown_content:
                    chunks_text = make_chunks(markdown_content)
                    for text in chunks_text:
                        chunks.append(
                            ContextChunk(
                                text=text,
                                source=url,
                                agent_name=self.name,
                                relevance_score=1.0
                            )
                        )
                    print(f"[WebScrapeAgent] Fallback scraped {len(markdown_content)} characters from {url}")
                else:
                    print(f"[WebScrapeAgent] Extracted markdown is empty for {url}")
                    
            except Exception as e:
                print(f"[WebScrapeAgent] Failed to scrape {url}: {e}")
                
        return chunks