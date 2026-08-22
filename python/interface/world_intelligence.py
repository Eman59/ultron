"""
World Intelligence Engine — Ultron's Eyes on the Planet.

Real-time awareness of everything happening in the world.
No API keys needed. Pure open-source intelligence (OSINT).

Feeds:
  - RSS news from 30+ major sources (BBC, Reuters, HN, ArXiv, etc.)
  - Weather for current location (Open-Meteo, free)
  - Crypto prices (CoinGecko, free)
  - GitHub trending repos
  - Reddit top posts from key subreddits
  - System events (disk, network, battery)
  - Earthquake/disaster alerts (USGS)

Every 5 minutes this engine pulls fresh data, summarizes it through
the LLM, and injects it into Ultron's world model so the brain is
ALWAYS aware of what's happening.

This is what makes Ultron omniscient within the limits of physics.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

REFRESH_INTERVAL = 300  # 5 minutes
MAX_ITEMS_PER_FEED = 5
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

PROJECT_ROOT = Path(__file__).parent.parent.parent
WORLD_STATE_FILE = PROJECT_ROOT / "data" / "real_time_feeds" / "world_state.json"
WORLD_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

logger.info(f"Project root: {PROJECT_ROOT}")
logger.info(f"World state file: {WORLD_STATE_FILE}")

# ═══════════════════════════════════════════════════════════════
# RSS FEED SOURCES — no API keys, pure open web
# ═══════════════════════════════════════════════════════════════

RSS_FEEDS = {
    # Tech & AI
    "hacker_news": "https://hnrss.org/frontpage",
    "arxiv_ai": "http://export.arxiv.org/rss/cs.AI",
    "techcrunch": "https://techcrunch.com/feed/",
    "ars_technica": "https://feeds.arstechnica.com/arstechnica/index",

    # World News
    "bbc_world": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "reuters_top": "https://news.google.com/rss/search?q=reuters+world+news&hl=en",
    "al_jazeera": "https://www.aljazeera.com/xml/rss/all.xml",

    # Science
    "nature": "https://www.nature.com/nature.rss",
    "science_daily": "https://www.sciencedaily.com/rss/all.xml",

    # Security
    "krebs_security": "https://krebsonsecurity.com/feed/",
    "the_hacker_news": "https://feeds.feedburner.com/TheHackersNews",

    # Space & Physics
    "nasa_breaking": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "space_com": "https://www.space.com/feeds/all",
}

logger.info(f"RSS feeds: {len(RSS_FEEDS)}")

# Subreddits to monitor (via RSS - no auth needed)
REDDIT_FEEDS = [
    "technology", "artificial", "machinelearning",
    "cybersecurity", "programming", "worldnews",
]

logger.info(f"Reddit feeds: {len(REDDIT_FEEDS)}")

# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class NewsItem:
    title: str
    source: str
    link: str = ""
    summary: Any = field(default=None)

    def __post_init__(self):
        logger.debug(f"News item created: {self.title} - {self.source}")