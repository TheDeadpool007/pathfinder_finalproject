#!/bin/bash

# Setup script for Agentic AI Travel Planner
# Run this script to set up the project

set -e

echo "🚀 Setting up Agentic AI Travel Planner..."

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "✓ Python version: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create .env if doesn't exist
if [ ! -f .env ]; then
    echo "🔑 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys!"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API keys:"
echo "   - Get OpenTripMap key: https://opentripmap.io/product"
echo "   - Get OpenRouteService key: https://openrouteservice.org/dev/#/signup"
echo ""
echo "2. (Optional) Install Ollama for LLM features:"
echo "   - Download from: https://ollama.ai"
echo "   - Run: ollama pull qwen2.5:0.5b"
echo ""
echo "3. Run the application:"
echo "   source venv/bin/activate"
echo "   streamlit run app.py"
echo ""
