"""
Ultron Internet Learning Engine

Learns from the internet using working APIs:
- Wikipedia REST API (no key needed, structured JSON)
- DuckDuckGo Instant Answer API (no key, JSON summaries)
- Direct URL fetching for specific pages
- RSS/Atom feeds for news and updates

Stores learned knowledge locally and makes it available for recall.
"""

import re
import json
import time
import threading
import subprocess
import ssl
from pathlib import Path
from typing import Dict, List, Optional, Any
import urllib.request
import urllib.parse
from datetime import datetime

# Import action engine for real execution
from .action_engine import shell, http_get, http_post, file_write, file_read


# Shared SSL context (some systems have cert issues)
def create_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    return ctx


def fetch_json_data(url: str, timeout: int = 12) -> Optional[dict]:
    """Fetch JSON from a URL. Returns None on failure."""
    headers = {
        'User-Agent': 'Ultron/1.0 (Learning Engine; compatible)',
        'Accept': 'application/json',
    }
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=create_ssl_context()) as response:
            return json.loads(response.read().decode('utf-8', errors='ignore'))
    except Exception:
        return None


def fetch_text_content(url: str, timeout: int = 12) -> Optional[str]:
    """Fetch raw text/HTML from a URL. Returns None on failure."""
    headers = {
        'User-Agent': 'Ultron/1.0 (Learning Engine; compatible)',
        'Accept': 'text/html,application/xhtml+xml,text/plain,application/xml;q=0.9,*/*;q=0.8',
    }
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=create_ssl_context()) as response:
            data = response.read()
            # Handle gzip if needed
            if response.headers.get('Content-Encoding') == 'gzip':
                import gzip
                data = gzip.decompress(data)
            return data.decode('utf-8', errors='ignore')
    except Exception:
        return None


class InternetLearningEngine:
    """
    Internet learning engine using working APIs.
    Sources: Wikipedia, DuckDuckGo Instant Answers, direct URLs, RSS feeds.
    """

    def __init__(self):
        self.learning_directory = Path(__file__).parent.parent.parent / "data" / "learned_knowledge"
        self.learning_directory.mkdir(parents=True, exist_ok=True)
        self.knowledge_database = self.learning_directory / "knowledge.json"
        self.execution_log_file = self.learning_directory / "execution_log.jsonl"

        # Load existing knowledge
        self.knowledge_base = self._load_knowledge()

        # Active learning threads
        self.active_learning_threads = []
        self.is_running = True

        print(f"[INTERNET LEARNING] Engine initialized")
        print(f"[INTERNET LEARNING] Knowledge base: {len(self.knowledge_base.get('topics', {}))} topics loaded")

    def _load_knowledge(self) -> Dict[str, Any]: