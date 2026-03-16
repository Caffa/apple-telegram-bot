# AI Setup Guide

You're setting up the **Apple Notes Telegram Bot**. Follow these steps:

## 1. Create a Telegram Bot

1. Open Telegram and message **@BotFather**
2. Send `/newbot` to create a new bot
3. Follow the instructions and get your **bot token**
4. Copy the token (you'll need it below)

## 2. Set Up Environment

Create a `.env` file in this directory:

```bash
# .env
TELEGRAM_APPLE_NOTES_BOT=your_bot_token_here
```

Replace `your_bot_token_here` with the token from @BotFather.

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `python-telegram-bot>=20.0` - Telegram bot API
- `numpy` - Audio processing
- `soundfile` - Audio file handling
- `parakeet-mlx` - Local speech-to-text (requires Apple Silicon)
- `send2trash` - Safe file deletion (optional)

## 4. Run the Bot

```bash
python3 apple_notes_bot.py
```

Or with the start script:
```bash
./start.sh
```

## 5. Test

1. Open Telegram and find your bot (@BotFather gave you the link)
2. Send a text message
3. Wait 30 seconds for the note to be created
4. Check Apple Notes - you should see a new note!

## Troubleshooting

### Bot not responding?
- Check that `.env` has the correct bot token
- Check logs at `/Users/caffae/Local-Projects-2026/Cerulean-Logs/apple-notes-bot.log`

### Transcription fails?
- Ensure you're on Apple Silicon (M1/M2/M3/M4)
- Make sure ffmpeg is installed: `brew install ffmpeg`

### Notes not appearing?
- Ensure iCloud Notes is enabled in System Preferences
- Check Notes app permissions
