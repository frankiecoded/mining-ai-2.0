import logging
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any

logger = logging.getLogger("ai_os.research.search_client")

def duckduckgo_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Performs a live web search by scraping DuckDuckGo's HTML search interface.
    This provides real-time search results without requiring Serper API keys.
    """
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    params = {"q": query}
    
    results = []
    try:
        # Perform request with standard HTTP client
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.post(url, data=params, headers=headers)
            
        if response.status_code != 200:
            logger.warning(f"DuckDuckGo HTML search returned status code {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # In DuckDuckGo HTML results, each result is usually in a div with class 'result'
        result_elements = soup.find_all("div", class_="result")
        for i, element in enumerate(result_elements):
            if len(results) >= limit:
                break
                
            title_tag = element.find("a", class_="result__url")
            snippet_tag = element.find("a", class_="result__snippet")
            
            if title_tag:
                title = title_tag.get_text(strip=True)
                href = title_tag.get("href", "")
                
                # Check for redirects/clean links
                # e.g., //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
                url_str = href
                if "uddg=" in href:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(href)
                    queries = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in queries:
                        url_str = queries["uddg"][0]
                
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                
                results.append({
                    "title": title,
                    "url": url_str,
                    "snippet": snippet,
                    "score": 1.0 - (i * 0.05)
                })
                
        logger.info(f"Scraped {len(results)} live search results from DuckDuckGo.")
    except Exception as e:
        logger.error(f"Error scraping DuckDuckGo: {e}")
        
    return results
