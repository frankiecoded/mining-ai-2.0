"""
Web Scraper Service for Live Market Prices
Scrapes gold, precious metals, and gemstone prices from multiple sources.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import hashlib

logger = logging.getLogger("ai_os.market_scraper")


@dataclass
class MarketPrice:
    """Represents a market price data point."""
    commodity: str
    price_usd: float
    unit: str
    source: str
    timestamp: datetime
    change_24h_percent: Optional[float] = None
    change_7d_percent: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commodity": self.commodity,
            "price_usd": self.price_usd,
            "unit": self.unit,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "change_24h_percent": self.change_24h_percent,
            "change_7d_percent": self.change_7d_percent,
            "metadata": self.metadata,
        }


@dataclass
class MarketCache:
    """In-memory cache for market prices."""
    prices: Dict[str, MarketPrice] = field(default_factory=dict)
    last_update: Optional[datetime] = None
    ttl_seconds: int = 300  # 5 minutes

    def is_stale(self) -> bool:
        if not self.last_update:
            return True
        return (datetime.utcnow() - self.last_update).total_seconds() > self.ttl_seconds

    def get(self, key: str) -> Optional[MarketPrice]:
        if self.is_stale():
            return None
        return self.prices.get(key)

    def set(self, key: str, price: MarketPrice):
        self.prices[key] = price
        self.last_update = datetime.utcnow()


class MarketScraperService:
    """
    Scrapes live market prices for gold, precious metals, and gemstones.
    Uses httpx for async HTTP requests with retry logic and caching.
    """

    SOURCES = {
        "metals": [
            {"name": "kitco", "url": "https://www.kitco.com/market/", "parser": "kitco"},
            {"name": "goldprice", "url": "https://goldprice.org/", "parser": "goldprice"},
            {"name": "bullionbypost", "url": "https://www.bullionbypost.com/gold-price/", "parser": "bullionbypost"},
        ],
        "gemstones": [
            {"name": "gemguide", "url": "https://www.gemguide.com/", "parser": "gemguide"},
            {"name": "rapaport", "url": "https://www.rapaport.com/", "parser": "rapaport"},
        ],
    }

    COMMODITY_MAPPINGS = {
        "gold": {"name": "Gold", "unit": "USD/oz"},
        "silver": {"name": "Silver", "unit": "USD/oz"},
        "platinum": {"name": "Platinum", "unit": "USD/oz"},
        "palladium": {"name": "Palladium", "unit": "USD/oz"},
        "diamond_1ct_flawless": {"name": "Diamond 1ct IF D", "unit": "USD/carat"},
        "diamond_1ct_vs1": {"name": "Diamond 1ct VS1 G", "unit": "USD/carat"},
        "diamond_industrial": {"name": "Industrial Diamond", "unit": "USD/carat"},
        "tanzanite_aaa": {"name": "Tanzanite AAA", "unit": "USD/carat"},
        "ruby_pigeon_blood": {"name": "Ruby Pigeon Blood", "unit": "USD/carat"},
        "emerald_fine": {"name": "Emerald Fine", "unit": "USD/carat"},
        "tsavorite_vivid": {"name": "Tsavorite Vivid Green", "unit": "USD/carat"},
    }

    FALLBACK_PRICES = {
        "gold": 2485.50,
        "silver": 31.45,
        "platinum": 1025.30,
        "palladium": 1180.50,
        "diamond_1ct_flawless": 15000.00,
        "diamond_1ct_vs1": 6500.00,
        "diamond_industrial": 15.00,
        "tanzanite_aaa": 1500.00,
        "ruby_pigeon_blood": 25000.00,
        "emerald_fine": 15000.00,
        "tsavorite_vivid": 8000.00,
    }

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.cache = MarketCache()
        self.scrape_history: List[Dict[str, Any]] = []
        self._http_client = None

    async def _get_http_client(self):
        """Lazy init httpx async client."""
        if self._http_client is None:
            try:
                import httpx
                self._http_client = httpx.AsyncClient(
                    timeout=30.0,
                    follow_redirects=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; AIOS-MarketScraper/1.0)",
                        "Accept": "text/html,application/json",
                    },
                )
            except ImportError:
                logger.warning("httpx not installed; using mock data")
                self.use_mock = True
                return None
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _mock_prices(self) -> Dict[str, MarketPrice]:
        """Generate realistic mock prices with slight variations."""
        import random
        now = datetime.utcnow()
        prices = {}

        for commodity, base_price in self.FALLBACK_PRICES.items():
            variation = random.uniform(-0.02, 0.02)  # ±2% variation
            mock_price = round(base_price * (1 + variation), 2)
            change_24h = round(random.uniform(-3.0, 3.0), 2)
            change_7d = round(random.uniform(-5.0, 5.0), 2)

            info = self.COMMODITY_MAPPINGS.get(commodity, {"name": commodity, "unit": "USD"})
            prices[commodity] = MarketPrice(
                commodity=commodity,
                price_usd=mock_price,
                unit=info["unit"],
                source="mock_fallback",
                timestamp=now,
                change_24h_percent=change_24h,
                change_7d_percent=change_7d,
                metadata={"info": info["name"]},
            )

        return prices

    async def _scrape_kitco(self) -> Dict[str, MarketPrice]:
        """Scrape Kitco for precious metals prices."""
        prices = {}
        now = datetime.utcnow()

        try:
            client = await self._get_http_client()
            if client is None:
                return prices

            response = await client.get(self.SOURCES["metals"][0]["url"])
            if response.status_code != 200:
                logger.warning(f"Kitco returned status {response.status_code}")
                return prices

            html = response.text

            # Parse gold price from HTML
            import re
            gold_match = re.search(r'gold.*?(\d{1,2},?\d{3}\.\d{2})', html, re.IGNORECASE)
            if gold_match:
                gold_price = float(gold_match.group(1).replace(",", ""))
                prices["gold"] = MarketPrice(
                    commodity="gold",
                    price_usd=gold_price,
                    unit="USD/oz",
                    source="kitco",
                    timestamp=now,
                )

            silver_match = re.search(r'silver.*?(\d{1,2}\.\d{2})', html, re.IGNORECASE)
            if silver_match:
                prices["silver"] = MarketPrice(
                    commodity="silver",
                    price_usd=float(silver_match.group(1)),
                    unit="USD/oz",
                    source="kitco",
                    timestamp=now,
                )

            platinum_match = re.search(r'platinum.*?(\d{1,3},?\d{3}\.\d{2})', html, re.IGNORECASE)
            if platinum_match:
                prices["platinum"] = MarketPrice(
                    commodity="platinum",
                    price_usd=float(platinum_match.group(1).replace(",", "")),
                    unit="USD/oz",
                    source="kitco",
                    timestamp=now,
                )

            palladium_match = re.search(r'palladium.*?(\d{1,3},?\d{3}\.\d{2})', html, re.IGNORECASE)
            if palladium_match:
                prices["palladium"] = MarketPrice(
                    commodity="palladium",
                    price_usd=float(palladium_match.group(1).replace(",", "")),
                    unit="USD/oz",
                    source="kitco",
                    timestamp=now,
                )

        except Exception as e:
            logger.error(f"Kitco scrape failed: {e}")

        return prices

    async def _scrape_goldprice(self) -> Dict[str, MarketPrice]:
        """Scrape goldprice.org for gold price."""
        prices = {}
        now = datetime.utcnow()

        try:
            client = await self._get_http_client()
            if client is None:
                return prices

            response = await client.get(self.SOURCES["metals"][1]["url"])
            if response.status_code != 200:
                return prices

            import re
            price_match = re.search(r'(\d{1,2},?\d{3}\.\d{2})', response.text)
            if price_match:
                prices["gold"] = MarketPrice(
                    commodity="gold",
                    price_usd=float(price_match.group(1).replace(",", "")),
                    unit="USD/oz",
                    source="goldprice.org",
                    timestamp=now,
                )

        except Exception as e:
            logger.error(f"goldprice.org scrape failed: {e}")

        return prices

    async def scrape_all(self) -> Dict[str, MarketPrice]:
        """
        Scrape all sources and return merged prices.
        Falls back to mock data if scraping fails.
        """
        all_prices: Dict[str, MarketPrice] = {}

        if self.use_mock:
            logger.info("Using mock market prices")
            all_prices = self._mock_prices()
            self.cache.prices.update(all_prices)
            self.cache.last_update = datetime.utcnow()
            return all_prices

        # Try each source, merge results (later sources override earlier)
        scrapers = [
            ("kitco", self._scrape_kitco),
            ("goldprice", self._scrape_goldprice),
        ]

        for name, scraper in scrapers:
            try:
                result = await scraper()
                all_prices.update(result)
                logger.info(f"Scraped {len(result)} prices from {name}")
            except Exception as e:
                logger.error(f"Scraper {name} failed: {e}")

        # If we got nothing, fall back to cached or mock
        if not all_prices:
            logger.warning("All scrapers failed; using fallback prices")
            all_prices = self._mock_prices()

        # Update cache
        self.cache.prices.update(all_prices)
        self.cache.last_update = datetime.utcnow()

        # Log scrape event
        self.scrape_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "prices_scraped": len(all_prices),
            "sources_tried": len(scrapers),
            "success": len(all_prices) > 0,
        })

        return all_prices

    async def get_gold_price(self) -> Optional[MarketPrice]:
        """Get current gold price from cache or scrape."""
        cached = self.cache.get("gold")
        if cached:
            return cached

        prices = await self.scrape_all()
        return prices.get("gold")

    async def get_all_prices(self) -> List[MarketPrice]:
        """Get all available prices."""
        prices = await self.scrape_all()
        return list(prices.values())

    async def get_price_comparison(self, commodity: str) -> Dict[str, Any]:
        """Compare price across different sources."""
        cached = self.cache.get(commodity)
        if cached and not self.cache.is_stale():
            return {
                "commodity": commodity,
                "current_price": cached.price_usd,
                "unit": cached.unit,
                "source": cached.source,
                "timestamp": cached.timestamp.isoformat(),
                "cache_age_seconds": (datetime.utcnow() - self.cache.last_update).total_seconds(),
            }

        prices = await self.scrape_all()
        target = prices.get(commodity)
        if target:
            return {
                "commodity": commodity,
                "current_price": target.price_usd,
                "unit": target.unit,
                "source": target.source,
                "timestamp": target.timestamp.isoformat(),
                "change_24h_percent": target.change_24h_percent,
                "change_7d_percent": target.change_7d_percent,
            }

        return {
            "commodity": commodity,
            "current_price": self.FALLBACK_PRICES.get(commodity, 0),
            "unit": self.COMMODITY_MAPPINGS.get(commodity, {}).get("unit", "USD"),
            "source": "fallback",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_market_summary(self) -> Dict[str, Any]:
        """Get a comprehensive market summary."""
        prices = await self.scrape_all()

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "metals": {},
            "gemstones": {},
            "alerts": [],
        }

        metals = ["gold", "silver", "platinum", "palladium"]
        gemstones = ["diamond_1ct_flawless", "tanzanite_aaa", "ruby_pigeon_blood", "emerald_fine", "tsavorite_vivid"]

        for m in metals:
            if m in prices:
                p = prices[m]
                summary["metals"][m] = {
                    "price": p.price_usd,
                    "unit": p.unit,
                    "change_24h": p.change_24h_percent,
                    "change_7d": p.change_7d_percent,
                }
                if p.change_24h_percent and abs(p.change_24h_percent) > 3:
                    summary["alerts"].append(f"{m.upper()} moved {p.change_24h_percent:+.1f}% in 24h")

        for g in gemstones:
            if g in prices:
                p = prices[g]
                summary["gemstones"][g] = {
                    "price": p.price_usd,
                    "unit": p.unit,
                }

        summary["gold_silver_ratio"] = (
            round(prices["gold"].price_usd / prices["silver"].price_usd, 1)
            if "gold" in prices and "silver" in prices and prices["silver"].price_usd > 0
            else None
        )

        return summary

    def get_scrape_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent scrape history."""
        return self.scrape_history[-limit:]


# Global singleton
_market_scraper: Optional[MarketScraperService] = None


def get_market_scraper(use_mock: bool = False) -> MarketScraperService:
    """Get or create the market scraper service singleton."""
    global _market_scraper
    if _market_scraper is None:
        _market_scraper = MarketScraperService(use_mock=use_mock)
    return _market_scraper
