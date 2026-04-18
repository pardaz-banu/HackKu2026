#!/bin/bash
# KellyCopilot — Quick Start Script
# Run from the travel-copilot/ root directory

echo "=============================="
echo " KellyCopilot Backend Setup"
echo "=============================="

cd backend

# Check Python version
python3 -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "❌ Python 3.10+ is required. Please upgrade."
  exit 1
fi

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "⚠️  ANTHROPIC_API_KEY is not set!"
  echo "    Export it first:"
  echo "    export ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE"
  echo ""
  read -p "    Enter your API key now (or press Enter to skip): " KEY
  if [ -n "$KEY" ]; then
    export ANTHROPIC_API_KEY="$KEY"
    echo "✅ API key set for this session."
  fi
fi

echo ""
echo "📦 Installing Python dependencies (ignoring unrelated conflicts)..."
pip install -r requirements.txt --upgrade --quiet 2>&1 | grep -v "^WARNING"

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "🚀 Starting backend on http://localhost:8000 ..."
echo "   API docs: http://localhost:8000/docs"
echo ""
uvicorn main:app --reload --port 8000 --host 0.0.0.0
