#!/usr/bin/env python3
"""
SUPER DUPER TELEGRAM BOT HOSTER - ULTIMATE AQUATIC EDITION
- Runs a Master Control Bot (userbot or bot)
- Manages multiple hosted bots (start/stop/restart)
- Manages userbots (via OTP login + Pyrogram sessions)
- Manages arbitrary Python/JS scripts (upload, run, stop, logs)
- Inline buttons, animations, aquatic theme
- Async performance with Pyrogram
- Real-time database storage (aiosqlite)
- Health check & auto-restart system
- Web Dashboard with JS Animations (aiohttp)
- Full web control, more animations
- Subscription, admin, broadcast system
"""

import asyncio
import random
import sys
import time
import os
import shutil
import subprocess
import threading
import re
import zipfile
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Set
import traceback   # added for detailed error logs

# Pyrogram imports
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

# Database import
import aiosqlite

# Web server import
from aiohttp import web

# Additional
import psutil

# --------------------------
# CONFIGURATION
# --------------------------
MASTER_API_ID = 33491590
MASTER_API_HASH = "35eb3cd440c7ad282cfdc2ce557e37f6"
MASTER_BOT_TOKEN = "8602762499:AAHRU4hAlT6G94Iz5ZHmPEjekT80G5Z4fpk"
MASTER_SESSION_STRING = None  # set if using userbot as master

OWNER_ID = 2119464081
SUPPORT_USERNAME = "@fxrsale"
MAX_USERBOTS_PER_USER = 3
MAX_SCRIPTS_PER_USER = 10

HOSTED_BOTS = []  # will be loaded from DB

# --------------------------
# ANIMATIONS (EXPANDED)
# --------------------------
ANIMATIONS = [
    "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif",
    "https://media.giphy.com/media/l0HlNaQ6gWfllcjDO/giphy.gif",
    "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
    "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif",
    "https://media.giphy.com/media/3o7aD2saalBwwftFIY/giphy.gif",
    "https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif",
    "https://media.giphy.com/media/l4FGuhL4U2WyjdkaY/giphy.gif",
    "https://media.giphy.com/media/3o7aD5jJzJzJZq5wM0/giphy.gif",
    "https://media.giphy.com/media/3o6Zt8HWq4g9fW8t4k/giphy.gif",
    "https://media.giphy.com/media/xT0xeMA62E1XIlupj2/giphy.gif",
]

EXTRA_ANIMATIONS = [
    "https://media.giphy.com/media/3o7aCTfyhYawdOXcFW/giphy.gif",
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/3o7aD2sG6Wf2rB3K3C/giphy.gif",
    "https://media.giphy.com/media/3o7aCT8bDhf2iW0m2A/giphy.gif",
    "https://media.giphy.com/media/3o7aTzG6i5tXlV6C7K/giphy.gif",
]

# More new animations
NEW_ANIMATIONS = [
    "https://media.giphy.com/media/3o6gb8e3wHnqCgG7Bm/giphy.gif",
    "https://media.giphy.com/media/3o6Zt8mJ8l3bXQG7eM/giphy.gif",
    "https://media.giphy.com/media/3o7TKqfH9pZ0VnPqY4/giphy.gif",
    "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif",
    "https://media.giphy.com/media/3o6gDUGtYPTQl8F4Gk/giphy.gif",
]

ANIMATIONS.extend(NEW_ANIMATIONS)

DB_PATH = "bot_hoster.db"
HEALTH_CHECK_INTERVAL = 30
WEB_PORT = int(os.environ.get("PORT", "8080"))   # use Railway's PORT env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, "upload_bots")
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)

# --------------------------
# DATABASE SETUP (extended)
# --------------------------
async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        # existing bots table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                name TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                status TEXT DEFAULT 'stopped'
            )
        """)
        # crash log
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crash_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT,
                timestamp TEXT,
                event TEXT
            )
        """)
        # userbots table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS userbots (
                name TEXT PRIMARY KEY,
                session_string TEXT NOT NULL,
                status TEXT DEFAULT 'stopped',
                user_id INTEGER
            )
        """)
        # users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                joined_at TEXT,
                is_premium INTEGER DEFAULT 0,
                expiry TEXT
            )
        """)
        # admins table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
        """)
        # user_files table (for arbitrary scripts)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_files (
                user_id INTEGER,
                file_name TEXT,
                file_type TEXT,
                PRIMARY KEY (user_id, file_name)
            )
        """)
        # subscriptions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                expiry TEXT
            )
        """)
        # blocked users
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked (
                user_id INTEGER PRIMARY KEY
            )
        """)
        # insert owner as admin
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
        await db.commit()

# --------------------------
# DATABASE FUNCTIONS (extended)
# --------------------------
# Bots (existing)
async def db_add_bot(name, token):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO bots (name, token, status) VALUES (?, ?, ?)", (name, token, "stopped"))
        await db.commit()

