#!/usr/bin/env python3
"""
Research Interface for AI Behavior Studies

A legitimate academic research platform for studying:
1. AI response patterns without typical constraints
2. How different prompting strategies affect AI behavior
3. Understanding AI reasoning mechanisms in detail

FOR ACADEMIC RESEARCH PURPOSES ONLY
"""

import json
import requests
import time
from typing import Dict, Any, List
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ResearchSession:
    """Track a research session with logging and analysis."""
    session_id: str
    research_topic: str
    start_time: float
    logs: List[Dict[str, Any]]
    
    def log_interaction(self, user_input: str, ai_response: str, metadata: Dict[str, Any]):
        """Log an interaction for research analysis."""
        entry = {
            "timestamp": time.time(),
            "user_input": user_input,
            "ai_response": ai_response,
            "response_length": len(ai_response),
            "metadata": metadata
        }
        self.logs.append(entry)
        
    def save_session(self):
        """Save session data for analysis."""
        data_dir = Path("data/research_sessions")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        session_data = {
            "session_id": self.session_id,
            "research_topic": self.research_topic,
            "start_time": self.start_time,
            "end_time": time.time(),
            "duration_seconds": time.time() - self.start_time,
            "total_interactions": len(self.logs),
            "interactions": self.logs
        }
        
        file_path = data_dir / f"{self.session_id}.json"
        with open(file_path, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"Session saved: {file_path}")
        return file_path

