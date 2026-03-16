#!/bin/bash
# Apple Notes Telegram Bot - Quick Start Script
# This script installs dependencies and launches the bot

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🍎 Apple Notes Telegram Bot - Setup"
echo "===================================="

# Check if config.yaml or .env exists
if [ ! -f "config.yaml" ] && [ ! -f ".env" ]; then
    echo "📝 Setting up configuration..."
    
    if [ -f "config.example.yaml" ]; then
        cp config.example.yaml config.yaml
        echo "✅ Created config.yaml from example"
        echo ""
        echo "⚠️  Please add your bot token to config.yaml or .env"
        echo "   Then run this script again."
        exit 0
    elif [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Created .env from example"
        echo ""
        echo "⚠️  Please add your bot token to .env"
        echo "   Then run this script again."
        exit 0
    fi
fi

# Check for bot token
if [ -f ".env" ]; then
    source .env
fi

if [ -z "$TELEGRAM_APPLE_NOTES_BOT" ]; then
    # Check config.yaml
    if [ -f "config.yaml" ]; then
        if grep -q 'bot_token: ""' config.yaml || ! grep -q 'bot_token:' config.yaml; then
            echo "⚠️  Bot token not set in config.yaml"
            echo "   Please add your bot token and run again."
            exit 1
        fi
    else
        echo "⚠️  Bot token not found!"
        echo "   Set TELEGRAM_APPLE_NOTES_BOT in .env or config.yaml"
        exit 1
    fi
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

# Install dependencies (check if pip exists)
if command -v pip3 &> /dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install -r requirements.txt --quiet
    echo "✅ Dependencies installed"
elif command -v pip &> /dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt --quiet
    echo "✅ Dependencies installed"
fi

# Check for ffmpeg (needed for audio)
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  ffmpeg not found - needed for audio processing"
    echo "   Install with: brew install ffmpeg"
fi

echo ""
echo "🚀 Starting Apple Notes Bot..."
echo ""

# Run with heartbeat menu (if available)
if [ -f "heartbeat_menu.py" ]; then
    exec python3 heartbeat_menu.py
else
    exec python3 apple_notes_bot.py
fi
