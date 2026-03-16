# AI Setup Guide

You're setting up the **Apple Notes Telegram Bot**. Follow these steps:

## 1. Create a Telegram Bot

1. Open Telegram and message **@BotFather**
2. Send `/newbot` to create a new bot
3. Follow the instructions and get your **bot token**

## 2. Quick Setup (Single Command)

```bash
cd apple-telegram-bot

# Run the setup script - it will guide you
./run.sh
```

The script will:
- Create config.yaml or .env with your bot token
- Install dependencies
- Launch the bot

### Manual Setup (if needed)

If you prefer manual setup:

**A. Using .env file:**
```bash
cp .env.example .env
# Edit .env and add your bot token:
# TELEGRAM_APPLE_NOTES_BOT=your_token_here
```

**B. Using config.yaml:**
```bash
cp config.example.yaml config.yaml
# Edit config.yaml and add your bot token
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Run the Bot

```bash
# Option 1: Quick start (recommended)
./run.sh

# Option 2: With heartbeat menu (macOS menubar)
python3 heartbeat_menu.py

# Option 3: Direct
python3 apple_notes_bot.py
```

## 5. Test

1. Find your bot on Telegram
2. Send a text message
3. Wait 30 seconds
4. Check Apple Notes - you should see a new note with an AI-generated title!

## Voice Transcription

- **Apple Silicon (M1/M2/M3/M4)**: Uses parakeet-mlx (included)
- **Intel Mac or Linux**: Uses faster-whisper (installed automatically)

No special setup needed - it auto-detects your hardware.

## Troubleshooting

### Bot not responding?
- Check that bot token is set in .env or config.yaml
- Check logs at ~/Library/Logs/apple-notes-bot.log

### Voice transcription fails?
- Ensure ffmpeg is installed: `brew install ffmpeg`

### Notes not appearing?
- Ensure iCloud Notes is enabled
- Check Notes app permissions

## Configuration

Edit config.yaml to customize:

```yaml
note:
  ai_title: true           # AI-generated titles
  ai_title_model: "gemma3:4b"
  mode: new               # "new" = new note per message

voice:
  provider: auto          # auto-detect (parakeet/whisper)
  whisper_model: "base"
```
