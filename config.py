#!/usr/bin/env python3
"""
Configuration loader for Apple Notes Telegram Bot.
Loads config from YAML file with environment variable overrides.
"""

import os
import platform
from pathlib import Path
from typing import Any

import yaml


def get_config_path() -> Path:
    """Get config file path."""
    # Check environment variable first
    if env_path := os.environ.get("APPLE_NOTES_CONFIG"):
        return Path(env_path)
    
    # Default to config.yaml in script directory
    script_dir = Path(__file__).parent
    return script_dir / "config.yaml"


def load_config() -> dict[str, Any]:
    """Load configuration from YAML file with env overrides."""
    config_path = get_config_path()
    
    # Load YAML if exists, otherwise use defaults
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
    
    # Environment variable overrides
    if bot_token := os.environ.get("TELEGRAM_APPLE_NOTES_BOT"):
        config["bot_token"] = bot_token
    
    if parakeet_path := os.environ.get("PARAKEET_PATH"):
        config.setdefault("paths", {})["parakeet_path"] = parakeet_path
    
    if whisper_model := os.environ.get("WHISPER_MODEL"):
        config.setdefault("voice", {})["whisper_model"] = whisper_model
    
    if log_file := os.environ.get("APPLE_NOTES_LOG"):
        config.setdefault("paths", {})["log_file"] = log_file
    
    # Apply defaults for missing values
    config = apply_defaults(config)
    
    return config


def apply_defaults(config: dict[str, Any]) -> dict[str, Any]:
    """Apply default values for missing configuration."""
    # Bot token (required)
    config.setdefault("bot_token", "")
    
    # Note settings
    config.setdefault("note", {})
    config["note"].setdefault("mode", "new")
    config["note"].setdefault("title_prefix", "Telegram")
    config["note"].setdefault("ai_title", True)  # Generate AI title using Ollama
    config["note"].setdefault("ai_title_model", "gemma3:4b")
    
    # Timeouts
    config.setdefault("timeouts", {})
    config["timeouts"].setdefault("text", 30)
    config["timeouts"].setdefault("voice", 120)
    config["timeouts"].setdefault("photo", 120)
    
    # Voice transcription
    config.setdefault("voice", {})
    config["voice"].setdefault("provider", "auto")
    config["voice"].setdefault("parakeet_model", "mlx-community/parakeet-tdt-0.6b-v3")
    config["voice"].setdefault("whisper_model", "base")
    
    # Paths
    config.setdefault("paths", {})
    config["paths"].setdefault("log_file", "~/Library/Logs/apple-notes-bot.log")
    config["paths"].setdefault("temp_dir", "/tmp/apple-notes-bot")
    config["paths"].setdefault("parakeet_path", "~/Local-Projects-2026/speech-to-text-parakeet")
    
    # Expand ~ in paths
    for key in ["log_file", "temp_dir", "parakeet_path"]:
        if config["paths"].get(key):
            config["paths"][key] = os.path.expanduser(config["paths"][key])
    
    # Health monitoring
    config.setdefault("health", {})
    config["health"].setdefault("periodic_restart_hours", 4)
    config["health"].setdefault("no_message_timeout_minutes", 30)
    config["health"].setdefault("check_interval_seconds", 10)
    
    return config


def detect_transcription_provider(config: dict[str, Any]) -> str:
    """Detect the best transcription provider based on hardware."""
    provider = config.get("voice", {}).get("provider", "auto")
    
    if provider != "auto":
        return provider
    
    # Auto-detect: check if Apple Silicon
    system = platform.system()
    machine = platform.machine()
    
    if system == "Darwin" and machine == "arm64":
        return "parakeet"
    else:
        return "faster-whisper"


def get_log_file(config: dict[str, Any]) -> Path:
    """Get log file path."""
    return Path(config["paths"]["log_file"])


def get_temp_dir(config: dict[str, Any]) -> Path:
    """Get temp directory path."""
    return Path(config["paths"]["temp_dir"])


def get_timeout(config: dict[str, Any], message_type: str) -> int:
    """Get timeout for message type."""
    return config["timeouts"].get(message_type, 30)


def get_note_ai_title(config: dict[str, Any]) -> bool:
    """Whether to generate AI titles for notes."""
    return config.get("note", {}).get("ai_title", True)


def get_note_ai_title_model(config: dict[str, Any]) -> str:
    """Get the Ollama model for AI title generation."""
    return config.get("note", {}).get("ai_title_model", "gemma3:4b")
