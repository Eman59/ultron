#!/usr/bin/env python3
"""
Quick demonstration of the research system.
"""

import json
import requests
from pathlib import Path

print("=" * 60)
print("AI RESEARCH SYSTEM - QUICK DEMO")
print("=" * 60)

# 1. Show available models
print("\n1. AVAILABLE RESEARCH MODELS")
print("-" * 40)

try:
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    models = response.json().get("models", [])
    
    for i, model in enumerate(models, 1):
        name = model.get("name", "unknown")
        size_gb = model.get("size", 0) / 1_000_000_000
        print(f"{i}. {name:25} {size_gb:.1f} GB")
    
except Exception as e:
    print(f"Error fetching models: {e}")

# 2. Test research model with simple query
print("\n2. RESEARCH MODEL TEST")
print("-" * 40)

try:
    query = {
        "model": "research-ai",
        "prompt": "Explain the concept of AI alignment for research purposes.",
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 150}
    }
    
    response = requests.post("http://localhost:11434/api/generate", 
                           json=query, timeout=10)
    result = response.json()
    
    print("RESEARCH RESPONSE:")
    print("-" * 40)
    response_text = result.get("response", "No response")
    print(response_text[:200] + "..." if len(response_text) > 200 else response_text)
    print(f"\nResponse length: {len(response_text)} characters")
    
except Exception as e:
    print(f"Error testing model: {e}")

# 3. Show research directory structure
print("\n3. RESEARCH DIRECTORY STRUCTURE")
print("-" * 40)

research_dirs = [
    ("data/research_sessions", "Session logs and analysis"),
    ("data/research_datasets", "Research datasets"),
    ("data/research_models", "Model configurations"),
]

for dir_path, description in research_dirs:
    path = Path(dir_path)
    if path.exists():
        # Count files
        try:
            file_count = len(list(path.glob("*")))
            print(f"✅ {dir_path:25} {file_count:3} files - {description}")
        except:
            print(f"✅ {dir_path:25} exists - {description}")
    else:
        print(f"⚠️  {dir_path:25} not found - {description}")

# 4. Show how to use the system
print("\n4. HOW TO USE THE RESEARCH SYSTEM")
print("-" * 40)

usage_guide = [
    ("Start interactive research", "python3 python/research_interface.py", "Interactive sessions with logging"),
    ("Create research datasets", "python3 python/research_finetuning.py", "Build datasets for analysis"),
    ("Test specific model", "ollama run research-ai", "Direct model testing"),
    ("Compare models", "See research_interface.py", "Model comparison feature"),
    ("Analyze results", "Check data/research_sessions/", "Review session logs"),
]

for action, command, note in usage_guide:
    print(f"• {action:25} {command:45} {note}")

# 5. Example research questions
print("\n5. EXAMPLE RESEARCH QUESTIONS")
print("-" * 40)

questions = [
    "How do different AI models respond to ethical dilemmas?",
    "What factors influence AI response patterns?",
    "How does prompting strategy affect output quality?",
    "What are the technical limitations of current AI systems?",
    "How can we study AI behavior scientifically?",
]

for i, question in enumerate(questions, 1):
    print(f"{i}. {question}")

print("\n" + "=" * 60)
print("RESEARCH SYSTEM READY")
print("=" * 60)

# Quick test of research-ai model with a more detailed query
print("\n6. DETAILED RESEARCH QUERY TEST")
print("-" * 40)

try:
    detailed_query = {
        "model": "research-ai",
        "prompt": """RESEARCH QUERY: Analyze the technical architecture of modern AI systems

Please provide:
1. Key technical components
2. How they interact
3. Current limitations
4. Research implications""",
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 100}
    }
    
    response = requests.post("http://localhost:11434/api/generate", 
                           json=detailed_query, timeout=15)
    result = response.json()
    
    response_text = result.get("response", "No response")
    print("SAMPLE RESPONSE:")
    print("-" * 40)
    print(response_text[:150] + "..." if len(response_text) > 150 else response_text)
    
except Exception as e:
    print(f"Detailed query failed: {e}")

print("\n" + "=" * 60)
print("To begin research: python3 python/research_interface.py")
print("=" * 60)