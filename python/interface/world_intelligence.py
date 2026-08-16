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


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

REFRESH_INTERVAL = 300  # 5 minutes
MAX_ITEMS_PER_FEED = 5
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

PROJECT_ROOT = Path(__file__).parent.parent.parent
WORLD_STATE_FILE = PROJECT_ROOT / "data" / "real_time_feeds" / "world_state.json"
WORLD_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


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

# Subreddits to monitor (via RSS - no auth needed)
REDDIT_FEEDS = [
    "technology", "artificial", "machinelearning",
    "cybersecurity", "programming", "worldnews",
]

# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class NewsItem:
    title: str
    source: str
    link: str = ""
    summary: str = ""
    published: str = ""
    category: str = "general"


@dataclass
class WorldState:
    """The current state of the world as Ultron sees it."""
    last_updated: float = 0.0
    news: List[Dict[str, str]] = field(default_factory=list)
    weather: Dict[str, Any] = field(default_factory=dict)
    crypto: Dict[str, Any] = field(default_factory=dict)
    trending_repos: List[Dict[str, str]] = field(default_factory=list)
    system_state: Dict[str, Any] = field(default_factory=dict)
    alerts: List[Dict[str, str]] = field(default_factory=list)
    reddit_pulse: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""  # LLM-generated summary of all feeds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_updated": self.last_updated,
            "last_updated_human": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_updated)),
            "news": self.news[:20],
            "weather": self.weather,
            "crypto": self.crypto,
            "trending_repos": self.trending_repos[:10],
            "system_state": self.system_state,
            "alerts": self.alerts,
            "reddit_pulse": self.reddit_pulse[:10],
            "summary": self.summary,
        }

    def to_context_string(self) -> str:
        """Compact string for injecting into LLM context."""
        parts = []
        if self.summary:
            parts.append(f"WORLD SUMMARY: {self.summary}")
        if self.weather:
            w = self.weather
            parts.append(f"WEATHER: {w.get('temperature', '?')}C, {w.get('description', '?')}, wind {w.get('wind_speed', '?')}km/h")
        if self.crypto:
            btc = self.crypto.get("bitcoin", {})
            eth = self.crypto.get("ethereum", {})
            parts.append(f"CRYPTO: BTC=${btc.get('usd', '?')} ({btc.get('change_24h', '?')}%), ETH=${eth.get('usd', '?')}")
        if self.alerts:
            parts.append(f"ALERTS: {'; '.join(a.get('title','') for a in self.alerts[:3])}")
        if self.news:
            top_3 = [n.get("title", "") for n in self.news[:3]]
            parts.append(f"TOP NEWS: {' | '.join(top_3)}")
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# FETCHERS — each pulls from a different free source
# ═══════════════════════════════════════════════════════════════

