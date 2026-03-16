# AI Setup Guide

You're setting up the **Apple Notes Telegram Bot**. Follow these steps:

## 1. Create a Telegram Bot

1. Open Telegram and message **@BotFather**
2. Send `/newbot` to create a new bot
3. Follow the instructions and get your **bot token**

## 2. Set Up Configuration

Copy the example config and add your bot token:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and set your bot token:

```yaml
bot_token: "your_bot_token_here"
```

Or set via environment variable:
```bash
export TELEGRAM_APPLE_NOTES_BOT="your_bot_token_here"
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** Voice transcription requires either:
- **Apple Silicon (M1/M2/M3/M4)**: Uses parakeet-mlx (no extra setup)
- **Intel Mac or Linux**: Uses faster-whisper (installs automatically)

ffmpeg is required for audio processing:
```bash
brew install ffmpeg
```

## 4. Run the Bot

**Option A: Direct**
```bash
python3 apple_notes_bot.py
```

**Option B: With Heartbeat Menu (recommended)**
```bash
python3 heartbeat_menu.py
```

The heartbeat menu runs in the macOS menubar and auto-restarts the bot if it crashes.

## 5. Test

1. Open Telegram and find your bot
2. Send a text message
3. Wait 30 seconds
4. Check Apple Notes - you should see a new note!

## Configuration Options

Edit `config.yaml` to customize:

```yaml
# Bot token (required)
bot_token: ""

# Note mode: "new" (one per message group) or "append" (single note)
note:
  mode: new
  title_prefix: "Telegram"

# Timeouts (seconds)
timeouts:
  text: 30
  voice: 120

# Voice transcription
voice:
  provider: auto  # "auto", "parakeet", or "faster-whisper"
  parakeet_model: "mlx-community/parakeet-tdt-0.6b-v3"
  whisper_model: "base"
```

## Troubleshooting

### Bot not responding?
- Check that `bot_token` in `config.yaml` is correct
- Check logs at `~/Library/Logs/apple-notes-bot.log`

### Transcription fails?
- **Apple Silicon**: Ensure parakeet-mlx is installed
- **Intel/Linux**: Ensure faster-whisper is installed: `pip install faster-whisper`
- Check ffmpeg: `brew install ffmpeg`

### Notes not appearing?
- Ensure iCloud Notes is enabled
- Check Notes app permissions
