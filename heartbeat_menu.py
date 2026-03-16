#!/usr/bin/env python3
"""
Heartbeat Menu - macOS menubar app for Apple Notes Telegram Bot
Monitors and manages the bot worker subprocess.
"""

import os
import signal
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import rumps

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config, get_log_file

CONFIG = load_config()
SCRIPT_DIR = Path(__file__).parent
WORKER_SCRIPT = SCRIPT_DIR / "apple_notes_bot.py"

# Health monitoring settings
HOURS_BEFORE_FORCED_RESTART = CONFIG.get("health", {}).get("periodic_restart_hours", 4)
MINUTES_BEFORE_HEALTH_CHECK = 5
NO_MESSAGE_TIMEOUT_MINUTES = CONFIG.get("health", {}).get("no_message_timeout_minutes", 30)
CHECK_INTERVAL = CONFIG.get("health", {}).get("check_interval_seconds", 10)

# Health log
HEALTH_LOG = Path("~/Library/Logs/apple-notes-bot-health.log").expanduser()


class HeartbeatMenu(rumps.App):
    def __init__(self):
        super().__init__("", quit_button=None)

        self.worker: subprocess.Popen | None = None
        self.is_running = False
        self.worker_start_time: datetime | None = None
        self.last_message_time: datetime | None = None

        # Icons
        self.icon_running = str(SCRIPT_DIR / "heart-icon-white.png")
        
        # Build menu
        self.status_item = rumps.MenuItem("Status: Initializing...")
        self.status_item.set_callback(None)

        self.menu = [
            self.status_item,
            None,
            rumps.MenuItem("Start Bot", callback=self.start_bot),
            rumps.MenuItem("Stop Bot", callback=self.stop_bot),
            rumps.MenuItem("Restart", callback=self.restart_app),
            None,
            rumps.MenuItem("View Log", callback=self.open_log),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Disable stop initially
        self.menu["Stop Bot"].set_callback(None)
        self.menu["Restart"].set_callback(None)

        self.icon = self.icon_running

        # Auto-start
        self.start_bot(None)

    @rumps.timer(CHECK_INTERVAL)
    def check_worker(self, _):
        """Check if worker process is alive."""
        if not self.is_running:
            return

        if self.worker and self.worker.poll() is not None:
            self.status_item.title = "Status: Crashed (restarting...)"
            self.icon = None
            self.title = "⚠️"
            rumps.notification("Apple Notes Bot", "Bot crashed", "Attempting restart...")
            self.is_running = False
            self.start_bot(None)
            return

        # Health checks
        if self.worker_start_time:
            now = datetime.now()
            uptime = now - self.worker_start_time
            uptime_hours = uptime.total_seconds() / 3600

            # Periodic restart
            if HOURS_BEFORE_FORCED_RESTART > 0 and uptime_hours >= HOURS_BEFORE_FORCED_RESTART:
                self.log_health(f"Periodic restart: uptime {uptime_hours:.1f}h")
                self.status_item.title = "Status: Periodic restart..."
                self.icon = None
                self.title = "🔄"
                self.is_running = False
                self._stop_worker()
                self.start_bot(None)
                return

            # No message timeout
            if (NO_MESSAGE_TIMEOUT_MINUTES > 0 and 
                uptime.total_seconds() > MINUTES_BEFORE_HEALTH_CHECK * 60 and 
                self.last_message_time):
                minutes_since = (now - self.last_message_time).total_seconds() / 60
                if minutes_since > NO_MESSAGE_TIMEOUT_MINUTES:
                    self.log_health(f"Restart: no messages for {minutes_since:.1f} minutes")
                    self.status_item.title = "Status: No messages (restarting...)"
                    self.icon = None
                    self.title = "💤"
                    self.is_running = False
                    self._stop_worker()
                    self.start_bot(None)
                    return

    def log_health(self, message: str):
        """Log health events."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] {message}\n"
        try:
            HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(HEALTH_LOG, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def start_log_monitor(self):
        """Monitor log for message activity."""
        def monitor():
            log_path = get_log_file(CONFIG)
            last_pos = 0
            
            while self.is_running and self.worker and self.worker.poll() is None:
                try:
                    if log_path.exists():
                        with open(log_path, "r", encoding="utf-8") as f:
                            f.seek(last_pos)
                            new_lines = f.readlines()
                            last_pos = f.tell()
                            
                            for line in new_lines:
                                if " from " in line and ("buffered" in line or "GROUPED" in line):
                                    self.last_message_time = datetime.now()
                                    break
                except Exception:
                    pass
                threading.Event().wait(5)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _stop_worker(self):
        if self.worker:
            self.worker.terminate()
            try:
                self.worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.worker.kill()
            self.worker = None

    def start_bot(self, _):
        if self.is_running:
            return

        bot_token = CONFIG.get("bot_token", "")
        if not bot_token:
            rumps.alert("Error", "Bot token not set in config.yaml")
            return

        try:
            self.worker_start_time = datetime.now()
            self.last_message_time = None

            env = os.environ.copy()
            env["TELEGRAM_APPLE_NOTES_BOT"] = bot_token

            self.worker = subprocess.Popen(
                [sys.executable, str(WORKER_SCRIPT)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            )

            self.is_running = True
            self.status_item.title = "Status: Running"
            self.icon = self.icon_running
            self.title = ""

            self.menu["Start Bot"].set_callback(None)
            self.menu["Stop Bot"].set_callback(self.stop_bot)
            self.menu["Restart"].set_callback(self.restart_app)

            self.start_log_monitor()

        except Exception as e:
            rumps.alert("Failed to start bot", str(e))

    def stop_bot(self, _):
        if not self.is_running or not self.worker:
            return

        self._stop_worker()
        self.worker = None
        self.is_running = False

        self.status_item.title = "Status: Stopped"
        self.icon = None
        self.title = "💔"

        self.menu["Start Bot"].set_callback(self.start_bot)
        self.menu["Stop Bot"].set_callback(None)
        self.menu["Restart"].set_callback(None)

    def open_log(self, _):
        log_path = get_log_file(CONFIG)
        if log_path.exists():
            subprocess.run(["open", str(log_path)])
        else:
            rumps.alert("Log not found", str(log_path))

    def quit_app(self, _):
        self.stop_bot(None)
        rumps.quit_application()

    def restart_app(self, _):
        self.stop_bot(None)
        subprocess.Popen(
            [sys.executable, str(SCRIPT_DIR / "heartbeat_menu.py")],
            detached=True,
            start_new_session=True,
        )
        rumps.quit_application()


if __name__ == "__main__":
    app = HeartbeatMenu()
    app.run()