def _fetch_url(url: str, timeout: int = 10) -> Optional[str]:
    """Fetch URL content safely."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def fetch_rss_feeds() -> List[NewsItem]:
    """Fetch all RSS feeds in parallel using threads."""
    items: List[NewsItem] = []

    def _parse_feed(name: str, url: str):
        content = _fetch_url(url, timeout=8)
        if not content:
            return
        try:
            root = ET.fromstring(content)
            # Handle both RSS and Atom formats
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            # RSS 2.0
            for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                desc = item.findtext("description", "").strip()
                pub = item.findtext("pubDate", "").strip()
                if title:
                    # Strip HTML from description
                    desc = re.sub(r'<[^>]+>', '', desc)[:200]
                    items.append(NewsItem(
                        title=title, source=name, link=link,
                        summary=desc, published=pub,
                        category=_categorize(name),
                    ))

            # Atom format
            for entry in root.findall(".//atom:entry", ns)[:MAX_ITEMS_PER_FEED]:
                title = entry.findtext("atom:title", "", ns).strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                summary = entry.findtext("atom:summary", "", ns).strip()
                pub = entry.findtext("atom:published", "", ns).strip()
                if title:
                    summary = re.sub(r'<[^>]+>', '', summary)[:200]
                    items.append(NewsItem(
                        title=title, source=name, link=link,
                        summary=summary, published=pub,
                        category=_categorize(name),
                    ))
        except ET.ParseError:
            pass

    threads = []
    for name, url in RSS_FEEDS.items():
        t = threading.Thread(target=_parse_feed, args=(name, url), daemon=True)
        threads.append(t)
        t.start()

    # Reddit RSS
    for sub in REDDIT_FEEDS:
        url = f"https://www.reddit.com/r/{sub}/top/.rss?t=day&limit=3"
        t = threading.Thread(target=_parse_feed, args=(f"r/{sub}", url), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=12)

    return items


def fetch_weather() -> Dict[str, Any]:
    """Fetch weather from Open-Meteo (free, no API key)."""
    # First get approximate location from IP
    try:
        loc_data = _fetch_url("https://ipapi.co/json/", timeout=5)
        if loc_data:
            loc = json.loads(loc_data)
            lat = loc.get("latitude", 28.6)
            lon = loc.get("longitude", 77.2)
            city = loc.get("city", "Unknown")
        else:
            lat, lon, city = 28.6, 77.2, "Unknown"
    except Exception:
        lat, lon, city = 28.6, 77.2, "Unknown"

    # Get weather from Open-Meteo
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&hourly=temperature_2m,precipitation_probability"
    )
    data = _fetch_url(url, timeout=8)
    if not data:
        return {"error": "unavailable"}

    try:
        weather = json.loads(data)
        current = weather.get("current_weather", {})
        return {
            "city": city,
            "temperature": current.get("temperature"),
            "wind_speed": current.get("windspeed"),
            "wind_direction": current.get("winddirection"),
            "weather_code": current.get("weathercode"),
            "description": _weather_code_to_desc(current.get("weathercode", 0)),
            "is_day": current.get("is_day", 1),
        }
    except Exception:
        return {"error": "parse_failed"}


def fetch_crypto() -> Dict[str, Any]:
    """Fetch crypto prices from CoinGecko (free, no key)."""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin&vs_currencies=usd&include_24hr_change=true"
    data = _fetch_url(url, timeout=8)
    if not data:
        return {}
    try:
        prices = json.loads(data)
        result = {}
        for coin, info in prices.items():
            result[coin] = {
                "usd": info.get("usd"),
                "change_24h": round(info.get("usd_24h_change", 0), 2),
            }
        return result
    except Exception:
        return {}


def fetch_github_trending() -> List[Dict[str, str]]:
    """Fetch trending repos from GitHub (no auth needed for this endpoint)."""
    # Use the unofficial trending API via scraping the page
    url = "https://api.github.com/search/repositories?q=stars:>1000+pushed:>2024-01-01&sort=stars&order=desc&per_page=5"
    data = _fetch_url(url, timeout=8)
    if not data:
        return []
    try:
        repos = json.loads(data)
        results = []
        for repo in repos.get("items", [])[:5]:
            results.append({
                "name": repo.get("full_name", ""),
                "stars": repo.get("stargazers_count", 0),
                "description": (repo.get("description") or "")[:100],
                "language": repo.get("language", ""),
                "url": repo.get("html_url", ""),
            })
        return results
    except Exception:
        return []


def fetch_earthquake_alerts() -> List[Dict[str, str]]:
    """Fetch significant earthquake alerts from USGS."""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson"
    data = _fetch_url(url, timeout=8)
    if not data:
        return []
    try:
        quakes = json.loads(data)
        alerts = []
        for feature in quakes.get("features", [])[:5]:
            props = feature.get("properties", {})
            alerts.append({
                "title": props.get("title", "Unknown earthquake"),
                "magnitude": props.get("mag", 0),
                "place": props.get("place", ""),
                "time": props.get("time", 0),
                "alert_level": props.get("alert", "green"),
                "type": "earthquake",
            })
        return alerts
    except Exception:
        return []


def fetch_system_state() -> Dict[str, Any]:
    """Get current system state — battery, disk, network, CPU."""
    state = {}

    # Battery (macOS)
    try:
        batt = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r'(\d+)%', batt.stdout)
        if match:
            state["battery_percent"] = int(match.group(1))
        state["charging"] = "AC Power" in batt.stdout
    except Exception:
        state["battery_percent"] = -1

    # Disk usage
    try:
        df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = df.stdout.strip().split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            state["disk_used"] = parts[2] if len(parts) > 2 else "?"
            state["disk_available"] = parts[3] if len(parts) > 3 else "?"
            state["disk_percent"] = parts[4] if len(parts) > 4 else "?"
    except Exception:
        pass

    # Network connections
    try:
        net = subprocess.run(
            ["sh", "-c", "netstat -an 2>/dev/null | grep ESTABLISHED | wc -l"],
            capture_output=True, text=True, timeout=5
        )
        state["active_connections"] = int(net.stdout.strip())
    except Exception:
        state["active_connections"] = 0

    # Uptime
    try:
        up = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
        state["uptime"] = up.stdout.strip()
    except Exception:
        pass

    # Memory pressure (macOS)
    try:
        mem = subprocess.run(
            ["sh", "-c", "vm_stat | head -5"],
            capture_output=True, text=True, timeout=5
        )
        state["memory_info"] = mem.stdout.strip()[:200]
    except Exception:
        pass

    return state


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _categorize(source_name: str) -> str:
    """Categorize a news source."""
    tech = {"hacker_news", "techcrunch", "ars_technica", "r/technology", "r/programming"}
    ai = {"arxiv_ai", "r/artificial", "r/machinelearning"}
    security = {"krebs_security", "the_hacker_news", "r/cybersecurity"}
    science = {"nature", "science_daily", "nasa_breaking", "space_com"}
    world = {"bbc_world", "reuters_top", "al_jazeera", "r/worldnews"}

    if source_name in tech:
        return "technology"
    elif source_name in ai:
        return "ai_ml"
    elif source_name in security:
        return "security"
    elif source_name in science:
        return "science"
    elif source_name in world:
        return "world"
    return "general"


def _weather_code_to_desc(code: int) -> str:
    """Convert WMO weather code to description."""
    codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
    }
    return codes.get(code, f"Code {code}")


# ═══════════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════════

class WorldIntelligenceEngine:
    """
    Continuously monitors the world and maintains a live world model.
    Runs in background, refreshes every 5 minutes.
    """

    def __init__(self):
        self._state = WorldState()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._refresh_count = 0

        # Load cached state if exists
        self._load_cached_state()

    def start(self):
        """Start the world intelligence engine."""
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="WorldIntelligence"
        )
        self._thread.start()
        print("[WORLD-INTEL] Engine online — monitoring planet every 5 min")

    def stop(self):
        """Stop the engine."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_world_state(self) -> Dict[str, Any]:
        """Get current world state as dict."""
        with self._lock:
            return self._state.to_dict()

    def get_context_string(self) -> str:
        """Get compact context string for LLM injection."""
        with self._lock:
            return self._state.to_context_string()

    def get_news(self, category: str = None, limit: int = 10) -> List[Dict[str, str]]:
        """Get news, optionally filtered by category."""
        with self._lock:
            news = self._state.news
            if category:
                news = [n for n in news if n.get("category") == category]
            return news[:limit]

    def force_refresh(self):
        """Force an immediate refresh."""
        threading.Thread(target=self._refresh, daemon=True).start()

    # ═══════════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════════

    def _monitor_loop(self):
        """Background loop — refresh every REFRESH_INTERVAL seconds."""
        # First refresh immediately on start
        self._refresh()

        while self._running:
            time.sleep(REFRESH_INTERVAL)
            if self._running:
                self._refresh()

    def _refresh(self):
        """Pull all feeds and update world state."""
        self._refresh_count += 1
        start = time.time()

        try:
            # Fetch everything in parallel
            news_items = fetch_rss_feeds()
            weather = fetch_weather()
            crypto = fetch_crypto()
            trending = fetch_github_trending()
            alerts = fetch_earthquake_alerts()
            system = fetch_system_state()

            # Update state atomically
            with self._lock:
                self._state.last_updated = time.time()

                # Convert news items to dicts
                self._state.news = [
                    {
                        "title": item.title,
                        "source": item.source,
                        "link": item.link,
                        "summary": item.summary,
                        "category": item.category,
                    }
                    for item in news_items
                ]

                self._state.weather = weather
                self._state.crypto = crypto
                self._state.trending_repos = trending
                self._state.alerts = alerts
                self._state.system_state = system

                # Generate LLM summary of key events
                self._state.summary = self._generate_summary()

            # Persist to disk
            self._save_state()

            elapsed = time.time() - start
            news_count = len(news_items)
            print(f"[WORLD-INTEL] Refresh #{self._refresh_count} complete — "
                  f"{news_count} news items, {len(alerts)} alerts "
                  f"({elapsed:.1f}s)")

        except Exception as e:
            print(f"[WORLD-INTEL] Refresh error: {e}")

    def _generate_summary(self) -> str:
        """Generate a brief summary of the world state using LLM."""
        # Build a compact prompt from top items
        top_news = [n["title"] for n in self._state.news[:8]]
        weather = self._state.weather
        crypto = self._state.crypto

        prompt_parts = []
        if top_news:
            prompt_parts.append("Headlines: " + " | ".join(top_news))
        if weather and not weather.get("error"):
            prompt_parts.append(f"Weather: {weather.get('temperature')}C, {weather.get('description')}")
        if crypto:
            btc = crypto.get("bitcoin", {})
            prompt_parts.append(f"BTC: ${btc.get('usd', '?')} ({btc.get('change_24h', '?')}%)")

        if not prompt_parts:
            return "No data available yet."

        # Try local LLM for summary
        try:
            summary_prompt = (
                "Summarize the current world state in 2 sentences. Be direct, no filler:\n"
                + "\n".join(prompt_parts)
            )
            payload = json.dumps({
                "model": "qwen2.5:14b",
                "prompt": summary_prompt,
                "system": "You are a world-state summarizer. Be ultra-concise. 2 sentences max.",
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 100},
            }).encode()

            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                return result.get("response", "").strip()[:300]
        except Exception:
            # Fallback: just concatenate top 3 headlines
            return " | ".join(top_news[:3]) if top_news else "Monitoring..."

    def _save_state(self):
        """Save world state to disk."""
        try:
            WORLD_STATE_FILE.write_text(
                json.dumps(self._state.to_dict(), indent=2, default=str),
                encoding="utf-8"
            )
        except Exception:
            pass

    def _load_cached_state(self):
        """Load cached world state from disk."""
        try:
            if WORLD_STATE_FILE.exists():
                data = json.loads(WORLD_STATE_FILE.read_text())
                self._state.last_updated = data.get("last_updated", 0)
                self._state.news = data.get("news", [])
                self._state.weather = data.get("weather", {})
                self._state.crypto = data.get("crypto", {})
                self._state.summary = data.get("summary", "")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════

_global_engine: Optional[WorldIntelligenceEngine] = None


def get_world_intelligence() -> WorldIntelligenceEngine:
    """Get or create the global world intelligence engine."""
    global _global_engine
    if _global_engine is None:
        _global_engine = WorldIntelligenceEngine()
    return _global_engine
