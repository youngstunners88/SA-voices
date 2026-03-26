#!/bin/bash

# SA Voices Setup Script

set -e

echo "🇿🇦 Setting up SA Voices..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install system dependencies (Ubuntu/Debian)
if command -v apt-get &> /dev/null; then
    echo "Installing system dependencies..."
    sudo apt-get update
    sudo apt-get install -y ffmpeg libsndfile1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Qwen3-TTS
echo "Installing Qwen3-TTS..."
if [ ! -d "Qwen3-TTS" ]; then
    git clone https://github.com/QwenLM/Qwen3-TTS.git
fi
cd Qwen3-TTS
pip install -e .
cd ..

# Create necessary directories
echo "Creating directories..."
mkdir -p data/{cache,waxal,sessions,state}
mkdir -p models/cache
mkdir -p logs
mkdir -p assets/{audio,prompts}

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your HuggingFace API key"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your HUGGINGFACE_API_KEY"
echo "2. Run: python -m src.core.cli languages"
echo "3. Test: python -m src.core.cli demo --language zu"
echo "4. Start server: python -m src.core.cli server"
echo ""