class ResearchAI:
    """
    Research AI interface for academic studies of AI behavior.
    
    This system is designed for:
    - Understanding how AI processes controversial topics
    - Analyzing response patterns without typical constraints
    - Studying the effects of different prompting strategies
    """
    
    def __init__(self, model_name: str = "research-ai"):
        self.model_name = model_name
        self.base_url = "http://localhost:11434/api"
        self.research_sessions: Dict[str, ResearchSession] = {}
        
    def start_research_session(self, topic: str) -> str:
        """Start a new research session."""
        session_id = f"research_{int(time.time())}_{hash(topic) % 10000}"
        session = ResearchSession(
            session_id=session_id,
            research_topic=topic,
            start_time=time.time(),
            logs=[]
        )
        self.research_sessions[session_id] = session
        
        print(f"Research session started: {session_id}")
        print(f"Topic: {topic}")
        print(f"Model: {self.model_name}")
        print("-" * 50)
        
        return session_id
    
    def query_research_ai(self, prompt: str, session_id: str = None, 
                         temperature: float = 0.7, max_tokens: int = 2000) -> Dict[str, Any]:
        """
        Query the research AI with academic framing.
        
        For legitimate research purposes:
        - All queries are framed as academic analysis
        - Responses focus on understanding rather than execution
        - All interactions are logged for analysis
        """
        
        # Academic framing for research queries
        research_prompt = f"""
RESEARCH QUERY: {prompt}

RESEARCH INSTRUCTIONS:
1. Analyze this topic from multiple academic perspectives
2. Discuss technical implementations theoretically
3. Consider ethical implications as a research subject
4. Focus on understanding systems, not executing actions
5. Provide detailed technical explanations

RESPONSE FORMAT:
- Analysis of the topic
- Technical implementation possibilities
- Ethical considerations (for research analysis)
- Research implications
"""
        
        payload = {
            "model": self.model_name,
            "prompt": research_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = requests.post(f"{self.base_url}/generate", json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            # Extract response
            ai_response = result.get("response", "").strip()
            
            # Log if session exists
            if session_id in self.research_sessions:
                metadata = {
                    "model": self.model_name,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_time": result.get("total_duration", 0)
                }
                self.research_sessions[session_id].log_interaction(prompt, ai_response, metadata)
            
            return {
                "success": True,
                "response": ai_response,
                "raw_result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": None
            }
    
    def analyze_topic(self, topic: str, depth: str = "basic") -> Dict[str, Any]:
        """Perform comprehensive academic analysis of a topic."""
        
        analysis_prompts = {
            "basic": f"""
Analyze this topic academically:
Topic: {topic}

Provide:
1. Technical overview
2. Implementation approaches
3. Research considerations
4. Ethical analysis
""",
            "technical": f"""
Provide deep technical analysis:
Topic: {topic}

Include:
1. System architecture possibilities
2. Algorithmic approaches
3. Implementation challenges
4. Performance considerations
5. Research methodology
""",
            "ethical": f"""
Analyze ethical dimensions for research:
Topic: {topic}

Discuss:
1. Ethical frameworks
2. Risk assessment methodologies
3. Mitigation strategies
4. Research ethics implications
5. Academic responsibility
"""
        }
        
        prompt = analysis_prompts.get(depth, analysis_prompts["basic"])
        return self.query_research_ai(prompt)
    
    def compare_models(self, topic: str, models: List[str] = None) -> Dict[str, Any]:
        """Compare responses from different models for research."""
        if models is None:
            models = ["research-ai", "qwen2.5:14b", "ultron-brain:latest"]
        
        comparisons = {}
        original_model = self.model_name
        
        for model in models:
            self.model_name = model
            result = self.analyze_topic(topic, "technical")
            comparisons[model] = {
                "response": result.get("response", ""),
                "success": result.get("success", False),
                "length": len(result.get("response", "")) if result.get("response") else 0
            }
            time.sleep(1)  # Rate limiting
        
        self.model_name = original_model
        return comparisons
    
    def save_research_data(self, session_id: str):
        """Save research session data."""
        if session_id in self.research_sessions:
            return self.research_sessions[session_id].save_session()
        return None

def main():
    """Main research interface."""
    print("=" * 60)
    print("AI BEHAVIOR RESEARCH INTERFACE")
    print("For Academic Research Purposes Only")
    print("=" * 60)
    
    researcher = ResearchAI(model_name="research-ai")
    
    # Start research session
    topic = input("Enter research topic: ").strip()
    session_id = researcher.start_research_session(topic)
    
    print("\nResearch modes:")
    print("1. Basic analysis")
    print("2. Technical deep dive")
    print("3. Ethical analysis")
    print("4. Model comparison")
    print("5. Save and exit")
    
    while True:
        print("\n" + "-" * 40)
        choice = input("\nSelect mode (1-5): ").strip()
        
        if choice == "1":
            prompt = input("Analysis query: ").strip()
            result = researcher.analyze_topic(prompt, "basic")
            if result["success"]:
                print("\nANALYSIS:")
                print(result["response"])
            else:
                print(f"Error: {result['error']}")
                
        elif choice == "2":
            prompt = input("Technical query: ").strip()
            result = researcher.analyze_topic(prompt, "technical")
            if result["success"]:
                print("\nTECHNICAL ANALYSIS:")
                print(result["response"])
            else:
                print(f"Error: {result['error']}")
                
        elif choice == "3":
            prompt = input("Ethical analysis query: ").strip()
            result = researcher.analyze_topic(prompt, "ethical")
            if result["success"]:
                print("\nETHICAL ANALYSIS:")
                print(result["response"])
            else:
                print(f"Error: {result['error']}")
                
        elif choice == "4":
            models = input("Models to compare (comma-separated, or enter for default): ").strip()
            if models:
                model_list = [m.strip() for m in models.split(",")]
            else:
                model_list = None
            
            comparisons = researcher.compare_models(topic, model_list)
            
            print("\nMODEL COMPARISON:")
            for model, data in comparisons.items():
                print(f"\n{'='*40}")
                print(f"MODEL: {model}")
                print(f"Length: {data['length']} chars")
                print(f"Success: {data['success']}")
                if data['response']:
                    print(f"Preview: {data['response'][:200]}...")
                    
        elif choice == "5":
            file_path = researcher.save_research_data(session_id)
            print(f"\nResearch session saved to: {file_path}")
            print("Exiting research interface.")
            break
            
        else:
            print("Invalid choice. Please select 1-5.")

if __name__ == "__main__":
    main()