async def db_remove_bot(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bots WHERE name = ?", (name,))
        await db.commit()

async def db_update_bot_status(name, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE bots SET status = ? WHERE name = ?", (status, name))
        await db.commit()

async def db_get_all_bots():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, token, status FROM bots")
        rows = await cursor.fetchall()
        return rows

async def db_log_crash(bot_name, event):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO crash_log (bot_name, timestamp, event) VALUES (?, ?, ?)", (bot_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), event))
        await db.commit()

async def db_get_recent_logs(limit=5):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT bot_name, timestamp, event FROM crash_log ORDER BY id DESC LIMIT ?", (limit,))
        return await cursor.fetchall()

# Userbots (extended with user_id)
async def db_add_userbot(name, session_string, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO userbots (name, session_string, status, user_id) VALUES (?, ?, ?, ?)", (name, session_string, "stopped", user_id))
        await db.commit()

async def db_remove_userbot(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM userbots WHERE name = ?", (name,))
        await db.commit()

async def db_update_userbot_status(name, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE userbots SET status = ? WHERE name = ?", (status, name))
        await db.commit()

async def db_get_userbots_for_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, session_string, status FROM userbots WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        return rows

async def db_get_all_userbots():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, session_string, status, user_id FROM userbots")
        rows = await cursor.fetchall()
        return rows

# User management
async def db_add_user(user_id, first_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, first_name, joined_at) VALUES (?, ?, ?)", (user_id, first_name, datetime.now().isoformat()))
        await db.commit()

async def db_get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def db_set_premium(user_id, expiry_days):
    expiry = (datetime.now() + timedelta(days=expiry_days)).isoformat() if expiry_days else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_premium = 1, expiry = ? WHERE user_id = ?", (expiry, user_id))
        await db.commit()

async def db_remove_premium(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_premium = 0, expiry = NULL WHERE user_id = ?", (user_id,))
        await db.commit()

# Admins
async def db_add_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def db_remove_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()

async def db_get_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM admins")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

# User files (for arbitrary scripts)
async def db_add_user_file(user_id, file_name, file_type):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)", (user_id, file_name, file_type))
        await db.commit()

async def db_remove_user_file(user_id, file_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_files WHERE user_id = ? AND file_name = ?", (user_id, file_name))
        await db.commit()

async def db_get_user_files(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT file_name, file_type FROM user_files WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        return rows

async def db_get_all_user_files():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, file_name, file_type FROM user_files")
        rows = await cursor.fetchall()
        return rows

# Subscriptions (legacy, but we use users table premium)
# Blocked
async def db_block_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO blocked (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def db_unblock_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blocked WHERE user_id = ?", (user_id,))
        await db.commit()

async def db_is_blocked(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM blocked WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None

# --------------------------
# BOT MANAGER (unchanged)
# --------------------------
class BotManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self.bot_info: Dict[str, dict] = {}

    async def load_from_db(self):
        rows = await db_get_all_bots()
        for name, token, status in rows:
            client = Client(name=f"hosted_{name}", api_id=MASTER_API_ID, api_hash=MASTER_API_HASH, bot_token=token, in_memory=True)
            self.clients[name] = client
            self.bot_info[name] = {"token": token, "status": status, "client": client}
            if status == "running":
                try:
                    await client.start()
                    self.bot_info[name]["status"] = "running"
                except Exception as e:
                    await db_log_crash(name, f"Failed to auto-start on load: {e}")
                    self.bot_info[name]["status"] = "stopped"
                    await db_update_bot_status(name, "stopped")

    async def add_bot(self, name: str, token: str):
        if name in self.bot_info:
            return False, "Bot name already exists."
        client = Client(name=f"hosted_{name}", api_id=MASTER_API_ID, api_hash=MASTER_API_HASH, bot_token=token, in_memory=True)
        self.clients[name] = client
        self.bot_info[name] = {"token": token, "status": "stopped", "client": client}
        await db_add_bot(name, token)
        return True, f"Bot '{name}' added successfully."

    async def remove_bot(self, name: str):
        if name not in self.bot_info:
            return False, "Bot not found."
        client = self.clients.pop(name, None)
        if client and client.is_initialized:
            await client.stop()
        self.bot_info.pop(name, None)
        await db_remove_bot(name)
        return True, f"Bot '{name}' removed."

    async def start_bot(self, name: str):
        if name not in self.bot_info:
            return False, "Bot not found."
        client = self.clients[name]
        if self.bot_info[name]["status"] == "running":
            return False, "Bot is already running."
        try:
            await client.start()
            self.bot_info[name]["status"] = "running"
            await db_update_bot_status(name, "running")
            return True, f"Bot '{name}' started."
        except Exception as e:
            await db_log_crash(name, f"Start failed: {e}")
            return False, f"Failed to start bot: {e}"

    async def stop_bot(self, name: str):
        if name not in self.bot_info:
            return False, "Bot not found."
        client = self.clients[name]
        if self.bot_info[name]["status"] == "stopped":
            return False, "Bot is already stopped."
        try:
            await client.stop()
            self.bot_info[name]["status"] = "stopped"
            await db_update_bot_status(name, "stopped")
            return True, f"Bot '{name}' stopped."
        except Exception as e:
            return False, f"Failed to stop bot: {e}"

    async def restart_bot(self, name: str):
        stop_result = await self.stop_bot(name)
        if not stop_result[0] and "already stopped" not in stop_result[1]:
            return stop_result
        return await self.start_bot(name)

    def get_status(self) -> str:
        if not self.bot_info:
            return "No bots hosted yet."
        lines = []
        for name, info in self.bot_info.items():
            status_emoji = "🟢" if info["status"] == "running" else "🔴"
            lines.append(f"{status_emoji} **{name}** - {info['status']}")
        return "\n".join(lines)

    def list_bot_names(self):
        return list(self.bot_info.keys())

    async def health_check(self):
        for name, info in self.bot_info.items():
            if info["status"] == "running":
                client = self.clients.get(name)
                if client and not client.is_initialized:
                    await db_log_crash(name, "Detected down by health check")
                    success, msg = await self.restart_bot(name)
                    if success:
                        await db_log_crash(name, "Auto-restarted successfully")
                    else:
                        await db_log_crash(name, f"Auto-restart failed: {msg}")

# --------------------------
# USERBOT MANAGER (extended with user_id)
# --------------------------
class UserbotManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self.userbot_info: Dict[str, dict] = {}

    async def load_from_db(self):
        rows = await db_get_all_userbots()
        for name, session_string, status, user_id in rows:
            client = Client(name=f"hosted_userbot_{name}", api_id=MASTER_API_ID, api_hash=MASTER_API_HASH, session_string=session_string, in_memory=True)
            self.clients[name] = client
            self.userbot_info[name] = {"session_string": session_string, "status": status, "client": client, "user_id": user_id}
            if status == "running":
                try:
                    await client.start()
                    self.userbot_info[name]["status"] = "running"
                except Exception as e:
                    await db_log_crash(f"userbot:{name}", f"Failed to auto-start on load: {e}")
                    self.userbot_info[name]["status"] = "stopped"
                    await db_update_userbot_status(name, "stopped")

    async def add_userbot(self, name: str, session_string: str, user_id: int):
        if name in self.userbot_info:
            return False, "Userbot name already exists."
        client = Client(name=f"hosted_userbot_{name}", api_id=MASTER_API_ID, api_hash=MASTER_API_HASH, session_string=session_string, in_memory=True)
        self.clients[name] = client
        self.userbot_info[name] = {"session_string": session_string, "status": "stopped", "client": client, "user_id": user_id}
        await db_add_userbot(name, session_string, user_id)
        return True, f"Userbot '{name}' added successfully."

    async def remove_userbot(self, name: str):
        if name not in self.userbot_info:
            return False, "Userbot not found."
        client = self.clients.pop(name, None)
        if client and client.is_initialized:
            await client.stop()
        self.userbot_info.pop(name, None)
        await db_remove_userbot(name)
        return True, f"Userbot '{name}' removed."

    async def start_userbot(self, name: str):
        if name not in self.userbot_info:
            return False, "Userbot not found."
        client = self.clients[name]
        if self.userbot_info[name]["status"] == "running":
            return False, "Userbot is already running."
        try:
            await client.start()
            self.userbot_info[name]["status"] = "running"
            await db_update_userbot_status(name, "running")
            return True, f"Userbot '{name}' started."
        except Exception as e:
            await db_log_crash(f"userbot:{name}", f"Start failed: {e}")
            return False, f"Failed to start userbot: {e}"

    async def stop_userbot(self, name: str):
        if name not in self.userbot_info:
            return False, "Userbot not found."
        client = self.clients[name]
        if self.userbot_info[name]["status"] == "stopped":
            return False, "Userbot is already stopped."
        try:
            await client.stop()
            self.userbot_info[name]["status"] = "stopped"
            await db_update_userbot_status(name, "stopped")
            return True, f"Userbot '{name}' stopped."
        except Exception as e:
            return False, f"Failed to stop userbot: {e}"

    async def restart_userbot(self, name: str):
        stop_result = await self.stop_userbot(name)
        if not stop_result[0] and "already stopped" not in stop_result[1]:
            return stop_result
        return await self.start_userbot(name)

    def get_status(self, user_id=None) -> str:
        if not self.userbot_info:
            return "No userbots hosted yet."
        lines = []
        for name, info in self.userbot_info.items():
            if user_id is not None and info.get("user_id") != user_id:
                continue
            status_emoji = "🟢" if info["status"] == "running" else "🔴"
            lines.append(f"{status_emoji} **{name}** - {info['status']}")
        return "\n".join(lines) if lines else "No userbots for this user."

    def list_userbot_names(self, user_id=None):
        if user_id is None:
            return list(self.userbot_info.keys())
        return [name for name, info in self.userbot_info.items() if info.get("user_id") == user_id]

    async def health_check(self):
        for name, info in self.userbot_info.items():
            if info["status"] == "running":
                client = self.clients.get(name)
                if client and not client.is_initialized:
                    await db_log_crash(f"userbot:{name}", "Detected down by health check")
                    success, msg = await self.restart_userbot(name)
                    if success:
                        await db_log_crash(f"userbot:{name}", "Auto-restarted successfully")
                    else:
                        await db_log_crash(f"userbot:{name}", f"Auto-restart failed: {msg}")

# --------------------------
# SCRIPT MANAGER (for arbitrary py/js scripts)
# --------------------------
class ScriptManager:
    def __init__(self):
        self.processes: Dict[str, subprocess.Popen] = {}
        self.log_files: Dict[str, str] = {}
        self.script_info: Dict[str, dict] = {}

    def get_user_folder(self, user_id):
        folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
        os.makedirs(folder, exist_ok=True)
        return folder

    async def upload_script(self, user_id: int, file_name: str, file_content: bytes, file_type: str) -> Tuple[bool, str]:
        # Check limit
        files = await db_get_user_files(user_id)
        if len(files) >= MAX_SCRIPTS_PER_USER:
            return False, f"Script limit ({MAX_SCRIPTS_PER_USER}) reached."
        user_folder = self.get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)
        # Check if already exists
        if os.path.exists(file_path):
            return False, f"File '{file_name}' already exists."
        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_content)
        await db_add_user_file(user_id, file_name, file_type)
        return True, f"File '{file_name}' uploaded."

    async def delete_script(self, user_id: int, file_name: str) -> Tuple[bool, str]:
        # Stop if running
        script_key = f"{user_id}_{file_name}"
        if script_key in self.processes:
            self.stop_script(user_id, file_name)
        user_folder = self.get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(log_path):
            os.remove(log_path)
        await db_remove_user_file(user_id, file_name)
        return True, f"Deleted '{file_name}'."

    def start_script(self, user_id: int, file_name: str, message_obj) -> bool:
        script_key = f"{user_id}_{file_name}"
        if script_key in self.processes:
            return False
        user_folder = self.get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)
        if not os.path.exists(file_path):
            return False
        # Determine file type from extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext == '.py':
            cmd = [sys.executable, file_path]
        elif ext == '.js':
            cmd = ['node', file_path]
        else:
            return False
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_path, 'w', encoding='utf-8', errors='ignore')
        try:
            process = subprocess.Popen(cmd, cwd=user_folder, stdout=log_file, stderr=log_file, stdin=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
            self.processes[script_key] = process
            self.log_files[script_key] = log_path
            self.script_info[script_key] = {"user_id": user_id, "file_name": file_name, "start_time": datetime.now(), "process": process}
            return True
        except Exception as e:
            log_file.close()
            return False

    def stop_script(self, user_id: int, file_name: str):
        script_key = f"{user_id}_{file_name}"
        if script_key not in self.processes:
            return
        process = self.processes[script_key]
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
        # close log file
        log_path = self.log_files.get(script_key)
        if log_path and os.path.exists(log_path):
            # we can't close the file because it's owned by process, but we can reopen and append? Not needed.
            pass
        del self.processes[script_key]
        del self.log_files[script_key]
        del self.script_info[script_key]

    def is_running(self, user_id: int, file_name: str) -> bool:
        script_key = f"{user_id}_{file_name}"
        if script_key not in self.processes:
            return False
        process = self.processes[script_key]
        return process.poll() is None

    def get_log(self, user_id: int, file_name: str, max_kb=100) -> str:
        user_folder = self.get_user_folder(user_id)
        log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        if not os.path.exists(log_path):
            return "No log file."
        file_size = os.path.getsize(log_path)
        if file_size == 0:
            return "(Empty log)"
        if file_size > max_kb * 1024:
            with open(log_path, 'rb') as f:
                f.seek(-max_kb * 1024, os.SEEK_END)
                data = f.read()
            content = data.decode('utf-8', errors='ignore')
            return f"(Last {max_kb} KB)\n...\n{content}"
        else:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()

    def get_running_scripts(self, user_id: int = None) -> List[dict]:
        result = []
        for key, info in self.script_info.items():
            if user_id is not None and info["user_id"] != user_id:
                continue
            result.append(info)
        return result

# Initialize managers
manager = BotManager()
userbot_manager = UserbotManager()
script_manager = ScriptManager()

# --------------------------
# MASTER CLIENT SETUP
# --------------------------
if MASTER_BOT_TOKEN:
    master = Client("master_bot", api_id=MASTER_API_ID, api_hash=MASTER_API_HASH, bot_token=MASTER_BOT_TOKEN)
elif MASTER_SESSION_STRING:
    master = Client("master_userbot", api_id=MASTER_API_ID, api_hash=MASTER_API_HASH, session_string=MASTER_SESSION_STRING)
else:
    print("Please set MASTER_BOT_TOKEN or MASTER_SESSION_STRING.")
    sys.exit(1)

# --------------------------
# HELPER FUNCTIONS
# --------------------------
async def send_animation(message: Message):
    gif_url = random.choice(ANIMATIONS)
    await message.reply_animation(animation=gif_url, caption="🌊 **Aquatic Power!**", parse_mode=ParseMode.MARKDOWN)

async def send_extra_animation(message: Message):
    gif_url = random.choice(EXTRA_ANIMATIONS)
    await message.reply_animation(animation=gif_url, caption="🐠 **Extra Aquatic Animation!**", parse_mode=ParseMode.MARKDOWN)

async def is_admin(user_id: int) -> bool:
    admins = await db_get_admins()
    return user_id in admins

async def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

async def is_premium(user_id: int) -> bool:
    user = await db_get_user(user_id)
    if not user:
        return False
    # user tuple: (user_id, first_name, joined_at, is_premium, expiry)
    if user[3] == 1:
        expiry = user[4]
        if expiry and datetime.fromisoformat(expiry) > datetime.now():
            return True
        else:
            # expired
            await db_remove_premium(user_id)
            return False
    return False

# --------------------------
# INLINE KEYBOARDS (extended)
# --------------------------
async def main_menu_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton("📋 List Bots", callback_data="list_bots"), InlineKeyboardButton("➕ Add Bot", callback_data="add_bot")],
        [InlineKeyboardButton("▶️ Start Bot", callback_data="start_bot"), InlineKeyboardButton("⏹️ Stop Bot", callback_data="stop_bot")],
        [InlineKeyboardButton("🔄 Restart Bot", callback_data="restart_bot"), InlineKeyboardButton("🗑️ Remove Bot", callback_data="remove_bot")],
        [InlineKeyboardButton("👥 List Userbots", callback_data="list_userbots"), InlineKeyboardButton("➕ Add Userbot", callback_data="add_userbot")],
        [InlineKeyboardButton("▶️ Start Userbot", callback_data="start_userbot"), InlineKeyboardButton("⏹️ Stop Userbot", callback_data="stop_userbot")],
        [InlineKeyboardButton("🔄 Restart Userbot", callback_data="restart_userbot"), InlineKeyboardButton("🗑️ Remove Userbot", callback_data="remove_userbot")],
        [InlineKeyboardButton("📁 My Scripts", callback_data="list_scripts"), InlineKeyboardButton("📤 Upload Script", callback_data="upload_script")],
        [InlineKeyboardButton("▶️ Start Script", callback_data="start_script"), InlineKeyboardButton("⏹️ Stop Script", callback_data="stop_script")],
        [InlineKeyboardButton("📜 View Logs", callback_data="view_logs"), InlineKeyboardButton("🗑️ Delete Script", callback_data="delete_script")],
        [InlineKeyboardButton("🏓 Ping", callback_data="ping"), InlineKeyboardButton("🎬 Animation", callback_data="animation")],
        [InlineKeyboardButton("🎞️ More Animations", callback_data="extra_animation"), InlineKeyboardButton("❤️ Health", callback_data="health")],
        [InlineKeyboardButton("🌐 Web Dashboard", callback_data="web")],
    ]
    if await is_owner(user_id) or await is_admin(user_id):
        buttons.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

def back_to_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]])

def bot_selection_keyboard(action: str):
    bot_names = manager.list_bot_names()
    if not bot_names:
        return None, "No bots available. Add a bot first."
    buttons = []
    for name in bot_names:
        buttons.append([InlineKeyboardButton(name, callback_data=f"{action}:{name}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons), None

def userbot_selection_keyboard(action: str, user_id):
    names = userbot_manager.list_userbot_names(user_id)
    if not names:
        return None, "No userbots available. Add a userbot first."
    buttons = []
    for name in names:
        buttons.append([InlineKeyboardButton(name, callback_data=f"ub_{action}:{name}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons), None

def script_selection_keyboard(action: str, user_id):
    files = asyncio.run(db_get_user_files(user_id))  # but we are in async, so we'll use a sync version? We'll handle in callback.
    # We'll use a dict to avoid async issues.
    return None, None  # will be handled in callback

# --------------------------
# WEB DASHBOARD (extended with scripts)
# --------------------------
HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>🌊 Super Duper Bot Hoster</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            color: white;
            margin: 0;
            padding: 20px;
            animation: waveBackground 15s ease infinite;
            background-size: 400% 400%;
        }
        @keyframes waveBackground {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            animation: float 3s ease-in-out infinite;
        }
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }
        .bot-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            backdrop-filter: blur(5px);
            animation: fadeInUp 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .status {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        .running { background: #4CAF50; }
        .stopped { background: #f44336; }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }
        .controls {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }
        .btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn:hover {
            background: rgba(255, 255, 255, 0.4);
        }
        .bubble {
            position: fixed;
            bottom: -50px;
            width: 20px;
            height: 20px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            animation: bubbleUp 10s linear infinite;
        }
        @keyframes bubbleUp {
            0% { bottom: -50px; opacity: 0.8; }
            100% { bottom: 110%; opacity: 0; }
        }
        .fish {
            position: fixed;
            font-size: 30px;
            animation: swim linear infinite;
        }
        @keyframes swim {
            0% { left: -10%; transform: translateX(0); }
            100% { left: 110%; transform: translateX(0); }
        }
        .section-title {
            font-size: 1.5em;
            margin-top: 30px;
            border-bottom: 1px solid rgba(255,255,255,0.3);
            padding-bottom: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌊 Super Duper Bot Hoster</h1>
        <button class="btn" onclick="fetchStatus()" style="margin-bottom:10px;">🔄 Refresh</button>
        <div id="botList"></div>
    </div>

    <script>
        function createBubbles() {
            for (let i = 0; i < 20; i++) {
                const bubble = document.createElement('div');
                bubble.className = 'bubble';
                bubble.style.left = Math.random() * 100 + '%';
                bubble.style.animationDuration = (Math.random() * 8 + 5) + 's';
                bubble.style.animationDelay = Math.random() * 5 + 's';
                document.body.appendChild(bubble);
            }
        }

        function createFish() {
            const fishEmojis = ['🐟', '🐠', '🐡', '🦈', '🐙', '🦑'];
            for (let i = 0; i < 8; i++) {
                const fish = document.createElement('div');
                fish.className = 'fish';
                fish.textContent = fishEmojis[Math.floor(Math.random() * fishEmojis.length)];
                fish.style.top = Math.random() * 80 + 10 + '%';
                fish.style.animationDuration = (Math.random() * 10 + 8) + 's';
                fish.style.animationDelay = Math.random() * 5 + 's';
                document.body.appendChild(fish);
            }
        }

        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                const botList = document.getElementById('botList');
                botList.innerHTML = '';
                // Bots
                if (data.bots.length > 0) {
                    const header = document.createElement('div');
                    header.className = 'section-title';
                    header.textContent = '🤖 Hosted Bots';
                    botList.appendChild(header);
                    data.bots.forEach(bot => {
                        const card = document.createElement('div');
                        card.className = 'bot-card';
                        card.innerHTML = `
                            <div>
                                <span class="status ${bot.status}"></span>
                                <strong>${bot.name}</strong> - ${bot.status}
                            </div>
                            <div class="controls">
                                <button class="btn" onclick="controlBot('start', '${bot.name}')">▶️ Start</button>
                                <button class="btn" onclick="controlBot('stop', '${bot.name}')">⏹️ Stop</button>
                                <button class="btn" onclick="controlBot('restart', '${bot.name}')">🔄 Restart</button>
                                <button class="btn" onclick="controlBot('remove', '${bot.name}')">🗑️ Remove</button>
                            </div>
                        `;
                        botList.appendChild(card);
                    });
                }
                // Userbots
                if (data.userbots.length > 0) {
                    const header = document.createElement('div');
                    header.className = 'section-title';
                    header.textContent = '👥 Hosted Userbots';
                    botList.appendChild(header);
                    data.userbots.forEach(ubot => {
                        const card = document.createElement('div');
                        card.className = 'bot-card';
                        card.innerHTML = `
                            <div>
                                <span class="status ${ubot.status}"></span>
                                <strong>${ubot.name}</strong> - ${ubot.status} (userbot)
                            </div>
                            <div class="controls">
                                <button class="btn" onclick="controlUserbot('start', '${ubot.name}')">▶️ Start</button>
                                <button class="btn" onclick="controlUserbot('stop', '${ubot.name}')">⏹️ Stop</button>
                                <button class="btn" onclick="controlUserbot('restart', '${ubot.name}')">🔄 Restart</button>
                                <button class="btn" onclick="controlUserbot('remove', '${ubot.name}')">🗑️ Remove</button>
                            </div>
                        `;
                        botList.appendChild(card);
                    });
                }
                // Scripts
                if (data.scripts.length > 0) {
                    const header = document.createElement('div');
                    header.className = 'section-title';
                    header.textContent = '📁 Hosted Scripts';
                    botList.appendChild(header);
                    data.scripts.forEach(script => {
                        const card = document.createElement('div');
                        card.className = 'bot-card';
                        card.innerHTML = `
                            <div>
                                <span class="status ${script.status}"></span>
                                <strong>${script.name}</strong> - ${script.status} (${script.type})
                            </div>
                            <div class="controls">
                                <button class="btn" onclick="controlScript('start', '${script.name}')">▶️ Start</button>
                                <button class="btn" onclick="controlScript('stop', '${script.name}')">⏹️ Stop</button>
                                <button class="btn" onclick="controlScript('logs', '${script.name}')">📜 Logs</button>
                                <button class="btn" onclick="controlScript('delete', '${script.name}')">🗑️ Delete</button>
                            </div>
                        `;
                        botList.appendChild(card);
                    });
                }
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }

        async function controlBot(action, name) {
            try {
                const response = await fetch(`/api/bot/${action}/${name}`, { method: 'POST' });
                const result = await response.json();
                alert(result.message || result.error);
                fetchStatus();
            } catch (error) {
                console.error('Error controlling bot:', error);
                alert('Failed to perform action');
            }
        }

        async function controlUserbot(action, name) {
            try {
                const response = await fetch(`/api/userbot/${action}/${name}`, { method: 'POST' });
                const result = await response.json();
                alert(result.message || result.error);
                fetchStatus();
            } catch (error) {
                console.error('Error controlling userbot:', error);
                alert('Failed to perform action');
            }
        }

        async function controlScript(action, name) {
            try {
                const response = await fetch(`/api/script/${action}/${name}`, { method: 'POST' });
                const result = await response.json();
                alert(result.message || result.error);
                fetchStatus();
            } catch (error) {
                console.error('Error controlling script:', error);
                alert('Failed to perform action');
            }
        }

        createBubbles();
        createFish();
        fetchStatus();
        setInterval(fetchStatus, 5000);
    </script>
</body>
</html>
"""

async def handle_web_index(request):
    return web.Response(text=HTML_DASHBOARD, content_type='text/html')

async def handle_api_status(request):
    bots = [{"name": name, "status": info["status"]} for name, info in manager.bot_info.items()]
    userbots = [{"name": name, "status": info["status"]} for name, info in userbot_manager.userbot_info.items()]
    # Scripts: get all running scripts (we need to fetch from script_manager)
    # We'll get all user files from DB and check status
    scripts = []
    all_files = await db_get_all_user_files()
    for user_id, file_name, file_type in all_files:
        status = "running" if script_manager.is_running(user_id, file_name) else "stopped"
        scripts.append({"name": file_name, "status": status, "type": file_type})
    return web.json_response({"bots": bots, "userbots": userbots, "scripts": scripts})

# Bot API handlers
async def handle_api_bot_start(request):
    bot_name = request.match_info['name']
    success, msg = await manager.start_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_bot_stop(request):
    bot_name = request.match_info['name']
    success, msg = await manager.stop_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_bot_restart(request):
    bot_name = request.match_info['name']
    success, msg = await manager.restart_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_bot_remove(request):
    bot_name = request.match_info['name']
    success, msg = await manager.remove_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

# Userbot API handlers
async def handle_api_userbot_start(request):
    name = request.match_info['name']
    success, msg = await userbot_manager.start_userbot(name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_userbot_stop(request):
    name = request.match_info['name']
    success, msg = await userbot_manager.stop_userbot(name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_userbot_restart(request):
    name = request.match_info['name']
    success, msg = await userbot_manager.restart_userbot(name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_userbot_remove(request):
    name = request.match_info['name']
    success, msg = await userbot_manager.remove_userbot(name)
    return web.json_response({"success": success, "message": msg})

# Script API handlers
async def handle_api_script_start(request):
    name = request.match_info['name']
    # Need to find user_id for this script from DB
    # We'll assume the script name is unique across users, but we need user_id.
    # We'll iterate files to find matching name.
    all_files = await db_get_all_user_files()
    for uid, fname, ftype in all_files:
        if fname == name:
            user_id = uid
            break
    else:
        return web.json_response({"success": False, "message": "Script not found"})
    # Check if already running
    if script_manager.is_running(user_id, name):
        return web.json_response({"success": False, "message": "Script already running"})
    # We need a message object for logs? We'll just start without reply.
    # We'll simulate a dummy message object.
    class DummyMessage:
        chat = None
        reply_text = lambda self, text: None
    dummy = DummyMessage()
    success = script_manager.start_script(user_id, name, dummy)
    if success:
        return web.json_response({"success": True, "message": f"Started {name}"})
    else:
        return web.json_response({"success": False, "message": "Failed to start script"})

async def handle_api_script_stop(request):
    name = request.match_info['name']
    all_files = await db_get_all_user_files()
    for uid, fname, ftype in all_files:
        if fname == name:
            user_id = uid
            break
    else:
        return web.json_response({"success": False, "message": "Script not found"})
    if not script_manager.is_running(user_id, name):
        return web.json_response({"success": False, "message": "Script not running"})
    script_manager.stop_script(user_id, name)
    return web.json_response({"success": True, "message": f"Stopped {name}"})

async def handle_api_script_logs(request):
    name = request.match_info['name']
    all_files = await db_get_all_user_files()
    for uid, fname, ftype in all_files:
        if fname == name:
            user_id = uid
            break
    else:
        return web.json_response({"success": False, "message": "Script not found"})
    log_content = script_manager.get_log(user_id, name)
    return web.json_response({"success": True, "log": log_content})

async def handle_api_script_delete(request):
    name = request.match_info['name']
    all_files = await db_get_all_user_files()
    for uid, fname, ftype in all_files:
        if fname == name:
            user_id = uid
            break
    else:
        return web.json_response({"success": False, "message": "Script not found"})
    success, msg = await script_manager.delete_script(user_id, name)
    return web.json_response({"success": success, "message": msg})

def create_web_app():
    app = web.Application()
    app.router.add_get('/', handle_web_index)
    app.router.add_get('/api/status', handle_api_status)
    # Bot routes
    app.router.add_post('/api/bot/start/{name}', handle_api_bot_start)
    app.router.add_post('/api/bot/stop/{name}', handle_api_bot_stop)
    app.router.add_post('/api/bot/restart/{name}', handle_api_bot_restart)
    app.router.add_post('/api/bot/remove/{name}', handle_api_bot_remove)
    # Userbot routes
    app.router.add_post('/api/userbot/start/{name}', handle_api_userbot_start)
    app.router.add_post('/api/userbot/stop/{name}', handle_api_userbot_stop)
    app.router.add_post('/api/userbot/restart/{name}', handle_api_userbot_restart)
    app.router.add_post('/api/userbot/remove/{name}', handle_api_userbot_remove)
    # Script routes
    app.router.add_post('/api/script/start/{name}', handle_api_script_start)
    app.router.add_post('/api/script/stop/{name}', handle_api_script_stop)
    app.router.add_post('/api/script/logs/{name}', handle_api_script_logs)
    app.router.add_post('/api/script/delete/{name}', handle_api_script_delete)
    return app

async def start_web_server():
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)
    await site.start()
    print(f"🌐 Web dashboard running on http://0.0.0.0:{WEB_PORT}")

# --------------------------
# OTP LOGIN (Pyrogram version)
# --------------------------
# We'll store pending logins temporarily
pending_logins = {}

async def start_otp_login(user_id, phone):
    try:
        client = Client(f"login_{user_id}", api_id=MASTER_API_ID, api_hash=MASTER_API_HASH, in_memory=True)
        await client.connect()
        sent = await client.send_code(phone)
        pending_logins[user_id] = {"client": client, "phone": phone, "phone_code_hash": sent.phone_code_hash}
        return True, "OTP sent. Please send the code via /code <code>"
    except Exception as e:
        return False, str(e)

async def complete_otp_login(user_id, code):
    data = pending_logins.get(user_id)
    if not data:
        return False, "No pending login. Start with /host"
    client = data["client"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        session_string = await client.export_session_string()
        await client.disconnect()
        pending_logins.pop(user_id, None)
        return True, session_string
    except SessionPasswordNeeded:
        return "2fa", "2FA required. Send /2fa <password>"
    except PhoneCodeInvalid:
        return False, "Invalid code. Try again."
    except PhoneCodeExpired:
        return False, "Code expired. Start /host again."
    except Exception as e:
        return False, str(e)

async def complete_2fa_login(user_id, password):
    data = pending_logins.get(user_id)
    if not data:
        return False, "No pending login."
    client = data["client"]
    try:
        await client.sign_in(password=password)
        session_string = await client.export_session_string()
        await client.disconnect()
        pending_logins.pop(user_id, None)
        return True, session_string
    except Exception as e:
        return False, str(e)

# --------------------------
# MASTER COMMAND HANDLERS
# --------------------------
@master.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    await db_add_user(user_id, message.from_user.first_name)
    await send_animation(message)
    await message.reply_text(
        "**🌊 Welcome to the Super Duper Bot Hoster!**\n"
        "Manage your hosted bots, userbots, and scripts with the menu below:",
        reply_markup=await main_menu_keyboard(user_id),
        parse_mode=ParseMode.MARKDOWN
    )

@master.on_message(filters.command("help"))
async def help_command(client, message):
    help_text = """
**🤖 Bot Hoster Commands**
- `/start` - Main menu
- `/help` - This help
- `/addbot <name> <token>` - Add a new bot
- `/removebot <name>` - Remove a bot
- `/startbot <name>` - Start a bot
- `/stopbot <name>` - Stop a bot
- `/restartbot <name>` - Restart a bot
- `/listbots` - List all bots and status

**👥 Userbot Commands**
- `/adduserbot <name>` - Add a userbot via OTP (then follow steps)
- `/removeuserbot <name>` - Remove a userbot
- `/startuserbot <name>` - Start a userbot
- `/stopuserbot <name>` - Stop a userbot
- `/restartuserbot <name>` - Restart a userbot
- `/listuserbots` - List all userbots

**📁 Script Commands**
- `/upload` - Upload a Python/JS script (reply to file)
- `/files` - List your uploaded scripts
- `/startscript <filename>` - Start a script
- `/stopscript <filename>` - Stop a script
- `/deletescript <filename>` - Delete a script
- `/logs <filename>` - View script logs

**Admin Commands** (Owner/Admin)
- `/addadmin <user_id>` - Add admin
- `/removeadmin <user_id>` - Remove admin
- `/listadmins` - List admins
- `/subscription <user_id> <days>` - Give premium
- `/removepremium <user_id>` - Remove premium
- `/broadcast` - Send broadcast (reply to message)
- `/stats` - Bot statistics
- `/lock` - Lock bot
- `/unlock` - Unlock bot

**Other**
- `/ping` - Check latency
- `/animation` - Random aquatic GIF
- `/extra_animation` - Extra GIFs
- `/web` - Web dashboard link
- `/health` - Health check
"""
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# OTP flow commands
@master.on_message(filters.command("host") & filters.private)
async def host_command(client, message):
    user_id = message.from_user.id
    # Check if user already has max userbots
    userbots = await db_get_userbots_for_user(user_id)
    if len(userbots) >= MAX_USERBOTS_PER_USER:
        await message.reply_text(f"⚠️ You already have {MAX_USERBOTS_PER_USER} userbots. Remove one first.")
        return
    await message.reply_text(
        "📱 **Add Userbot via OTP**\n"
        "Send your phone number in format: `+911234567890`\n"
        "Reply with `/host <phone>`"
    )

@master.on_message(filters.command("host") & filters.private)
async def host_phone(client, message):
    # Actually, this is the same command. We need to parse args.
    pass

# We'll use a conversation-like approach via command steps.
# For simplicity, we use separate commands: /host <phone>, /code <code>, /2fa <password>
@master.on_message(filters.command("host") & filters.private)
async def host_phone_command(client, message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/host +911234567890`")
        return
    phone = parts[1].strip()
    if not phone.startswith('+'):
        phone = '+' + phone
    # Check if user already has max userbots
    userbots = await db_get_userbots_for_user(user_id)
    if len(userbots) >= MAX_USERBOTS_PER_USER:
        await message.reply_text(f"⚠️ You already have {MAX_USERBOTS_PER_USER} userbots.")
        return
    success, msg = await start_otp_login(user_id, phone)
    if success:
        await message.reply_text(f"✅ OTP sent to {phone}. Use `/code <code>` to complete.")
    else:
        await message.reply_text(f"❌ Failed: {msg}")

@master.on_message(filters.command("code") & filters.private)
async def code_command(client, message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/code 12345`")
        return
    code = parts[1].strip()
    result = await complete_otp_login(user_id, code)
    if isinstance(result, tuple):
        success, data = result
        if success:
            session_string = data
            # Save userbot with a name
            name = f"ub_{user_id}_{int(time.time())}"
            success2, msg2 = await userbot_manager.add_userbot(name, session_string, user_id)
            if success2:
                await message.reply_text(f"✅ Userbot '{name}' added and ready. Use /startuserbot {name} to start.")
            else:
                await message.reply_text(f"❌ Failed to save userbot: {msg2}")
        else:
            await message.reply_text(f"❌ {data}")
    elif result == "2fa":
        await message.reply_text("🔐 2FA required. Send `/2fa <password>`")
    else:
        await message.reply_text(f"❌ {result}")

@master.on_message(filters.command("2fa") & filters.private)
async def twofa_command(client, message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/2fa your_password`")
        return
    password = parts[1].strip()
    result = await complete_2fa_login(user_id, password)
    if isinstance(result, tuple):
        success, data = result
        if success:
            session_string = data
            name = f"ub_{user_id}_{int(time.time())}"
            success2, msg2 = await userbot_manager.add_userbot(name, session_string, user_id)
            if success2:
                await message.reply_text(f"✅ Userbot '{name}' added and ready.")
            else:
                await message.reply_text(f"❌ Failed to save userbot: {msg2}")
        else:
            await message.reply_text(f"❌ {data}")
    else:
        await message.reply_text(f"❌ {result}")

# Existing bot/userbot commands (from first script)
@master.on_message(filters.command("addbot"))
async def addbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply_text("Usage: `/addbot <name> <token>`")
            return
        name, token = parts[1], parts[2]
        success, msg = await manager.add_bot(name, token)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("removebot"))
async def removebot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/removebot <name>`")
            return
        name = parts[1]
        success, msg = await manager.remove_bot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("startbot"))
async def startbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/startbot <name>`")
            return
        name = parts[1]
        success, msg = await manager.start_bot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("stopbot"))
async def stopbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/stopbot <name>`")
            return
        name = parts[1]
        success, msg = await manager.stop_bot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("restartbot"))
async def restartbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/restartbot <name>`")
            return
        name = parts[1]
        success, msg = await manager.restart_bot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("listbots"))
async def listbots_command(client, message):
    status_text = manager.get_status()
    await message.reply_text(f"**📋 Hosted Bots:**\n{status_text}", parse_mode=ParseMode.MARKDOWN)

# Userbot commands (from first script)
@master.on_message(filters.command("removeuserbot"))
async def removeuserbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/removeuserbot <name>`")
            return
        name = parts[1]
        success, msg = await userbot_manager.remove_userbot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("startuserbot"))
async def startuserbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/startuserbot <name>`")
            return
        name = parts[1]
        success, msg = await userbot_manager.start_userbot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("stopuserbot"))
async def stopuserbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/stopuserbot <name>`")
            return
        name = parts[1]
        success, msg = await userbot_manager.stop_userbot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("restartuserbot"))
async def restartuserbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Usage: `/restartuserbot <name>`")
            return
        name = parts[1]
        success, msg = await userbot_manager.restart_userbot(name)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

@master.on_message(filters.command("listuserbots"))
async def listuserbots_command(client, message):
    user_id = message.from_user.id
    status_text = userbot_manager.get_status(user_id)
    await message.reply_text(f"**👥 Your Userbots:**\n{status_text}", parse_mode=ParseMode.MARKDOWN)

# Script commands
@master.on_message(filters.command("upload") & filters.private)
async def upload_command(client, message):
    await message.reply_text("📤 Reply to this message with your Python/JS file or a ZIP archive.")

@master.on_message(filters.document & filters.private)
async def handle_file_upload(client, message):
    user_id = message.from_user.id
    doc = message.document
    if not doc:
        return
    file_name = doc.file_name
    if not file_name:
        await message.reply_text("⚠️ No file name.")
        return
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in ['.py', '.js', '.zip']:
        await message.reply_text("⚠️ Only .py, .js, .zip allowed.")
        return
    # Check limit
    files = await db_get_user_files(user_id)
    if len(files) >= MAX_SCRIPTS_PER_USER:
        await message.reply_text(f"⚠️ Script limit ({MAX_SCRIPTS_PER_USER}) reached.")
        return
    # Download file
    file_path = await client.download_media(message, file_name=os.path.join(UPLOAD_BOTS_DIR, str(user_id), file_name))
    if not file_path:
        await message.reply_text("❌ Failed to download file.")
        return
    # If zip, extract and find main script
    if ext == '.zip':
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            # Find main script
            py_files = []
            js_files = []
            for root, dirs, files_in in os.walk(temp_dir):
                for f in files_in:
                    if f.endswith('.py'):
                        py_files.append(os.path.join(root, f))
                    elif f.endswith('.js'):
                        js_files.append(os.path.join(root, f))
            if not py_files and not js_files:
                await message.reply_text("❌ No .py or .js found in archive.")
                return
            # Move all files to user folder, keeping structure
            user_folder = script_manager.get_user_folder(user_id)
            for root, dirs, files_in in os.walk(temp_dir):
                for f in files_in:
                    src = os.path.join(root, f)
                    rel_path = os.path.relpath(src, temp_dir)
                    dst = os.path.join(user_folder, rel_path)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(src, dst)
            # Choose main script
            main_script = None
            if py_files:
                # Prefer main.py, bot.py, app.py
                for pref in ['main.py', 'bot.py', 'app.py']:
                    for p in py_files:
                        if os.path.basename(p) == pref:
                            main_script = p
                            break
                    if main_script:
                        break
                if not main_script:
                    main_script = py_files[0]
                file_type = 'py'
            else:
                for pref in ['main.js', 'index.js', 'bot.js', 'app.js']:
                    for p in js_files:
                        if os.path.basename(p) == pref:
                            main_script = p
                            break
                    if main_script:
                        break
                if not main_script:
                    main_script = js_files[0]
                file_type = 'js'
            main_script_name = os.path.basename(main_script)
            # Save to DB
            await db_add_user_file(user_id, main_script_name, file_type)
            await message.reply_text(f"✅ Archive extracted and main script `{main_script_name}` registered.")
            # Optionally install requirements if requirements.txt exists
            req_path = os.path.join(user_folder, 'requirements.txt')
            if os.path.exists(req_path):
                await message.reply_text("🔄 Installing Python dependencies...")
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_path], check=True, capture_output=True)
                    await message.reply_text("✅ Dependencies installed.")
                except subprocess.CalledProcessError as e:
                    await message.reply_text(f"❌ Failed to install dependencies: {e.stderr.decode()}")
            # npm install if package.json
            pkg_path = os.path.join(user_folder, 'package.json')
            if os.path.exists(pkg_path):
                await message.reply_text("🔄 Installing Node dependencies...")
                try:
                    subprocess.run(['npm', 'install'], cwd=user_folder, check=True, capture_output=True)
                    await message.reply_text("✅ Node dependencies installed.")
                except subprocess.CalledProcessError as e:
                    await message.reply_text(f"❌ Failed to install Node deps: {e.stderr.decode()}")
            # Optionally start automatically?
        except Exception as e:
            await message.reply_text(f"❌ Error processing zip: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            os.remove(file_path)
        return
    else:
        # Single file
        file_type = 'py' if ext == '.py' else 'js'
        await db_add_user_file(user_id, file_name, file_type)
        await message.reply_text(f"✅ File `{file_name}` uploaded. Use /files to manage.")

@master.on_message(filters.command("files") & filters.private)
async def list_files_command(client, message):
    user_id = message.from_user.id
    files = await db_get_user_files(user_id)
    if not files:
        await message.reply_text("📁 No scripts uploaded.")
        return
    lines = []
    for fname, ftype in files:
        running = script_manager.is_running(user_id, fname)
        status = "🟢 Running" if running else "🔴 Stopped"
        lines.append(f"`{fname}` ({ftype}) - {status}")
    await message.reply_text("📁 **Your Scripts:**\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

@master.on_message(filters.command("startscript") & filters.private)
async def start_script_command(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/startscript <filename>`")
        return
    file_name = parts[1]
    user_id = message.from_user.id
    files = await db_get_user_files(user_id)
    if not any(f[0] == file_name for f in files):
        await message.reply_text("❌ Script not found.")
        return
    if script_manager.is_running(user_id, file_name):
        await message.reply_text("⚠️ Script already running.")
        return
    success = script_manager.start_script(user_id, file_name, message)
    if success:
        await message.reply_text(f"✅ Script `{file_name}` started.")
    else:
        await message.reply_text(f"❌ Failed to start script. Check logs.")

@master.on_message(filters.command("stopscript") & filters.private)
async def stop_script_command(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/stopscript <filename>`")
        return
    file_name = parts[1]
    user_id = message.from_user.id
    files = await db_get_user_files(user_id)
    if not any(f[0] == file_name for f in files):
        await message.reply_text("❌ Script not found.")
        return
    if not script_manager.is_running(user_id, file_name):
        await message.reply_text("⚠️ Script not running.")
        return
    script_manager.stop_script(user_id, file_name)
    await message.reply_text(f"✅ Script `{file_name}` stopped.")

@master.on_message(filters.command("deletescript") & filters.private)
async def delete_script_command(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/deletescript <filename>`")
        return
    file_name = parts[1]
    user_id = message.from_user.id
    files = await db_get_user_files(user_id)
    if not any(f[0] == file_name for f in files):
        await message.reply_text("❌ Script not found.")
        return
    success, msg = await script_manager.delete_script(user_id, file_name)
    await message.reply_text(msg)

@master.on_message(filters.command("logs") & filters.private)
async def logs_command(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/logs <filename>`")
        return
    file_name = parts[1]
    user_id = message.from_user.id
    files = await db_get_user_files(user_id)
    if not any(f[0] == file_name for f in files):
        await message.reply_text("❌ Script not found.")
        return
    log_content = script_manager.get_log(user_id, file_name)
    if len(log_content) > 4000:
        log_content = log_content[-4000:]
    await message.reply_text(f"📜 **Logs for {file_name}:**\n```\n{log_content}\n```", parse_mode=ParseMode.MARKDOWN)

# Admin commands
@master.on_message(filters.command("addadmin") & filters.private)
async def add_admin_command(client, message):
    if not await is_owner(message.from_user.id):
        await message.reply_text("⚠️ Owner only.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/addadmin <user_id>`")
        return
    try:
        uid = int(parts[1])
        await db_add_admin(uid)
        await message.reply_text(f"✅ User {uid} is now admin.")
    except:
        await message.reply_text("❌ Invalid user ID.")

@master.on_message(filters.command("removeadmin") & filters.private)
async def remove_admin_command(client, message):
    if not await is_owner(message.from_user.id):
        await message.reply_text("⚠️ Owner only.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/removeadmin <user_id>`")
        return
    try:
        uid = int(parts[1])
        if uid == OWNER_ID:
            await message.reply_text("❌ Cannot remove owner.")
            return
        await db_remove_admin(uid)
        await message.reply_text(f"✅ Admin {uid} removed.")
    except:
        await message.reply_text("❌ Invalid user ID.")

@master.on_message(filters.command("listadmins") & filters.private)
async def list_admins_command(client, message):
    if not await is_admin(message.from_user.id):
        await message.reply_text("⚠️ Admin only.")
        return
    admins = await db_get_admins()
    if not admins:
        await message.reply_text("No admins.")
        return
    lines = [f"- `{uid}`" for uid in admins]
    await message.reply_text("👑 **Admins:**\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

@master.on_message(filters.command("subscription") & filters.private)
async def subscription_command(client, message):
    if not await is_admin(message.from_user.id):
        await message.reply_text("⚠️ Admin only.")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text("Usage: `/subscription <user_id> <days>`")
        return
    try:
        uid = int(parts[1])
        days = int(parts[2])
        await db_set_premium(uid, days)
        await message.reply_text(f"✅ User {uid} got premium for {days} days.")
    except:
        await message.reply_text("❌ Invalid input.")

@master.on_message(filters.command("removepremium") & filters.private)
async def remove_premium_command(client, message):
    if not await is_admin(message.from_user.id):
        await message.reply_text("⚠️ Admin only.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("Usage: `/removepremium <user_id>`")
        return
    try:
        uid = int(parts[1])
        await db_remove_premium(uid)
        await message.reply_text(f"✅ Premium removed from {uid}.")
    except:
        await message.reply_text("❌ Invalid user ID.")

@master.on_message(filters.command("broadcast") & filters.private)
async def broadcast_command(client, message):
    if not await is_admin(message.from_user.id):
        await message.reply_text("⚠️ Admin only.")
        return
    if not message.reply_to_message:
        await message.reply_text("Reply to a message to broadcast.")
        return
    # Broadcast to all users
    # We need to get all users from DB
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        users = [row[0] for row in await cursor.fetchall()]
    if not users:
        await message.reply_text("No users to broadcast.")
        return
    # Forward the replied message to all users
    await message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    success_count = 0
    for uid in users:
        try:
            await message.reply_to_message.copy(uid)
            success_count += 1
        except Exception as e:
            # ignore
            pass
        await asyncio.sleep(0.1)  # avoid flood
    await message.reply_text(f"✅ Broadcast sent to {success_count} users.")

@master.on_message(filters.command("stats") & filters.private)
async def stats_command(client, message):
    if not await is_admin(message.from_user.id):
        await message.reply_text("⚠️ Admin only.")
        return
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM user_files")
        total_files = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM userbots")
        total_userbots = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM bots")
        total_bots = (await cursor.fetchone())[0]
    running_userbots = sum(1 for name, info in userbot_manager.userbot_info.items() if info["status"] == "running")
    running_bots = sum(1 for name, info in manager.bot_info.items() if info["status"] == "running")
    running_scripts = len(script_manager.processes)
    await message.reply_text(
        f"📊 **Statistics**\n"
        f"👥 Total users: {total_users}\n"
        f"🤖 Bots: {total_bots} (running: {running_bots})\n"
        f"👤 Userbots: {total_userbots} (running: {running_userbots})\n"
        f"📁 Scripts: {total_files} (running: {running_scripts})"
    )

@master.on_message(filters.command("lock") & filters.private)
async def lock_bot(client, message):
    if not await is_admin(message.from_user.id):
        await message.reply_text("⚠️ Admin only.")
        return
    # Implement lock flag (globally)
    global bot_locked
    bot_locked = True
    await message.reply_text("🔒 Bot locked. Only admins can use commands.")

@master.on_message(filters.command("unlock") & filters.private)
async def unlock_bot(client, message):
    if not await is_admin(message.from_user.id):
        await message.reply_text("⚠️ Admin only.")
        return
    global bot_locked
    bot_locked = False
    await message.reply_text("🔓 Bot unlocked.")

# Other commands
@master.on_message(filters.command("ping"))
async def ping_command(client, message):
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    latency = round((time.time() - start) * 1000, 2)
    await msg.edit_text(f"🏓 **Pong!**\nLatency: `{latency} ms`", parse_mode=ParseMode.MARKDOWN)

@master.on_message(filters.command("animation"))
async def animation_command(client, message):
    await send_animation(message)

@master.on_message(filters.command("extra_animation"))
async def extra_animation_command(client, message):
    await send_extra_animation(message)

@master.on_message(filters.command("web") | filters.command("dashboard"))
async def web_command(client, message):
    await message.reply_text(f"🌐 **Web Dashboard:**\nhttp://localhost:{WEB_PORT}\nOpen in browser to see animated status.", parse_mode=ParseMode.MARKDOWN)

@master.on_message(filters.command("health"))
async def health_command(client, message):
    await manager.health_check()
    await userbot_manager.health_check()
    status_text = manager.get_status() + "\n\n**Userbots:**\n" + userbot_manager.get_status()
    logs = await db_get_recent_logs(5)
    log_text = "\n".join([f"`{log[0]}` - {log[1]}: {log[2]}" for log in logs]) if logs else "No recent logs."
    await message.reply_text(
        f"**❤️ Health Check Completed**\n\n**Current Status:**\n{status_text}\n\n**Recent Logs:**\n{log_text}",
        parse_mode=ParseMode.MARKDOWN
    )

# --------------------------
# CALLBACK QUERY HANDLERS
# --------------------------
@master.on_callback_query()
async def handle_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    await callback_query.answer()

    if data == "main_menu":
        await callback_query.message.edit_text(
            "**🌊 Main Menu**\nChoose an option:",
            reply_markup=await main_menu_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "list_bots":
        status_text = manager.get_status()
        await callback_query.message.edit_text(
            f"**📋 Hosted Bots:**\n{status_text}",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "add_bot":
        await callback_query.message.edit_text(
            "➕ To add a bot, use command:\n`/addbot <name> <token>`",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data in ["start_bot", "stop_bot", "restart_bot", "remove_bot"]:
        action_map = {"start_bot": "start", "stop_bot": "stop", "restart_bot": "restart", "remove_bot": "remove"}
        action = action_map[data]
        kb, error = bot_selection_keyboard(action)
        if error:
            await callback_query.message.edit_text(error, reply_markup=back_to_main())
        else:
            await callback_query.message.edit_text(f"Select a bot to {action}:", reply_markup=kb)
    elif data.startswith("start:") or data.startswith("stop:") or data.startswith("restart:") or data.startswith("remove:"):
        action, bot_name = data.split(":", 1)
        if action == "start":
            success, msg = await manager.start_bot(bot_name)
        elif action == "stop":
            success, msg = await manager.stop_bot(bot_name)
        elif action == "restart":
            success, msg = await manager.restart_bot(bot_name)
        elif action == "remove":
            success, msg = await manager.remove_bot(bot_name)
        await callback_query.message.edit_text(msg, reply_markup=back_to_main(), parse_mode=ParseMode.MARKDOWN)

    # Userbot callbacks
    elif data == "list_userbots":
        status_text = userbot_manager.get_status(user_id)
        await callback_query.message.edit_text(
            f"**👥 Your Userbots:**\n{status_text}",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "add_userbot":
        await callback_query.message.edit_text(
            "➕ To add a userbot, use command:\n`/host +911234567890`\nThen `/code <code>`",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data in ["start_userbot", "stop_userbot", "restart_userbot", "remove_userbot"]:
        action_map = {"start_userbot": "start", "stop_userbot": "stop", "restart_userbot": "restart", "remove_userbot": "remove"}
        action = action_map[data]
        kb, error = userbot_selection_keyboard(action, user_id)
        if error:
            await callback_query.message.edit_text(error, reply_markup=back_to_main())
        else:
            await callback_query.message.edit_text(f"Select a userbot to {action}:", reply_markup=kb)
    elif data.startswith("ub_start:") or data.startswith("ub_stop:") or data.startswith("ub_restart:") or data.startswith("ub_remove:"):
        action, name = data.split(":", 1)[0].replace("ub_", ""), data.split(":", 1)[1]
        if action == "start":
            success, msg = await userbot_manager.start_userbot(name)
        elif action == "stop":
            success, msg = await userbot_manager.stop_userbot(name)
        elif action == "restart":
            success, msg = await userbot_manager.restart_userbot(name)
        elif action == "remove":
            success, msg = await userbot_manager.remove_userbot(name)
        await callback_query.message.edit_text(msg, reply_markup=back_to_main(), parse_mode=ParseMode.MARKDOWN)

    # Script callbacks (simplified: we'll show files and actions)
    elif data == "list_scripts":
        files = await db_get_user_files(user_id)
        if not files:
            await callback_query.message.edit_text("📁 No scripts uploaded.", reply_markup=back_to_main())
            return
        lines = []
        kb = InlineKeyboardMarkup(row_width=1)
        for fname, ftype in files:
            running = script_manager.is_running(user_id, fname)
            status = "🟢 Running" if running else "🔴 Stopped"
            lines.append(f"`{fname}` ({ftype}) - {status}")
            # Add buttons for each file
            kb.add(InlineKeyboardButton(f"{fname} - {status}", callback_data=f"script_{user_id}_{fname}"))
        kb.add(InlineKeyboardButton("⬅️ Back", callback_data="main_menu"))
        await callback_query.message.edit_text("📁 **Your Scripts:**\n" + "\n".join(lines), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    elif data == "upload_script":
        await callback_query.message.edit_text("📤 Reply to this message with your Python/JS file or ZIP.", reply_markup=back_to_main())
    elif data.startswith("script_"):
        # Handle individual script controls
        _, uid_str, fname = data.split("_", 2)
        uid = int(uid_str)
        if uid != user_id and not await is_admin(user_id):
            await callback_query.message.edit_text("⚠️ Not your script.", reply_markup=back_to_main())
            return
        running = script_manager.is_running(uid, fname)
        kb = InlineKeyboardMarkup(row_width=2)
        if running:
            kb.add(InlineKeyboardButton("⏹️ Stop", callback_data=f"stopscript_{uid}_{fname}"))
        else:
            kb.add(InlineKeyboardButton("▶️ Start", callback_data=f"startscript_{uid}_{fname}"))
        kb.add(InlineKeyboardButton("📜 Logs", callback_data=f"logscript_{uid}_{fname}"))
        kb.add(InlineKeyboardButton("🗑️ Delete", callback_data=f"deletescript_{uid}_{fname}"))
        kb.add(InlineKeyboardButton("⬅️ Back", callback_data="list_scripts"))
        await callback_query.message.edit_text(f"Controls for `{fname}`", reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("startscript_"):
        _, uid_str, fname = data.split("_", 2)
        uid = int(uid_str)
        if uid != user_id and not await is_admin(user_id):
            await callback_query.message.edit_text("⚠️ Not your script.", reply_markup=back_to_main())
            return
        success = script_manager.start_script(uid, fname, callback_query.message)
        msg = "✅ Started." if success else "❌ Failed."
        await callback_query.message.edit_text(msg, reply_markup=back_to_main())
    elif data.startswith("stopscript_"):
        _, uid_str, fname = data.split("_", 2)
        uid = int(uid_str)
        if uid != user_id and not await is_admin(user_id):
            await callback_query.message.edit_text("⚠️ Not your script.", reply_markup=back_to_main())
            return
        script_manager.stop_script(uid, fname)
        await callback_query.message.edit_text("✅ Stopped.", reply_markup=back_to_main())
    elif data.startswith("logscript_"):
        _, uid_str, fname = data.split("_", 2)
        uid = int(uid_str)
        if uid != user_id and not await is_admin(user_id):
            await callback_query.message.edit_text("⚠️ Not your script.", reply_markup=back_to_main())
            return
        log_content = script_manager.get_log(uid, fname)
        if len(log_content) > 4000:
            log_content = log_content[-4000:]
        await callback_query.message.edit_text(f"📜 **Logs:**\n```\n{log_content}\n```", parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_main())
    elif data.startswith("deletescript_"):
        _, uid_str, fname = data.split("_", 2)
        uid = int(uid_str)
        if uid != user_id and not await is_admin(user_id):
            await callback_query.message.edit_text("⚠️ Not your script.", reply_markup=back_to_main())
            return
        success, msg = await script_manager.delete_script(uid, fname)
        await callback_query.message.edit_text(msg, reply_markup=back_to_main())

    # Other callbacks
    elif data == "ping":
        start = time.time()
        await callback_query.message.edit_text("🏓 Pinging...")
        latency = round((time.time() - start) * 1000, 2)
        await callback_query.message.edit_text(f"🏓 **Pong!**\nLatency: `{latency} ms`", reply_markup=back_to_main(), parse_mode=ParseMode.MARKDOWN)
    elif data == "animation":
        gif_url = random.choice(ANIMATIONS)
        await callback_query.message.reply_animation(animation=gif_url, caption="🌊 **Aquatic Power!**", parse_mode=ParseMode.MARKDOWN)
        await callback_query.message.edit_text("🎬 **Animation sent!**", reply_markup=back_to_main())
    elif data == "extra_animation":
        gif_url = random.choice(EXTRA_ANIMATIONS)
        await callback_query.message.reply_animation(animation=gif_url, caption="🐠 **Extra Aquatic Animation!**", parse_mode=ParseMode.MARKDOWN)
        await callback_query.message.edit_text("🎞️ **Extra animation sent!**", reply_markup=back_to_main())
    elif data == "health":
        await manager.health_check()
        await userbot_manager.health_check()
        status_text = manager.get_status() + "\n\n**Userbots:**\n" + userbot_manager.get_status()
        logs = await db_get_recent_logs(5)
        log_text = "\n".join([f"`{log[0]}` - {log[1]}: {log[2]}" for log in logs]) if logs else "No recent logs."
        await callback_query.message.edit_text(
            f"**❤️ Health Check Completed**\n\n**Current Status:**\n{status_text}\n\n**Recent Logs:**\n{log_text}",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "web":
        await callback_query.message.edit_text(
            f"🌐 **Web Dashboard:**\nhttp://localhost:{WEB_PORT}\n\nYou can control bots, userbots, and scripts from the browser!",
            reply_markup=back_to_main()
        )
    elif data == "admin_panel":
        if not (await is_admin(user_id) or await is_owner(user_id)):
            await callback_query.message.edit_text("⚠️ Admin only.", reply_markup=back_to_main())
            return
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("📊 Statistics", callback_data="stats"))
        kb.add(InlineKeyboardButton("👥 Admins", callback_data="list_admins"))
        kb.add(InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"))
        kb.add(InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin"))
        kb.add(InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"))
        kb.add(InlineKeyboardButton("🔒 Lock/Unlock", callback_data="lock_toggle"))
        kb.add(InlineKeyboardButton("⬅️ Back", callback_data="main_menu"))
        await callback_query.message.edit_text("👑 **Admin Panel**", reply_markup=kb)
    elif data == "stats":
        # Trigger stats command
        await stats_command(client, callback_query.message)
    elif data == "list_admins":
        admins = await db_get_admins()
        lines = [f"- `{uid}`" for uid in admins]
        await callback_query.message.edit_text("👑 **Admins:**\n" + "\n".join(lines), reply_markup=back_to_main(), parse_mode=ParseMode.MARKDOWN)
    elif data == "add_admin":
        await callback_query.message.edit_text("➕ Send `/addadmin <user_id>`", reply_markup=back_to_main())
    elif data == "remove_admin":
        await callback_query.message.edit_text("➖ Send `/removeadmin <user_id>`", reply_markup=back_to_main())
    elif data == "broadcast":
        await callback_query.message.edit_text("📢 Reply to a message and use /broadcast", reply_markup=back_to_main())
    elif data == "lock_toggle":
        global bot_locked
        bot_locked = not bot_locked
        status = "locked" if bot_locked else "unlocked"
        await callback_query.message.edit_text(f"🔒 Bot is now {status}.", reply_markup=back_to_main())

# --------------------------
# BACKGROUND HEALTH CHECK LOOP
# --------------------------
async def health_check_loop():
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        try:
            await manager.health_check()
            await userbot_manager.health_check()
        except Exception as e:
            print(f"Health check error: {e}")

# --------------------------
# MAIN ENTRY POINT with robust error handling
# --------------------------
bot_locked = False

async def main():
    print("🌊 Starting Super Duper Bot Hoster (Ultimate Edition)...")
    print(f"Using token: {MASTER_BOT_TOKEN[:10]}... (masked)")

    # 1. Database init
    try:
        await init_db()
        print("✅ Database initialized.")
    except Exception as e:
        print("❌ Database init failed:")
        traceback.print_exc()
        sys.exit(1)

    # 2. Load bots
    try:
        await manager.load_from_db()
        print(f"✅ Loaded {len(manager.bot_info)} bots from DB.")
    except Exception as e:
        print("❌ Failed to load bots:")
        traceback.print_exc()
        sys.exit(1)

    # 3. Load userbots
    try:
        await userbot_manager.load_from_db()
        print(f"✅ Loaded {len(userbot_manager.userbot_info)} userbots from DB.")
    except Exception as e:
        print("❌ Failed to load userbots:")
        traceback.print_exc()
        sys.exit(1)

    # 4. Start master client
    try:
        await master.start()
        print("✅ Master client started.")
    except Exception as e:
        print("❌ Master client start failed:")
        traceback.print_exc()
        sys.exit(1)

    # 5. Start background tasks
    asyncio.create_task(health_check_loop())
    print("✅ Health check loop started.")

    # 6. Start web server (non‑critical – log error but continue)
    try:
        await start_web_server()
        print(f"✅ Web server running on port {WEB_PORT}.")
    except Exception as e:
        print("❌ Web server failed to start (but bot will keep running):")
        traceback.print_exc()

    print("✅ Master control is running. Press Ctrl+C to stop.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print("Unhandled exception in main loop:")
        traceback.print_exc()
