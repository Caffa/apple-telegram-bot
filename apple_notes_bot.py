#!/usr/bin/env python3
"""
Apple Notes Telegram Bot
Receives text, voice messages, and images from Telegram and creates Apple Notes.
Uses parakeet-mlx (Apple Silicon) or faster-whisper (Intel) for voice transcription.

Setup:
    1. Copy config.example.yaml to config.yaml
    2. Add your bot token to config.yaml or set TELEGRAM_APPLE_NOTES_BOT env var
    3. Run: python3 apple_notes_bot.py
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

# Add current directory to path for config module
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    load_config,
    detect_transcription_provider,
    get_log_file,
    get_temp_dir,
    get_timeout,
)

# Load configuration
CONFIG = load_config()

# Resolve paths
LOG_FILE = get_log_file(CONFIG)
TEMP_DIR = get_temp_dir(CONFIG)

# Ensure directories exist
for d in [LOG_FILE.parent, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Telegram imports
from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, CallbackContext, MessageHandler, filters


def log(msg: str):
    """Write timestamped log message."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# ==============================================================================
# AI TITLE GENERATION
# ==============================================================================


def generate_ai_title(content: str) -> str:
    """Generate a title for the note using Ollama."""
    from config import get_note_ai_title, get_note_ai_title_model
    
    if not get_note_ai_title(CONFIG):
        return None
    
    model = get_note_ai_title_model(CONFIG)
    
    prompt = f"""Generate a short, descriptive title (max 50 characters) for this note content. 
Just return the title, nothing else.

Content:
{content[:500]}
"""

    try:
        import requests
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "text",
            },
            timeout=30,
        )
        
        if response.status_code == 200:
            title = response.json().get("response", "").strip()
            # Clean up title
            title = title.strip('"').strip("'").strip()
            # Limit length
            if len(title) > 50:
                title = title[:47] + "..."
            log(f"AI generated title: {title}")
            return title
        else:
            log(f"AI title generation failed: {response.status_code}")
            return None
            
    except Exception as e:
        log(f"AI title generation error: {e}")
        return None


# ==============================================================================
# VOICE TRANSCRIPTION (parakeet or faster-whisper)
# ==============================================================================


def transcribe_with_parakeet(audio_path: Path) -> str:
    """Transcribe audio using parakeet-mlx (Apple Silicon)."""
    parakeet_path = Path(CONFIG["paths"]["parakeet_path"])
    
    if not parakeet_path.exists():
        raise RuntimeError(f"Parakeet not found at: {parakeet_path}")
    
    # Add to path
    if str(parakeet_path) not in sys.path:
        sys.path.insert(0, str(parakeet_path))
    
    from parakeet_mlx import from_pretrained
    from asr_helper import preprocess_audio, mechanical_cleanup
    
    model_name = CONFIG["voice"]["parakeet_model"]
    log(f"Loading parakeet model: {model_name}")
    model = from_pretrained(model_name)
    
    log(f"Preprocessing audio: {audio_path.name}")
    wav_path = preprocess_audio(audio_path)
    
    if wav_path is None:
        raise RuntimeError("Audio preprocessing failed")
    
    try:
        log(f"Transcribing: {wav_path.name}")
        result = model.transcribe(str(wav_path))
        text = result.text.strip()
        text = mechanical_cleanup(text)
        log(f"Parakeet transcription: {text[:100]}...")
        return text
    finally:
        if wav_path and wav_path.exists():
            wav_path.unlink()


