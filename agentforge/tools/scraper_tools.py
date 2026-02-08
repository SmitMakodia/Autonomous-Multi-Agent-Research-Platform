import requests
from bs4 import BeautifulSoup
from crewai.tools import tool

class ScraperTools:
    @tool("Web Scraper")
    def scrape_website(url: str) -> str:
        """
        Scrape text content from a website URL.
        Useful for getting detailed information from a specific page.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            for script in soup(["script", "style"]):
                script.decompose()
                
            text = soup.get_text()
            
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text[:5000] + "..." if len(text) > 5000 else text
            
        except Exception as e:
            return f"Error scraping website: {str(e)}"
