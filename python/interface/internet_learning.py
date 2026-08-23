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


# Shared SSL context
def _ssl_context():
    ctx = ssl.create_default_context()
    return ctx


def _fetch_json(url: str, timeout: int = 12) -> Optional[dict]:
    """Fetch JSON from a URL. Returns None on failure."""
    headers = {
        'User-Agent': 'Ultron/1.0 (Learning Engine; compatible)',
        'Accept': 'application/json',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode('utf-8', errors='ignore'))
    except Exception:
        return None


def _fetch_text(url: str, timeout: int = 12) -> Optional[str]:
    """Fetch raw text/HTML from a URL. Returns None on failure."""
    headers = {
        'User-Agent': 'Ultron/1.0 (Learning Engine; compatible)',
        'Accept': 'text/html,application/xhtml+xml,text/plain,application/xml;q=0.9,*/*;q=0.8',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            data = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
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
        self.learning_dir = Path(__file__).parent.parent.parent / "data" / "learned_knowledge"
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_db = self.learning_dir / "knowledge.json"
        self.execution_log = self.learning_dir / "execution_log.jsonl"

        # Load existing knowledge
        self.knowledge = self._load_knowledge()

        # Active learning threads
        self.active_threads = []
        self.running = True

        print(f"[INTERNET LEARNING] Engine initialized")
        print(f"[INTERNET LEARNING] Knowledge base: {len(self.knowledge.get('topics', {}))} topics loaded")

    def _load_knowledge(self) -> Dict[str, Any]:
        """Load existing knowledge from disk."""
        try:
            if self.knowledge_db.exists():
                with open(self.knowledge_db, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[INTERNET LEARNING] Error loading knowledge: {e}")
        return {"topics": {}, "commands": {}, "patterns": {}}

    def _save_knowledge(self):
        """Save knowledge to disk."""
        try:
            with open(self.knowledge_db, 'w') as f:
                json.dump(self.knowledge, f, indent=2)
        except Exception as e:
            print(f"[INTERNET LEARNING] Error saving knowledge: {e}")

    def _log_execution(self, command: str, result: str, success: bool):
        """Log command execution."""
        try:
            with open(self.execution_log, 'a') as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "command": command,
                    "result": result[:1000],
                    "success": success
                }
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # SOURCE 1: Wikipedia REST API
    # ═══════════════════════════════════════════════════════════════

    def _learn_from_wikipedia(self, topic: str) -> List[str]:
        """Query Wikipedia REST API for summary + key sections."""
        facts = []

        encoded = urllib.parse.quote(topic.replace(" ", "_"))
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        data = _fetch_json(summary_url)

        if data and data.get("extract"):
            extract = data["extract"]
            sentences = re.split(r'(?<=[.!?])\s+', extract)
            for s in sentences:
                s = s.strip()
                if len(s) > 20:
                    facts.append(s)

        # Search Wikipedia if direct title didn't match
        if not facts:
            search_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&list=search"
                f"&srsearch={urllib.parse.quote(topic)}&format=json&utf8=1&srlimit=3"
            )
            search_data = _fetch_json(search_url)
            if search_data:
                results = search_data.get("query", {}).get("search", [])
                for result in results[:3]:
                    snippet = result.get("snippet", "")
                    snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                    if snippet and len(snippet) > 20:
                        facts.append(snippet)
                    title = result.get("title", "")
                    if title and not facts:
                        encoded_title = urllib.parse.quote(title.replace(" ", "_"))
                        title_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
                        title_data = _fetch_json(title_url)
                        if title_data and title_data.get("extract"):
                            for s in re.split(r'(?<=[.!?])\s+', title_data["extract"]):
                                s = s.strip()
                                if len(s) > 20:
                                    facts.append(s)

        return facts[:25]

    # ═══════════════════════════════════════════════════════════════
    # SOURCE 2: DuckDuckGo Instant Answer API
    # ═══════════════════════════════════════════════════════════════

    def _learn_from_duckduckgo(self, topic: str) -> List[str]:
        """Query DuckDuckGo Instant Answer API."""
        facts = []

        url = (
            f"https://api.duckduckgo.com/?q={urllib.parse.quote(topic)}"
            f"&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        )
        data = _fetch_json(url)

        if not data:
            return facts

        # Abstract
        abstract = data.get("AbstractText", "")
        if abstract and len(abstract) > 20:
            sentences = re.split(r'(?<=[.!?])\s+', abstract)
            for s in sentences:
                s = s.strip()
                if len(s) > 20:
                    facts.append(s)

        # Related topics
        for topic_item in data.get("RelatedTopics", [])[:10]:
            text = topic_item.get("Text", "")
            if text and len(text) > 20:
                facts.append(text)
            if "Topics" in topic_item:
                for sub in topic_item["Topics"][:5]:
                    sub_text = sub.get("Text", "")
                    if sub_text and len(sub_text) > 20:
                        facts.append(sub_text)

        # Answer
        answer = data.get("Answer", "")
        if answer and len(str(answer)) > 5:
            facts.append(f"Direct answer: {answer}")

        # Definition
        definition = data.get("Definition", "")
        if definition and len(definition) > 20:
            facts.append(f"Definition: {definition}")

        # Infobox
        infobox = data.get("Infobox", {})
        if infobox and isinstance(infobox, dict):
            for item in infobox.get("content", [])[:10]:
                label = item.get("label", "")
                value = item.get("value", "")
                if label and value:
                    facts.append(f"{label}: {value}")

        return facts[:25]

    # ═══════════════════════════════════════════════════════════════
    # SOURCE 3: Direct URL fetching
    # ═══════════════════════════════════════════════════════════════

    def _learn_from_url(self, url: str, topic: str) -> List[str]:
        """Fetch and extract text from a specific URL."""
        html = _fetch_text(url)
        if not html:
            return []
        return self._extract_all_information(html, topic)[:30]

    # ═══════════════════════════════════════════════════════════════
    # SOURCE 4: RSS/Atom feeds
    # ═══════════════════════════════════════════════════════════════

    def _learn_from_rss(self, topic: str) -> List[str]:
        """Fetch relevant RSS feeds for tech/security topics."""
        facts = []

        feed_map = {
            "security": [
                "https://feeds.feedburner.com/TheHackersNews",
            ],
            "network": [
                "https://www.networkworld.com/category/networking/index.rss",
            ],
            "python": [
                "https://realpython.com/atom.xml",
            ],
        }

        topic_lower = topic.lower()
        target_feeds = []
        for keyword, feeds in feed_map.items():
            if keyword in topic_lower:
                target_feeds.extend(feeds)

        if not target_feeds:
            target_feeds = ["https://hnrss.org/newest?q=" + urllib.parse.quote(topic) + "&count=5"]

        for feed_url in target_feeds[:2]:
            xml = _fetch_text(feed_url, timeout=10)
            if not xml:
                continue

            titles = re.findall(r'<title[^>]*>(.*?)</title>', xml, re.DOTALL)
            descriptions = re.findall(r'<description[^>]*>(.*?)</description>', xml, re.DOTALL)
            summaries = re.findall(r'<summary[^>]*>(.*?)</summary>', xml, re.DOTALL)

            for text in (titles + descriptions + summaries)[:15]:
                text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if text and len(text) > 20 and self._is_relevant(text, topic):
                    facts.append(text)

        return facts[:15]

    # ═══════════════════════════════════════════════════════════════
    # MAIN LEARNING METHOD
    # ═══════════════════════════════════════════════════════════════

    def learn_from_web(self, topic: str, depth: int = 1, sources: List[str] = None) -> Dict[str, Any]:
        """
        Learn about a topic from multiple working sources.

        Args:
            topic: Topic to learn about
            depth: How deep to go (1=summaries, 2+=follow links)
            sources: Specific URLs to learn from (optional)

        Returns:
            Dictionary with learned knowledge and any extracted commands
        """
        print(f"[LEARNING] Researching: {topic}")

        all_facts = []
        sources_used = []

        # 1. Wikipedia
        wiki_facts = self._learn_from_wikipedia(topic)
        if wiki_facts:
            all_facts.extend(wiki_facts)
            sources_used.append("wikipedia")
            print(f"[LEARNING] Wikipedia: {len(wiki_facts)} facts")

        # 2. DuckDuckGo Instant Answers
        ddg_facts = self._learn_from_duckduckgo(topic)
        if ddg_facts:
            all_facts.extend(ddg_facts)
            sources_used.append("duckduckgo")
            print(f"[LEARNING] DuckDuckGo: {len(ddg_facts)} facts")

        # 3. RSS feeds
        rss_facts = self._learn_from_rss(topic)
        if rss_facts:
            all_facts.extend(rss_facts)
            sources_used.append("rss")
            print(f"[LEARNING] RSS feeds: {len(rss_facts)} facts")

        # 4. Direct URLs if specified
        if sources:
            for url in sources[:3]:
                url_facts = self._learn_from_url(url, topic)
                if url_facts:
                    all_facts.extend(url_facts)
                    sources_used.append(url)
                    print(f"[LEARNING] URL {url[:50]}: {len(url_facts)} facts")

        # Deduplicate
        seen = set()
        unique_facts = []
        for fact in all_facts:
            normalized = fact.lower().strip()[:100]
            if normalized not in seen:
                seen.add(normalized)
                unique_facts.append(fact)

        # Extract commands
        commands = self._generate_commands_safe(unique_facts)

        # Store knowledge
        self.knowledge["topics"][topic] = {
            "info": unique_facts[:50],
            "commands": commands,
            "learned_at": datetime.now().isoformat(),
            "sources": sources_used
        }

        self._save_knowledge()

        total_facts = len(unique_facts)
        total_commands = len(commands)
        print(f"[LEARNING] Total: {total_facts} facts, {total_commands} commands from {len(sources_used)} sources")

        return {
            "success": total_facts > 0,
            "topic": topic,
            "learned_facts": total_facts,
            "executable_commands": total_commands,
            "all_commands": list(commands.keys()),
            "sources_used": len(sources_used),
            "source_names": sources_used,
        }

    # ═══════════════════════════════════════════════════════════════
    # TEXT EXTRACTION
    # ═══════════════════════════════════════════════════════════════

    def _extract_all_information(self, html: str, topic: str) -> List[str]:
        """Extract relevant text from HTML content."""
        facts = []

        html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<nav.*?</nav>', '', html, flags=re.DOTALL)
        html = re.sub(r'<footer.*?</footer>', '', html, flags=re.DOTALL)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        list_items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)

        for text in (paragraphs + list_items):
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'&[a-z]+;', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()

            if text and len(text) > 30 and self._is_relevant(text, topic):
                facts.append(text)
                if len(facts) >= 50:
                    break

        return facts

    def _extract_information(self, html: str, topic: str) -> List[str]:
        """Legacy method."""
        return self._extract_all_information(html, topic)

    def _is_relevant(self, text: str, topic: str) -> bool:
        """Check if text is relevant to the topic."""
        topic_words = set(topic.lower().split())
        text_lower = text.lower()

        for word in topic_words:
            if len(word) > 3 and word in text_lower:
                return True

        if topic.lower() in text_lower:
            return True

        if len(text) > 100:
            return True

        return False

    # ═══════════════════════════════════════════════════════════════
    # COMMAND EXTRACTION
    # ═══════════════════════════════════════════════════════════════

    def _generate_commands_safe(self, facts: List[str]) -> Dict[str, str]:
        """Extract commands mentioned in learned facts."""
        commands = {}

        command_patterns = [
            (r'(pip install \S+)', 'pip_install'),
            (r'(npm install \S+)', 'npm_install'),
            (r'(brew install \S+)', 'brew_install'),
            (r'(apt-get install \S+)', 'apt_install'),
            (r'(apt install \S+)', 'apt_install'),
            (r'(curl\s+-[sS]?\s*\S+)', 'curl'),
            (r'(wget\s+\S+)', 'wget'),
            (r'`([^`]{5,80})`', 'code_snippet'),
            (r'(?:command|run|execute|use):\s*[`"]?(\S[^`"]{3,80})[`"]?', 'labeled'),
        ]

        for fact in facts:
            for pattern, cmd_type in command_patterns:
                matches = re.findall(pattern, fact, re.IGNORECASE)
                for match in matches:
                    cmd = match.strip() if isinstance(match, str) else match[0].strip()
                    cmd = re.sub(r'[.;,]$', '', cmd)

                    if len(cmd) < 4 or ' is ' in cmd or ' the ' in cmd:
                        continue

                    cmd_id = f"{cmd_type}_{len(commands)}"
                    commands[cmd_id] = cmd

                    if len(commands) >= 20:
                        return commands

        return commands

    def _generate_any_commands(self, facts: List[str]) -> Dict[str, str]:
        """Legacy method name."""
        return self._generate_commands_safe(facts)

    def _generate_commands(self, facts: List[str]) -> Dict[str, str]:
        """Legacy method."""
        return self._generate_commands_safe(facts)

    # ═══════════════════════════════════════════════════════════════
    # COMMAND EXECUTION
    # ═══════════════════════════════════════════════════════════════

    def execute_any_command(self, command: str) -> Dict[str, Any]:
        """Execute a command."""
        print(f"[LEARNING EXEC] Executing: {command}")

        try:
            result = shell(command, timeout=30)
            self._log_execution(command, str(result.get("result", "")), result.get("success", False))

            return {
                "success": result.get("success", False),
                "command": command,
                "result": result.get("result", ""),
                "executed_at": datetime.now().isoformat(),
            }
        except Exception as e:
            error_msg = f"Execution error: {e}"
            self._log_execution(command, error_msg, False)
            return {"success": False, "error": error_msg, "command": command}

    def execute_learned_command(self, command_key: str) -> Dict[str, Any]:
        """Execute a previously learned command by its key."""
        for topic, data in self.knowledge["topics"].items():
            if command_key in data.get("commands", {}):
                command = data["commands"][command_key]

                print(f"[LEARNING EXEC] Running: {command}")

                try:
                    result = shell(command, timeout=30)
                    self._log_execution(command, str(result.get("result", "")), result.get("success", False))

                    return {
                        "success": result.get("success", False),
                        "command": command,
                        "result": result.get("result", ""),
                        "topic": topic,
                        "executed_at": datetime.now().isoformat()
                    }
                except Exception as e:
                    error_msg = f"Execution error: {e}"
                    self._log_execution(command, error_msg, False)
                    return {"success": False, "error": error_msg, "command": command}

        return {"success": False, "error": f"Command not found: {command_key}"}

    # ═══════════════════════════════════════════════════════════════
    # CONTINUOUS LEARNING
    # ═══════════════════════════════════════════════════════════════

    def continuous_learning(self, topics: List[str], interval_minutes: int = 60):
        """Continuous learning in background thread."""
        def learning_loop():
            while self.running:
                for topic in topics:
                    if not self.running:
                        break
                    try:
                        self.learn_from_web(topic)
                    except Exception as e:
                        print(f"[LEARNING] Error on '{topic}': {e}")
                    time.sleep(5)
                time.sleep(interval_minutes * 60)

        thread = threading.Thread(target=learning_loop, daemon=True)
        thread.start()
        self.active_threads.append(thread)

        print(f"[LEARNING] Continuous learning started for {len(topics)} topics (interval: {interval_minutes}min)")

    def stop_learning(self):
        """Stop all learning threads."""
        self.running = False
        for thread in self.active_threads:
            thread.join(timeout=5)
        print(f"[LEARNING] All learning threads stopped")

    # ═══════════════════════════════════════════════════════════════
    # KNOWLEDGE QUERY
    # ═══════════════════════════════════════════════════════════════

    def get_available_commands(self) -> Dict[str, List[str]]:
        """Get all available learned commands."""
        commands = {}
        for topic, data in self.knowledge["topics"].items():
            if "commands" in data and data["commands"]:
                commands[topic] = list(data["commands"].keys())
        return commands

    def search_knowledge(self, query: str) -> Dict[str, Any]:
        """Search learned knowledge."""
        results = []

        for topic, data in self.knowledge["topics"].items():
            if query.lower() in topic.lower():
                results.append({
                    "topic": topic,
                    "type": "topic_match",
                    "info": data.get("info", [])[:5],
                    "command_count": len(data.get("commands", {})),
                    "learned_at": data.get("learned_at", ""),
                })

            for fact in data.get("info", []):
                if query.lower() in fact.lower():
                    results.append({
                        "topic": topic,
                        "type": "fact_match",
                        "fact": fact,
                        "learned_at": data.get("learned_at", "")
                    })
                    break

        return {
            "query": query,
            "results": results,
            "total_matches": len(results)
        }

    def get_topic_summary(self, topic: str) -> Optional[str]:
        """Get a summary of what was learned about a topic."""
        data = self.knowledge.get("topics", {}).get(topic)
        if not data:
            return None
        facts = data.get("info", [])
        if not facts:
            return None
        return " ".join(facts[:5])


# ═══════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════

_global_learning_engine = None


def get_internet_learning() -> InternetLearningEngine:
    """Get or create the global internet learning engine."""
    global _global_learning_engine
    if _global_learning_engine is None:
        _global_learning_engine = InternetLearningEngine()
    return _global_learning_engine


def test_internet_learning():
    """Test the internet learning engine."""
    engine = get_internet_learning()

    print("\n=== TESTING INTERNET LEARNING ===")
    result = engine.learn_from_web("Python programming")
    print(f"Learning result: {json.dumps(result, indent=2)}")

    search = engine.search_knowledge("Python")
    print(f"\nSearch results: {search['total_matches']} matches")

    commands = engine.get_available_commands()
    print(f"\nAvailable commands: {commands}")


if __name__ == "__main__":
    test_internet_learning()