def transcribe_with_whisper(audio_path: Path) -> str:
    """Transcribe audio using faster-whisper (Intel/any system)."""
    try:
        from faster_whisper import WhisperModel
        
        model_name = CONFIG["voice"]["whisper_model"]
        log(f"Loading faster-whisper model: {model_name}")
        
        # Use CPU with int8 for best compatibility
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        
        log(f"Transcribing: {audio_path.name}")
        segments, info = model.transcribe(str(audio_path), beam_size=5)
        
        # Collect all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
        
        text = " ".join(text_parts)
        log(f"Whisper transcription: {text[:100]}...")
        return text
        
    except ImportError:
        raise RuntimeError("faster-whisper not installed. Run: pip install faster-whisper")


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe audio using the appropriate provider."""
    provider = detect_transcription_provider(CONFIG)
    
    log(f"Using transcription provider: {provider}")
    
    if provider == "parakeet":
        # Check if parakeet path exists before trying
        parakeet_path = Path(CONFIG["paths"]["parakeet_path"])
        if not parakeet_path.exists():
            log(f"Parakeet not found at {parakeet_path}, falling back to faster-whisper")
            provider = "faster-whisper"
        else:
            try:
                return transcribe_with_parakeet(audio_path)
            except Exception as e:
                log(f"Parakeet failed: {e}, falling back to faster-whisper")
                provider = "faster-whisper"
    
    if provider == "faster-whisper":
        return transcribe_with_whisper(audio_path)
    
    # Final fallback
    return transcribe_with_whisper(audio_path)


# ==============================================================================
# APPLE NOTES INTEGRATION
# ==============================================================================


def create_apple_note(title: str, content: str) -> bool:
    """Create a new Apple Note."""
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


def append_to_apple_note(note_name: str, content: str) -> bool:
    """Append content to an existing Apple Note."""
    escaped_note_name = note_name.replace("\\", "\\\\").replace('"', '\\"')
    escaped_content = content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    
    apple_script = f'''
    tell application "Notes"
        set noteName to "{escaped_note_name}"
        set foundNote to missing value
        repeat with n in every note
            if name of n is equal to noteName then
                set foundNote to n
                exit repeat
            end if
        end repeat
        if foundNote is missing value then
            tell account "iCloud"
                make new note at folder "Notes" with properties {{name:noteName, body:""}}
                set foundNote to first note whose name is noteName
            end tell
        end if
        tell foundNote
            set theText to body
            set body to theText & "{escaped_content}" & linefeed & linefeed
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
        
        log(f"Appended to Apple Note: '{note_name}'")
        return True
        
    except Exception as e:
        log(f"Failed to append to Apple Note: {e}")
        return False


def copy_image_to_notes_attachments(image_path: Path) -> Optional[Path]:
    """Copy image to Notes attachments folder."""
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
# MESSAGE BUFFERING
# ==============================================================================


@dataclass
class BufferedMessage:
    message_type: str
    timestamp: str
    content: str
    temp_file_path: Optional[Path] = None
    caption: Optional[str] = None


@dataclass
class UserBuffer:
    user_id: int
    first_timestamp: str
    messages: list[BufferedMessage] = field(default_factory=list)
    contains_voice: bool = False
    timer_task: Optional[asyncio.Task] = None


class MessageBuffer:
    def __init__(self):
        self.buffers: dict[int, UserBuffer] = {}

    def add_message(
        self,
        user_id: int,
        message_type: str,
        content: str,
        timestamp: str,
        temp_file_path: Optional[Path] = None,
        caption: Optional[str] = None,
    ) -> UserBuffer:
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
        if buffer.contains_voice:
            return get_timeout(CONFIG, "voice")
        return get_timeout(CONFIG, "text")

    def check_timeout(self, buffer: UserBuffer) -> bool:
        first_dt = datetime.strptime(buffer.first_timestamp, "%Y-%m-%d %H:%M:%S")
        current_dt = datetime.now()
        elapsed = (current_dt - first_dt).total_seconds()
        return elapsed >= self.get_timeout(buffer)

    def get_messages(self, user_id: int) -> Optional[UserBuffer]:
        return self.buffers.get(user_id)

    def clear_buffer(self, user_id: int):
        if user_id in self.buffers:
            buffer = self.buffers[user_id]
            if buffer.timer_task and not buffer.timer_task.done():
                buffer.timer_task.cancel()
            del self.buffers[user_id]


message_buffer = MessageBuffer()


# ==============================================================================
# REACTIONS (Heartbeat Menu)
# ==============================================================================


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
        text_parts = []
        image_paths = []
        
        for i, msg in enumerate(buffer.messages):
            log(f"Process: Handling message {i+1}/{len(buffer.messages)} - type: {msg.message_type}")
            
            if msg.message_type == "text":
                text_parts.append(msg.content)
                
            elif msg.message_type == "photo":
                if msg.temp_file_path:
                    dest_path = copy_image_to_notes_attachments(msg.temp_file_path)
                    if dest_path:
                        image_paths.append(dest_path)
                    if msg.temp_file_path.exists():
                        msg.temp_file_path.unlink()
                if msg.caption:
                    text_parts.append(f"[Photo Caption]: {msg.caption}")
                    
            elif msg.message_type == "voice":
                if msg.temp_file_path:
                    try:
                        transcript = transcribe_audio(msg.temp_file_path)
                        if transcript:
                            text_parts.append(f"[Voice]: {transcript}")
                    except Exception as e:
                        log(f"Process: Voice transcription failed: {e}")
                        text_parts.append(f"[Voice]: (transcription failed)")
                    finally:
                        if msg.temp_file_path.exists():
                            msg.temp_file_path.unlink()

        # Build note content
        timestamp = buffer.first_timestamp
        content_lines = []
        content_lines.append(f"=== {timestamp} ===")
        content_lines.append("")
        
        if text_parts:
            content_lines.extend(text_parts)
            content_lines.append("")
        
        for img_path in image_paths:
            content_lines.append(f"[Image attached: {img_path.name}]")
        
        note_content = "\n".join(content_lines)
        
        # Determine note mode
        note_mode = CONFIG.get("note", {}).get("mode", "new")
        
        if note_mode == "new":
            # Generate AI title or use timestamp
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            title_prefix = CONFIG.get("note", {}).get("title_prefix", "Telegram")
            
            # Try AI title first
            ai_title = generate_ai_title(note_content)
            if ai_title:
                note_title = ai_title
            else:
                note_title = f"{title_prefix} - {dt.strftime('%Y-%m-%d %H:%M')}"
            
            success = create_apple_note(note_title, note_content)
        else:
            # Append to existing note
            note_title = CONFIG.get("note", {}).get("name", "Telegram Bot")
            success = append_to_apple_note(note_title, note_content)
        
        if success:
            log(f"Created/appended note for {user_name}: {note_title}")
            
            preview = note_content[:100].replace("\n", " ")
            reply_text = f"✅ Note: {note_title}\n\n{preview}..."
            
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
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    text = update.message.text
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    voice = update.message.voice
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    temp_ogg = TEMP_DIR / f"voice_{uuid.uuid4()}.ogg"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

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
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    audio = update.message.audio
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    temp_audio = TEMP_DIR / f"audio_{uuid.uuid4()}.m4a"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

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
            message_type="voice",
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
    user_id = update.effective_user.id
    user = update.effective_user.first_name or "Unknown"
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    photo = update.message.photo[-1]
    caption = update.message.caption

    temp_photo = TEMP_DIR / f"photo_{uuid.uuid4()}.jpg"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

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
    bot_token = CONFIG.get("bot_token", "")
    
    if not bot_token:
        print("ERROR: Bot token not set!", file=sys.stderr)
        print("Set bot_token in config.yaml or TELEGRAM_APPLE_NOTES_BOT env var", file=sys.stderr)
        sys.exit(1)
    
    provider = detect_transcription_provider(CONFIG)
    log("Apple Notes Bot starting...")
    log(f"Transcription provider: {provider}")
    log(f"Log file: {LOG_FILE}")
    
    app = Application.builder().token(bot_token).build()
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.AUDIO, on_audio))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    
    print("Polling for messages...", flush=True)
    log("Bot is running...")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)


if __name__ == "__main__":
    main()
