import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from research.search_client import duckduckgo_search

def test_duckduckgo_live_search():
    """
    Test executing live HTML search scraping against DuckDuckGo.
    """
    query = "copper mining industry updates 2026"
    results = duckduckgo_search(query, limit=3)
    
    assert isinstance(results, list)
    # Check shape of results if any are returned
    if len(results) > 0:
        first = results[0]
        assert "title" in first
        assert "url" in first
        assert "snippet" in first
        assert isinstance(first["title"], str)
        assert len(first["title"]) > 0
        assert first["url"].startswith("http")
