#!/usr/bin/env python3
"""
Apple Notes Telegram Bot
Receives text, voice messages, and images from Telegram and creates new Apple Notes for each message group.
Uses parakeet-mlx for voice transcription.

Setup:
    1. Create a Telegram bot via @BotFather and get the token
    2. Set TELEGRAM_APPLE_NOTES_BOT=<token> environment variable
    3. Run: python apple_notes_bot.py
"""

import asyncio
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Telegram imports
from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, CallbackContext, MessageHandler, filters

# Configuration
BOT_TOKEN = os.environ.get("TELEGRAM_APPLE_NOTES_BOT", "")

# Paths
PARAKEET_MODEL = os.environ.get("PARAKEET_MODEL", "mlx-community/parakeet-tdt-0.6b-v3")
LOG_FILE = Path("/Users/caffae/Local-Projects-2026/Cerulean-Logs/apple-notes-bot.log")
TEMP_DIR = Path("/tmp/apple-notes-bot")

# Ensure directories exist
for d in [LOG_FILE.parent, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# Parakeet path
PARAKEET_PATH = Path("/Users/caffae/Local-Projects-2026/speech-to-text-parakeet")
if PARAKEET_PATH.exists():
    sys.path.insert(0, str(PARAKEET_PATH))


def log(msg: str):
    """Write timestamped log message."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# ==============================================================================
# PARAKEET TRANSCRIPTION
# ==============================================================================


def transcribe_with_parakeet(audio_path: Path) -> str:
    """
    Transcribe audio file using parakeet-mlx.
    """
    try:
        from parakeet_mlx import from_pretrained
        from asr_helper import preprocess_audio, mechanical_cleanup
        
        log(f"Loading parakeet model: {PARAKEET_MODEL}")
        model = from_pretrained(PARAKEET_MODEL)
        
        # Preprocess audio
        log(f"Preprocessing audio: {audio_path.name}")
        wav_path = preprocess_audio(audio_path)
        
        if wav_path is None:
            raise RuntimeError("Audio preprocessing failed")
        
        try:
            log(f"Transcribing: {wav_path.name}")
            result = model.transcribe(str(wav_path))
            text = result.text.strip()
            text = mechanical_cleanup(text)
            log(f"Transcription complete: {text[:100]}...")
            return text
        finally:
            if wav_path and wav_path.exists():
                wav_path.unlink()
                
    except Exception as e:
        log(f"Transcription error: {e}")
        raise


# ==============================================================================
# APPLE NOTES INTEGRATION
# ==============================================================================


def create_apple_note(title: str, content: str) -> bool:
    """
    Create a new Apple Note with title and content.
    
    Args:
        title: Note title
        content: Note body content
    
    Returns:
        True if successful
    """
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    escaped_content = content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    
    apple_script = f'''
    tell application "Notes"
        tell account "iCloud"
            make new note at folder "Notes" with properties {{name:"{escaped_title}", body:"{escaped_content}"}}
        end tell
    end tell
    '''
    
    try:
        result = subprocess.run(
            ["osascript", "-e", apple_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            log(f"AppleScript error: {result.stderr}")
            return False
        
        log(f"Created Apple Note: '{title}'")
        return True
        
    except Exception as e:
        log(f"Failed to create Apple Note: {e}")
        return False


def copy_image_to_notes_attachments(image_path: Path) -> Optional[Path]:
    """
    Copy an image to the Notes attachments folder so it appears in the note.
    
    Args:
        image_path: Path to image file
    
    Returns:
        Path to the copied image, or None if failed
    """
    try:
        notes_attachments = Path.home() / "Library/Group Containers/group.com.apple.notes/Attachments"
        notes_attachments.mkdir(parents=True, exist_ok=True)
        
        dest_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{image_path.name}"
        dest_path = notes_attachments / dest_name
        shutil.copy2(str(image_path), str(dest_path))
        
        log(f"Copied image to Notes attachments: {dest_path.name}")
        return dest_path
        
    except Exception as e:
        log(f"Failed to copy image to Notes: {e}")
        return None


# ==============================================================================
# MESSAGE BUFFERING (from original bot)
# ==============================================================================


@dataclass
class BufferedMessage:
    """Represents a single buffered message."""
    message_type: str  # "text", "photo", "voice"
    timestamp: str
    content: str
    temp_file_path: Optional[Path] = None
    caption: Optional[str] = None


@dataclass
class UserBuffer:
    """Buffer for a single user's messages."""
    user_id: int
    first_timestamp: str
    messages: list[BufferedMessage] = field(default_factory=list)
    contains_voice: bool = False
    timer_task: Optional[asyncio.Task] = None


class MessageBuffer:
    """Manages time-based message grouping buffers."""
    
    def __init__(self):
        self.buffers: dict[int, UserBuffer] = {}
        self.default_timeout = 30  # seconds
        self.voice_timeout = 120  # seconds (2 minutes)

    def add_message(
        self,
        user_id: int,
        message_type: str,
        content: str,
        timestamp: str,
        temp_file_path: Optional[Path] = None,
        caption: Optional[str] = None,
    ) -> UserBuffer:
        """Add message to buffer, creating new buffer if needed."""
        msg = BufferedMessage(
            message_type=message_type,
            timestamp=timestamp,
            content=content,
            temp_file_path=temp_file_path,
            caption=caption,
        )

        if user_id not in self.buffers:
            self.buffers[user_id] = UserBuffer(
                user_id=user_id,
                first_timestamp=timestamp,
                messages=[msg],
                contains_voice=(message_type == "voice"),
            )
        else:
            buffer = self.buffers[user_id]
            buffer.messages.append(msg)
            if message_type == "voice":
                buffer.contains_voice = True

        return self.buffers[user_id]

    def get_timeout(self, buffer: UserBuffer) -> int:
        return self.voice_timeout if buffer.contains_voice else self.default_timeout

    def check_timeout(self, buffer: UserBuffer) -> bool:
        first_dt = datetime.strptime(buffer.first_timestamp, "%Y-%m-%d %H:%M:%S")
        current_dt = datetime.now()
        elapsed = (current_dt - first_dt).total_seconds()
        timeout = self.get_timeout(buffer)
        return elapsed >= timeout

    def get_messages(self, user_id: int) -> Optional[UserBuffer]:
        return self.buffers.get(user_id)

    def clear_buffer(self, user_id: int):
        if user_id in self.buffers:
            buffer = self.buffers[user_id]
            if buffer.timer_task and not buffer.timer_task.done():
                buffer.timer_task.cancel()
            del self.buffers[user_id]


# Global buffer instance
message_buffer = MessageBuffer()


# ==============================================================================
# HEARTBEAT MENU (from original bot)
# ==============================================================================


def build_heartbeat_menu(user_name: str, note_title: str, content_preview: str) -> list:
    """
    Build inline keyboard with actions for the note.
    
    Returns list of button rows for telegram bot menu.
    """
    # For Apple Notes, we mainly show the note was created
    # The menu shows options for what was done
    return []


async def add_reaction(update: Update, context: CallbackContext, emoji: str = "❤️"):
    """Add an emoji reaction to the message."""
    try:
        await update.message.set_reaction(ReactionTypeEmoji(emoji=emoji))
    except Exception as e:
        log(f"Failed to add reaction ({emoji}): {e}")


# ==============================================================================
# MESSAGE PROCESSING
# ==============================================================================


async def process_buffered_messages(
    user_id: int, update: Update, context: CallbackContext
):
    """Process all buffered messages for a user as a single group."""
    buffer = message_buffer.get_messages(user_id)
    if not buffer:
        log(f"Process: No buffer for user {user_id}, skipping")
        return

    log(f"Process: Starting for user {user_id} with {len(buffer.messages)} message(s)")

    user_name = update.effective_user.first_name or "Unknown"
    
    try:
        # Collect content from all messages
        text_parts = []
        image_paths = []
        
        for i, msg in enumerate(buffer.messages):
            log(f"Process: Handling message {i+1}/{len(buffer.messages)} - type: {msg.message_type}")
            
            if msg.message_type == "text":
                text_parts.append(msg.content)
                
            elif msg.message_type == "photo":
                if msg.temp_file_path:
                    # Copy image to Notes attachments
                    dest_path = copy_image_to_notes_attachments(msg.temp_file_path)
                    if dest_path:
                        image_paths.append(dest_path)
                    # Clean up temp
                    if msg.temp_file_path.exists():
                        msg.temp_file_path.unlink()
                if msg.caption:
                    text_parts.append(f"[Photo Caption]: {msg.caption}")
                    
            elif msg.message_type == "voice":
                if msg.temp_file_path:
                    try:
                        log(f"Process: Transcribing voice from {msg.temp_file_path}")
                        transcript = transcribe_with_parakeet(msg.temp_file_path)
                        if transcript:
                            text_parts.append(f"[Voice]: {transcript}")
                    except Exception as e:
                        log(f"Process: Voice transcription failed: {e}")
                        text_parts.append(f"[Voice]: (transcription failed)")
                    finally:
                        # Clean up temp audio
                        if msg.temp_file_path.exists():
                            msg.temp_file_path.unlink()

        # Build note content
        timestamp = buffer.first_timestamp
        content_lines = []
        
        # Add header
        content_lines.append(f"=== {timestamp} ===")
        content_lines.append("")
        
        # Add text content
        if text_parts:
            content_lines.extend(text_parts)
            content_lines.append("")
        
        # Add image references
        for img_path in image_paths:
            content_lines.append(f"[Image attached: {img_path.name}]")
        
        note_content = "\n".join(content_lines)
        
        # Create note title from timestamp
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        note_title = f"Telegram - {dt.strftime('%Y-%m-%d %H:%M')}"
        
        # Create the Apple Note
        success = create_apple_note(note_title, note_content)
        
        if success:
            log(f"Created note for {user_name}: {note_title}")
            
            # Format reply
            preview = note_content[:100].replace("\n", " ")
            reply_text = f"✅ Created note: {note_title}\n\n{preview}..."
            
            # Send reply
            try:
                await update.message.reply_text(
                    reply_text,
                    disable_notification=True,
                    read_timeout=5,
                    write_timeout=5,
                )
            except Exception as e:
                log(f"Failed to send reply: {e}")
        else:
            log(f"Failed to create note for {user_name}")
            try:
                await update.message.reply_text(
                    "❌ Failed to create note",
                    disable_notification=True,
                )
            except Exception:
                pass

    except Exception as e:
        log(f"Process ERROR: {e}")
        import traceback
        log(f"TRACEBACK: {traceback.format_exc()}")
    finally:
        message_buffer.clear_buffer(user_id)


async def buffer_timer_handler(user_id: int, update: Update, context: CallbackContext):
    """Handler for buffer timeout."""
    try:
        buffer = message_buffer.get_messages(user_id)
        if not buffer:
            return

        timeout = message_buffer.get_timeout(buffer)
        log(f"Timer: Starting {timeout}s sleep for user {user_id}")
        await asyncio.sleep(timeout)

        buffer = message_buffer.get_messages(user_id)
        if not buffer:
            return

        is_timed_out = message_buffer.check_timeout(buffer)
        log(f"Timer: Check for user {user_id} - timeout={is_timed_out}")

        if is_timed_out:
            await process_buffered_messages(user_id, update, context)
    except asyncio.CancelledError:
        log(f"Timer: Cancelled for user {user_id}")
    except Exception as e:
        log(f"Timer: ERROR for user {user_id}: {e}")


# ==============================================================================
# TELEGRAM HANDLERS
# ==============================================================================


async def on_text(update: Update, context: CallbackContext):
    """Handle text messages."""
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    text = update.message.text
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine emoji
    existing_buffer = message_buffer.get_messages(user_id)
    is_initial = existing_buffer is None or len(existing_buffer.messages) == 0
    emoji = "❤️" if is_initial else "👍"

    try:
        await add_reaction(update, context, emoji=emoji)
    except Exception as e:
        log(f"Failed to add reaction: {e}")

    try:
        buffer = message_buffer.add_message(
            user_id=user_id,
            message_type="text",
            content=text,
            timestamp=received_at,
        )

        if buffer.timer_task and not buffer.timer_task.done():
            buffer.timer_task.cancel()

        timeout = message_buffer.get_timeout(buffer)
        buffer.timer_task = asyncio.create_task(
            buffer_timer_handler(user_id, update, context)
        )

        log(f"TEXT from {user}: buffered ({len(buffer.messages)} msg(s), timeout: {timeout}s)")

    except Exception as e:
        log(f"TEXT from {user}: ERROR - {e}")


async def on_voice(update: Update, context: CallbackContext):
    """Handle voice messages."""
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    voice = update.message.voice
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    temp_ogg = TEMP_DIR / f"voice_{uuid.uuid4()}.ogg"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Determine emoji
    existing_buffer = message_buffer.get_messages(user_id)
    is_initial = existing_buffer is None or len(existing_buffer.messages) == 0
    emoji = "❤️" if is_initial else "👍"

    try:
        await add_reaction(update, context, emoji=emoji)
    except Exception as e:
        log(f"Failed to add reaction: {e}")

    try:
        file = await voice.get_file()
        await file.download_to_drive(str(temp_ogg))

        buffer = message_buffer.add_message(
            user_id=user_id,
            message_type="voice",
            content="",
            timestamp=received_at,
            temp_file_path=temp_ogg,
        )

        if buffer.timer_task and not buffer.timer_task.done():
            buffer.timer_task.cancel()

        timeout = message_buffer.get_timeout(buffer)
        buffer.timer_task = asyncio.create_task(
            buffer_timer_handler(user_id, update, context)
        )

        log(f"VOICE from {user}: buffered ({len(buffer.messages)} msg(s), timeout: {timeout}s)")

    except Exception as e:
        log(f"VOICE from {user}: ERROR - {e}")


async def on_audio(update: Update, context: CallbackContext):
    """Handle audio files."""
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    audio = update.message.audio
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    temp_audio = TEMP_DIR / f"audio_{uuid.uuid4()}.m4a"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Determine emoji
    existing_buffer = message_buffer.get_messages(user_id)
    is_initial = existing_buffer is None or len(existing_buffer.messages) == 0
    emoji = "❤️" if is_initial else "👍"

    try:
        await add_reaction(update, context, emoji=emoji)
    except Exception as e:
        log(f"Failed to add reaction: {e}")

    try:
        file = await audio.get_file()
        await file.download_to_drive(str(temp_audio))

        buffer = message_buffer.add_message(
            user_id=user_id,
            message_type="voice",  # Treat as voice
            content="",
            timestamp=received_at,
            temp_file_path=temp_audio,
        )

        if buffer.timer_task and not buffer.timer_task.done():
            buffer.timer_task.cancel()

        timeout = message_buffer.get_timeout(buffer)
        buffer.timer_task = asyncio.create_task(
            buffer_timer_handler(user_id, update, context)
        )

        log(f"AUDIO from {user}: buffered ({len(buffer.messages)} msg(s), timeout: {timeout}s)")

    except Exception as e:
        log(f"AUDIO from {user}: ERROR - {e}")


async def on_photo(update: Update, context: CallbackContext):
    """Handle photo messages."""
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    photo = update.message.photo[-1]
    caption = update.message.caption

    temp_photo = TEMP_DIR / f"photo_{uuid.uuid4()}.jpg"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Determine emoji
    existing_buffer = message_buffer.get_messages(user_id)
    is_initial = existing_buffer is None or len(existing_buffer.messages) == 0
    emoji = "❤️" if is_initial else "👍"

    try:
        await add_reaction(update, context, emoji=emoji)
    except Exception as e:
        log(f"Failed to add reaction: {e}")

    try:
        file = await photo.get_file()
        await file.download_to_drive(str(temp_photo))

        buffer = message_buffer.add_message(
            user_id=user_id,
            message_type="photo",
            content="",
            timestamp=received_at,
            temp_file_path=temp_photo,
            caption=caption,
        )

        if buffer.timer_task and not buffer.timer_task.done():
            buffer.timer_task.cancel()

        timeout = message_buffer.get_timeout(buffer)
        buffer.timer_task = asyncio.create_task(
            buffer_timer_handler(user_id, update, context)
        )

        log(f"PHOTO from {user}: buffered ({len(buffer.messages)} msg(s), timeout: {timeout}s)")

    except Exception as e:
        log(f"PHOTO from {user}: ERROR - {e}")


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_APPLE_NOTES_BOT not set", file=sys.stderr)
        print("Get a bot token from @BotFather and set:", file=sys.stderr)
        print("  export TELEGRAM_APPLE_NOTES_BOT=your_token_here", file=sys.stderr)
        sys.exit(1)
    
    log("Apple Notes Bot starting...")
    log(f"Parakeet model: {PARAKEET_MODEL}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.AUDIO, on_audio))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    
    print("Polling for messages...", flush=True)
    log("Bot is running...")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)


if __name__ == "__main__":
    main()
