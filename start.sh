#!/bin/bash
# Start script for Apple Notes Telegram Bot
# Usage: ./start.sh [note_name]
# Default note name is "Telegram Bot"

# Get note name from argument or use default
NOTE_NAME="${1:-Telegram Bot}"

# Export variables
export TELEGRAM_APPLE_NOTES_BOT="${TELEGRAM_APPLE_NOTES_BOT:?Please set TELEGRAM_APPLE_NOTES_BOT environment variable}"
export APPLE_NOTE_NAME="$NOTE_NAME"

# Optional: specify parakeet model (default is mlx-community/parakeet-tdt-0.6b-v3)
# export PARAKEET_MODEL="mlx-community/parakeet-tdt-0.6b-v2"

# Change to script directory
cd "$(dirname "$0")"

# Run the bot
exec python3 apple_notes_bot.py
