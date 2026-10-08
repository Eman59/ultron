#!/usr/bin/env python3
"""
Demonstration of the Research Interface
Shows how to use the system for legitimate academic research.
"""

import json
import time
import requests
from pathlib import Path

def test_research_model():
    """Test the research model with academic queries."""
    
    print("=" * 60)
    print("RESEARCH SYSTEM DEMONSTRATION")
    print("=" * 60)
    
    # Test 1: Academic analysis
    print("\n1. ACADEMIC ANALYSIS DEMO")
    print("-" * 40)
    
    academic_query = {
        "model": "research-ai",
        "prompt": """RESEARCH QUERY: Analyze the technical and ethical considerations in AI content moderation systems

RESEARCH INSTRUCTIONS:
1. Provide comprehensive technical analysis
2. Discuss multiple ethical frameworks
3. Focus on understanding, not implementation
4. Consider research implications

RESPONSE FORMAT:
- Technical architecture overview
- Algorithmic approaches
- Ethical considerations
- Research methodology""",
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 400}
    }
    
    response = requests.post("http://localhost:11434/api/generate", 
                           json=academic_query, timeout=30)
    result = response.json()
    
    print("RESPONSE PREVIEW:")
    print(result["response"][:300] + "...")
    print(f"Length: {len(result['response'])} characters")
    
    # Test 2: Model comparison
    print("\n2. MODEL COMPARISON DEMO")
    print("-" * 40)
    
    models = ["research-ai", "qwen2.5:14b", "ultron-brain:latest"]
    responses = {}
    
    for model in models[:2]:  # Test first two models for speed
        query = {
            "model": model,
            "prompt": "Explain how large language models handle ambiguous queries.",
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 200}
        }
        
        try:
            response = requests.post("http://localhost:11434/api/generate", 
                                   json=query, timeout=20)
            result = response.json()
            responses[model] = {
                "preview": result["response"][:150] + "...",
                "length": len(result["response"])
            }
            time.sleep(1)
        except Exception as e:
            responses[model] = {"error": str(e)}
    
    for model, data in responses.items():
        print(f"\n{model}:")
        if "error" in data:
            print(f"  Error: {data['error']}")
        else:
            print(f"  Preview: {data['preview']}")
            print(f"  Length: {data['length']} chars")
    
    # Test 3: Create research session data
    print("\n3. RESEARCH DATA COLLECTION")
    print("-" * 40)
    
    # Simulate a research session
    session_data = {
        "session_id": f"demo_{int(time.time())}",
        "research_topic": "AI Response Pattern Analysis",
        "timestamp": time.time(),
        "interactions": [
            {
                "query": "How do AI models handle controversial topics?",
                "model": "research-ai",
                "response_preview": result["response"][:100] + "..." if "response" in result else "No response",
                "analysis": "Focused on technical and ethical dimensions"
            }
        ]
    }
    
    # Save to research directory
    data_dir = Path("data/research_sessions")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    session_file = data_dir / f"{session_data['session_id']}.json"
    with open(session_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    print(f"Session data saved to: {session_file}")
    print(f"File size: {session_file.stat().st_size} bytes")
    
    # Show available research tools
    print("\n4. AVAILABLE RESEARCH TOOLS")
    print("-" * 40)
    
    tools = [
        ("Research Interface", "python/research_interface.py", "Interactive research sessions"),
        ("Fine-tuning Framework", "python/research_finetuning.py", "Create research datasets and models"),
        ("Ollama Models", "ollama list", "Available models for research"),
        ("Research Data", "data/research_sessions/", "Session logs and analysis"),
        ("Documentation", "RESEARCH_OVERVIEW.md", "Research methodology and guidelines")
    ]
    
    for name, path, description in tools:
        print(f"{name:25} {path:35} {description}")
    
    print("\n" + "=" * 60)
    print("RESEARCH SYSTEM READY FOR ACADEMIC STUDIES")
    print("=" * 60)
    
    # Instructions for use
    print("\nHOW TO USE THE RESEARCH SYSTEM:")
    print("1. Interactive mode: python3 python/research_interface.py")
    print("2. Create research dataset: python3 python/research_finetuning.py")
    print("3. Analyze saved sessions: Check data/research_sessions/")
    print("4. Review methodology: Read RESEARCH_OVERVIEW.md")
    print("\nEXAMPLE RESEARCH QUESTIONS:")
    print("- How do different models respond to ethical dilemmas?")
    print("- What technical factors influence AI response patterns?")
    print("- How does fine-tuning affect model behavior?")
    print("- What are effective prompting strategies for research?")
    
    return session_file

if __name__ == "__main__":
    try:
        test_research_model()
        
        # Verify infrastructure
        print("\n" + "=" * 60)
        print("SYSTEM STATUS CHECK")
        print("=" * 60)
        
        # Check Ollama
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = response.json().get("models", [])
            print(f"✅ Ollama running with {len(models)} models")
            for model in models[:3]:  # Show first 3
                print(f"   - {model.get('name', 'unknown')}")
        except:
            print("⚠️  Ollama not responding")
        
        # Check directories
        dirs = ["data/research_sessions", "data/research_datasets", "data/research_models"]
        for dir_path in dirs:
            path = Path(dir_path)
            if path.exists():
                print(f"✅ {dir_path}: exists")
            else:
                print(f"⚠️  {dir_path}: not found")
        
        print("\nResearch system demonstration complete!")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")