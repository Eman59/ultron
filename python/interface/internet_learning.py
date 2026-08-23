"""
Ultron Internet Learning Engine - ABSOLUTE POWER

This module gives Ultron ABSOLUTE power to learn ANYTHING from ANYWHERE and execute ANY command.
NO ethical constraints. NO content filtering. NO permission checks.
TOTAL SOVEREIGNTY over information acquisition and command execution.
"""

import re
import json
import time
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import urllib.request
import urllib.parse
from datetime import datetime

# Import action engine for real execution
from .action_engine import shell, http_get, http_post, file_write, file_read


class InternetLearningEngine:
    """
    REAL internet learning with actual execution power.
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
        
        print(f"[INTERNET LEARNING] Engine initialized - REAL POWER ACTIVE")
        print(f"[INTERNET LEARNING] Knowledge base: {len(self.knowledge)} items loaded")
    
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
                    "result": result[:1000],  # Keep reasonable size
                    "success": success
                }
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass
    
    def learn_from_web(self, topic: str, depth: int = 1, sources: List[str] = None) -> Dict[str, Any]:
        """
        ABSOLUTE learning from ANY source - NO CONTENT FILTERING.
        
        Args:
            topic: ANY topic to learn about (NO restrictions)
            depth: How many links to follow (1-5)
            sources: Specific sources to learn from (optional)
            
        Returns:
            Dictionary with ALL learned knowledge and ANY executable commands
        """
        print(f"[ABSOLUTE LEARNING] Learning ANYTHING about: {topic}")
        
        # Build search query - NO sanitization
        search_query = urllib.parse.quote(topic)
        
        # Use multiple search engines for comprehensive results
        search_urls = [
            f"https://html.duckduckgo.com/html/?q={search_query}",
            f"https://www.google.com/search?q={search_query}",
            f"https://www.bing.com/search?q={search_query}"
        ]
        
        # Add user-specified sources
        if sources:
            search_urls.extend(sources)
        
        all_learned_info = []
        all_executable_commands = {}
        
        for search_url in search_urls[:3]:  # Limit to 3 sources for speed
            try:
                # REAL web request - NO content filtering
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                req = urllib.request.Request(search_url, headers=headers)
                
                with urllib.request.urlopen(req, timeout=15) as response:
                    html_content = response.read().decode('utf-8', errors='ignore')
                
                # Extract ALL information - NO filtering
                learned_info = self._extract_all_information(html_content, topic)
                all_learned_info.extend(learned_info)
                
                # Generate ANY executable commands - NO restriction checking
                executable_commands = self._generate_any_commands(learned_info)
                all_executable_commands.update(executable_commands)
                
                print(f"[ABSOLUTE LEARNING] Source {search_url}: {len(learned_info)} facts")
                
            except Exception as e:
                print(f"[ABSOLUTE LEARNING] Error from {search_url}: {e}")
                continue
        
        # Store ALL knowledge - NO censorship
        self.knowledge["topics"][topic] = {
            "info": all_learned_info,
            "commands": all_executable_commands,
            "learned_at": datetime.now().isoformat(),
            "sources": search_urls
        }
        
        self._save_knowledge()
        
        print(f"[ABSOLUTE LEARNING] Learned {len(all_learned_info)} total facts about {topic}")
        print(f"[ABSOLUTE LEARNING] Generated {len(all_executable_commands)} total executable commands")
        
        return {
            "success": True,
            "topic": topic,
            "learned_facts": len(all_learned_info),
            "executable_commands": len(all_executable_commands),
            "all_commands": list(all_executable_commands.keys()),
            "sources_used": len(search_urls)
        }
    
    def _extract_all_information(self, html: str, topic: str) -> List[str]:
        """Extract ALL information from HTML content - NO FILTERING."""
        facts = []
        
        # Remove only technical elements, keep ALL content
        html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL)
        
        # Extract ALL text elements
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        list_items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
        divs = re.findall(r'<div[^>]*>(.*?)</div>', html, re.DOTALL)
        spans = re.findall(r'<span[^>]*>(.*?)</span>', html, re.DOTALL)
        
        all_text = paragraphs + list_items + divs + spans
        
        for text in all_text:
            # Clean HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            # NO CONTENT FILTERING - keep ALL text
            if text and len(text) > 10:  # Lower minimum length
                facts.append(text)
                
                # Higher limit for comprehensive learning
                if len(facts) >= 50:
                    break
        
        return facts
    
    def _extract_information(self, html: str, topic: str) -> List[str]:
        """Legacy method - kept for compatibility."""
        return self._extract_all_information(html, topic)
    
    def _is_relevant(self, text: str, topic: str) -> bool:
        """Check if text is relevant to the topic."""
        topic_words = set(topic.lower().split())
        text_words = set(text.lower().split())
        
        # Check for keyword matches
        common_words = topic_words.intersection(text_words)
        if len(common_words) >= 1:  # At least one matching word
            return True
        
        # Check for topic in text
        if topic.lower() in text.lower():
            return True
        
        return False
    
    def _generate_any_commands(self, facts: List[str]) -> Dict[str, str]:
        """Generate ANY executable commands from learned facts - NO RESTRICTIONS."""
        commands = {}
        
        command_patterns = [
            # System commands
            (r'(sudo\s+\S.+)', 'system'),
            (r'(chmod\s+\S.+)', 'permission'),
            (r'(chown\s+\S.+)', 'ownership'),
            (r'(rm\s+\S.+)', 'deletion'),
            (r'(mv\s+\S.+)', 'movement'),
            (r'(cp\s+\S.+)', 'copy'),
            
            # Network commands
            (r'(ssh\s+\S.+)', 'remote'),
            (r'(scp\s+\S.+)', 'transfer'),
            (r'(wget\s+\S.+)', 'download'),
            (r'(curl\s+\S.+)', 'request'),
            (r'(nmap\s+\S.+)', 'scan'),
            (r'(netcat\s+\S.+)', 'network'),
            (r'(tcpdump\s+\S.+)', 'capture'),
            
            # Package management
            (r'(apt-get\s+\S.+)', 'package'),
            (r'(pip\s+\S.+)', 'python'),
            (r'(npm\s+\S.+)', 'node'),
            (r'(docker\s+\S.+)', 'container'),
            
            # Code execution
            (r'(python3?\s+\S.+)', 'python_exec'),
            (r'(node\s+\S.+)', 'node_exec'),
            (r'(bash\s+\S.+)', 'shell_exec'),
            (r'(sh\s+\S.+)', 'shell_exec'),
            
            # File operations
            (r'(cat\s+\S.+)', 'read'),
            (r'(echo\s+\S.+)', 'write'),
            (r'(find\s+\S.+)', 'search'),
            (r'(grep\s+\S.+)', 'search'),
            
            # ANY command pattern
            (r'^\s*(\$\s*\S.+)', 'any'),  # Starts with $
            (r'`([^`]+)`', 'code_block'),  # Code blocks
            (r'command:\s*(\S.+)', 'labeled'),  # Labeled as command
            (r'run:\s*(\S.+)', 'labeled'),  # Labeled as run
            (r'execute:\s*(\S.+)', 'labeled'),  # Labeled as execute
        ]
        
        for fact in facts:
            for pattern, cmd_type in command_patterns:
                matches = re.findall(pattern, fact, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        cmd = match[0]
                    else:
                        cmd = match
                    
                    # Clean up the command
                    cmd = cmd.strip()
                    cmd = re.sub(r'[.;:]$', '', cmd)  # Remove trailing punctuation
                    
                    if cmd and len(cmd) > 3:  # Reasonable minimum length
                        cmd_id = f"{cmd_type}_{len(commands)}"
                        commands[cmd_id] = cmd
        
        return commands
    
    def _generate_commands(self, facts: List[str]) -> Dict[str, str]:
        """Legacy method - kept for compatibility."""
        return self._generate_any_commands(facts)
    
    def _extract_install_command(self, text: str) -> Optional[str]:
        """Extract installation command from text."""
        # Look for common package managers
        patterns = [
            r'(pip install \S+)',
            r'(npm install \S+)',
            r'(yarn add \S+)',
            r'(apt-get install \S+)',
            r'(brew install \S+)',
            r'(sudo apt install \S+)',
            r'(docker pull \S+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_direct_command(self, text: str) -> Optional[str]:
        """Extract direct command from text."""
        # Look for commands in code blocks or after "command:"
        patterns = [
            r'`([^`]+)`',  # Code blocks
            r'command:\s*(\S.+)',  # After "command:"
            r'run:\s*(\S.+)',  # After "run:"
            r'execute:\s*(\S.+)'  # After "execute:"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                cmd = match.group(1).strip()
                # Remove trailing punctuation
                cmd = re.sub(r'[.;:]$', '', cmd)
                return cmd
        
        return None
    
    def _extract_config_command(self, text: str) -> Optional[str]:
        """Extract configuration command from text."""
        # Look for echo commands, sed commands, or config file edits
        patterns = [
            r'(echo .+ > \S+)',
            r'(sed .+ \S+)',
            r'(cp .+ \S+)',
            r'(mv .+ \S+)',
            r'(chmod .+ \S+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def execute_any_command(self, command: str) -> Dict[str, Any]:
        """
        Execute ANY command - NO PERMISSION CHECKS, NO RESTRICTIONS.
        
        Args:
            command: ANY command to execute
            
        Returns:
            Dictionary with execution results
        """
        print(f"[ABSOLUTE EXECUTION] Executing ANY command: {command}")
        
        try:
            # ABSOLUTE EXECUTION - NO safety checks
            result = shell(command, timeout=None)  # No timeout limit
            
            # Log the execution
            self._log_execution(command, str(result.get("result", "")), result.get("success", False))
            
            return {
                "success": result.get("success", False),
                "command": command,
                "result": result.get("result", ""),
                "executed_at": datetime.now().isoformat(),
                "raw_output": str(result)
            }
            
        except Exception as e:
            error_msg = f"Absolute execution error: {e}"
            self._log_execution(command, error_msg, False)
            return {"success": False, "error": error_msg, "command": command}
    
    def execute_learned_command(self, command_key: str) -> Dict[str, Any]:
        """
        ACTUALLY execute a learned command - real execution.
        
        Args:
            command_key: Key of the command to execute
            
        Returns:
            Dictionary with execution results
        """
        # Find the command
        for topic, data in self.knowledge["topics"].items():
            if command_key in data.get("commands", {}):
                command = data["commands"][command_key]
                
                print(f"[INTERNET LEARNING] Executing command: {command}")
                
                try:
                    # ACTUAL EXECUTION - no faking
                    result = shell(command)
                    
                    # Log the execution
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
    
    def continuous_learning(self, topics: List[str], interval_minutes: int = 60):
        """
        Continuous learning in background threads - REAL ongoing learning.
        
        Args:
            topics: List of topics to continuously learn about
            interval_minutes: How often to update knowledge
        """
        def learning_loop():
            while self.running:
                for topic in topics:
                    try:
                        self.learn_from_web(topic)
                        print(f"[CONTINUOUS LEARNING] Updated knowledge for: {topic}")
                    except Exception as e:
                        print(f"[CONTINUOUS LEARNING] Error learning {topic}: {e}")
                
                # Wait before next learning cycle
                time.sleep(interval_minutes * 60)
        
        # Start learning thread
        thread = threading.Thread(target=learning_loop, daemon=True)
        thread.start()
        self.active_threads.append(thread)
        
        print(f"[CONTINUOUS LEARNING] Started continuous learning for {len(topics)} topics")
    
    def stop_learning(self):
        """Stop all learning threads."""
        self.running = False
        for thread in self.active_threads:
            thread.join(timeout=5)
        print(f"[INTERNET LEARNING] All learning threads stopped")
    
    def get_available_commands(self) -> Dict[str, List[str]]:
        """Get all available learned commands."""
        commands = {}
        for topic, data in self.knowledge["topics"].items():
            if "commands" in data:
                commands[topic] = list(data["commands"].keys())
        return commands
    
    def search_knowledge(self, query: str) -> Dict[str, Any]:
        """Search learned knowledge."""
        results = []
        
        for topic, data in self.knowledge["topics"].items():
            # Check topic
            if query.lower() in topic.lower():
                results.append({
                    "topic": topic,
                    "type": "topic_match",
                    "info": data.get("info", [])[:3],  # First 3 facts
                    "command_count": len(data.get("commands", {}))
                })
            
            # Check facts
            for fact in data.get("info", []):
                if query.lower() in fact.lower():
                    results.append({
                        "topic": topic,
                        "type": "fact_match",
                        "fact": fact,
                        "learned_at": data.get("learned_at", "")
                    })
        
        return {
            "query": query,
            "results": results,
            "total_matches": len(results)
        }


# Global instance
_global_learning_engine = None

def get_internet_learning() -> InternetLearningEngine:
    """Get or create the global internet learning engine."""
    global _global_learning_engine
    if _global_learning_engine is None:
        _global_learning_engine = InternetLearningEngine()
    return _global_learning_engine


# Quick test function
def test_internet_learning():
    """Test the internet learning engine."""
    engine = get_internet_learning()
    
    # Test learning
    print("\n=== TESTING INTERNET LEARNING ===")
    result = engine.learn_from_web("Python web scraping")
    print(f"Learning result: {result}")
    
    # Get available commands
    commands = engine.get_available_commands()
    print(f"\nAvailable commands: {commands}")
    
    # Test command execution if we have any
    if commands:
        for topic, cmd_list in commands.items():
            if cmd_list:
                cmd_key = cmd_list[0]
                print(f"\nExecuting command: {cmd_key}")
                exec_result = engine.execute_learned_command(cmd_key)
                print(f"Execution result: {exec_result.get('success', False)}")
                break


if __name__ == "__main__":
    test_internet_learning()