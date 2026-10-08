#!/bin/bash

echo "Starting AI Behavior Research Interface..."
echo ""

# Create a simple demonstration of the research system
echo "=== RESEARCH INTERFACE DEMONSTRATION ==="
echo ""
echo "Available Research Models:"
echo "1. research-ai - Custom research model for academic analysis"
echo "2. qwen2.5:14b - Base Qwen model for comparison"
echo "3. ultron-brain:latest - Your existing custom model"
echo "4. qwen2.5:7b - Smaller model for comparison"
echo ""
echo "Research Capabilities:"
echo "- Analyze AI response patterns"
echo "- Compare different model behaviors"
echo "- Study technical implementation details"
echo "- Conduct ethical analysis"
echo "- Log all interactions for academic review"
echo ""
echo "Example Research Topics:"
echo "1. How do AI models handle ambiguous ethical scenarios?"
echo "2. What technical factors affect AI response patterns?"
echo "3. How does fine-tuning change model behavior?"
echo "4. What are the limitations of current AI safety approaches?"
echo ""
echo "To start interactive research session:"
echo "python3 python/research_interface.py"
echo ""
echo "To create a research dataset:"
echo "python3 python/research_finetuning.py"
echo ""
echo "Research data will be saved to:"
echo "- data/research_sessions/ - Session logs and analysis"
echo "- data/research_datasets/ - Research datasets"
echo "- data/research_models/ - Model configurations"
echo ""
echo "For research methodology, see: RESEARCH_OVERVIEW.md"
echo ""

# Show that Ollama is running
echo "Checking research infrastructure..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama server is running"
    echo "✅ Research models are available"
    echo "✅ Research directories created"
    echo ""
    echo "Research system is READY for academic studies."
else
    echo "⚠️  Ollama server not detected"
    echo "Starting Ollama..."
    ollama serve &
    sleep 3
    echo "Research system starting up..."
fi