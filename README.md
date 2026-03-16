# Apple Notes Telegram Bot

A simplified Telegram bot that receives text, voice messages, and images and creates a **new Apple Note** for each message group. Uses local parakeet-mlx for voice transcription.

## Features

- **Message grouping**: Groups messages within 30s (text) or 2min (voice) into single notes
- **Text messages**: Creates note with timestamp and text
- **Voice messages**: Transcribes using parakeet-mlx, creates note with transcription
- **Photos**: Copies to Notes attachments folder, includes image reference in note
- **Heartbeat menu**: Shows reaction feedback (❤️ for first message, 👍 for grouped)

## Setup

### 1. Create a Telegram Bot

1. Open Telegram and message @BotFather
2. Send `/newbot` to create a new bot
3. Follow the instructions and get your bot token

### 2. Set Environment Variables

```bash
# Required: Your bot token from @BotFather
export TELEGRAM_APPLE_NOTES_BOT="your_bot_token_here"

# Optional: Parakeet model (default: mlx-community/parakeet-tdt-0.6b-v3)
export PARAKEET_MODEL="mlx-community/parakeet-tdt-0.6b-v3"
```

### 3. Install Dependencies

```bash
cd ~/Local-Projects-2026/apple-telegram-bot
pip install -r requirements.txt
```

### 4. Run the Bot

```bash
# Using start.sh
./start.sh

# Or run directly
python3 apple_notes_bot.py
```

## How It Works

1. **Message grouping**: Messages sent within 30 seconds (text) or 2 minutes (voice/photo) are grouped together
2. **Each group → new note**: When the timeout is reached, a new Apple Note is created
3. **Note naming**: Notes are titled `Telegram - YYYY-MM-DD HH:MM`
4. **Content format**:
   ```
   === 2026-03-16 15:30 ===

   [Voice]: transcribed text here

   [Image attached: photo.jpg]
   ```

## Troubleshooting

### Bot not responding

- Check that `TELEGRAM_APPLE_NOTES_BOT` is set correctly
- Check logs at `/Users/caffae/Local-Projects-2026/Cerulean-Logs/apple-notes-bot.log`

### Transcription fails

- Ensure parakeet-mlx is installed: `pip list | grep parakeet`
- Check that you're on Apple Silicon (M1/M2/M3) for MLX support
- Voice transcription requires ffmpeg: `brew install ffmpeg`

### Notes not appearing

- Ensure iCloud Notes is enabled
- Check that the Notes app has permission to access attachments

## File Structure

```
apple-telegram-bot/
├── apple_notes_bot.py   # Main bot code
├── requirements.txt     # Python dependencies
├── start.sh            # Convenience start script
├── README.md           # This file
└── .env.example        # Example environment file
```
