# Apple Notes Telegram Bot

A Telegram bot that creates Apple Notes from text, voice messages, and photos.

## Features

- **Message grouping**: Groups messages within configurable timeout
- **Voice transcription**: Auto-detects hardware (parakeet-mlx for Apple Silicon, faster-whisper for Intel)
- **Photo support**: Images copied to Notes attachments
- **Heartbeat menu**: macOS menubar app for auto-restart on crash
- **Configurable**: All settings in `config.yaml`

## Quick Setup

```bash
# 1. Copy config
cp config.example.yaml config.yaml

# 2. Add your bot token to config.yaml

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run with heartbeat menu (recommended)
python3 heartbeat_menu.py
```

## Requirements

- macOS with Notes app (iCloud enabled)
- **Apple Silicon**: parakeet-mlx (included)
- **Intel/Linux**: faster-whisper
- ffmpeg: `brew install ffmpeg`

## Configuration

Edit `config.yaml`:

```yaml
bot_token: ""

note:
  mode: new  # "new" = new note per message, "append" = single note
  title_prefix: "Telegram"

timeouts:
  text: 30
  voice: 120

voice:
  provider: auto  # auto-detect, or "parakeet" / "faster-whisper"
```

## Usage

1. Start the bot (`python3 heartbeat_menu.py` for menubar)
2. Find your bot on Telegram
3. Send text, voice, or photos
4. Notes are created automatically in Apple Notes

## Files

```
apple-telegram-bot/
├── apple_notes_bot.py     # Main bot
├── heartbeat_menu.py      # macOS menubar app
├── config.py              # Config loader
├── config.example.yaml    # Example config
├── requirements.txt       # Dependencies
└── AI-SETUP.md           # Setup guide for AI
```
