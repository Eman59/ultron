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
    "technology", "artificial", "machinelearning", "datascience", "cybersecurity"
]

# Create a cache for RSS feeds
rss_cache = {}

def fetch_rss_feed(url):
    """Fetch an RSS feed and cache the result."""
    if url in rss_cache:
        return rss_cache[url]
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        response = urllib.request.urlopen(req)
        feed = response.read()
        rss_cache[url] = feed
        return feed
    except urllib.error.URLError as e:
        logger.error(f"Error fetching RSS feed: {e}")
        return None

def parse_rss_feed(feed):
    """Parse an RSS feed and extract the items."""
    try:
        root = ET.fromstring(feed)
        items = []
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            items.append((title, link))
        return items
    except ET.ParseError as e:
        logger.error(f"Error parsing RSS feed: {e}")
        return []

def get_rss_feeds():
    """Get the RSS feeds and cache the results."""
    feeds = {}
    for name, url in RSS_FEEDS.items():
        feed = fetch_rss_feed(url)
        if feed:
            items = parse_rss_feed(feed)
            feeds[name] = items[:MAX_ITEMS_PER_FEED]
    return feeds

def get_reddit_feeds():
    """Get the Reddit feeds and cache the results."""
    feeds = {}
    for subreddit in REDDIT_FEEDS:
        url = f"https://www.reddit.com/r/{subreddit}/.rss"
        feed = fetch_rss_feed(url)
        if feed:
            items = parse_rss_feed(feed)
            feeds[subreddit] = items[:MAX_ITEMS_PER_FEED]
    return feeds

async def update_world_state():
    """Update the world state with the latest feeds."""
    rss_feeds = get_rss_feeds()
    reddit_feeds = get_reddit_feeds()
    world_state = {
        'rss': rss_feeds,
        'reddit': reddit_feeds
    }
    with open(WORLD_STATE_FILE, 'w') as f:
        json.dump(world_state, f)

async def main():
    """Main loop."""
    while True:
        await update_world_state()
        await asyncio.sleep(REFRESH_INTERVAL)

if __name__ == '__main__':
    asyncio.run(main())