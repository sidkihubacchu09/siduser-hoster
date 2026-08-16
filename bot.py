#!/usr/bin/env python3
"""
SUPER DUPER TELEGRAM BOT HOSTER - ULTIMATE AQUATIC EDITION
- Runs a Master Control Bot (userbot or bot)
- Manages multiple hosted bots (start/stop/restart)
- Inline buttons, animations, aquatic theme
- Async performance with Pyrogram
- Real-time database storage (aiosqlite)
- Health check & auto-restart system
- Web Dashboard with JS Animations (aiohttp)
- ADDED: Full web control, more animations
- ADDED: Userbot hosting (separate manager, DB, commands)
"""

import asyncio
import random
import sys
import time
from datetime import datetime
from typing import Dict, Optional

# Pyrogram imports
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ParseMode

# Database import
import aiosqlite

# Web server import
from aiohttp import web

# --------------------------
# CONFIGURATION
# --------------------------
MASTER_API_ID = 33491590         # Your API ID
MASTER_API_HASH = "35eb3cd440c7ad282cfdc2ce557e37f6"
MASTER_BOT_TOKEN = "8602762499:AAFO1ZuzFY6VgKXambFPdpWcvcfUthT6ATw"           # If using bot as master, set token here
MASTER_SESSION_STRING = "1"      # If using userbot as master, set session string

HOSTED_BOTS = [
    # {"name": "Bot1", "token": "123456:ABC..."},
]

# --------------------------
# ANIMATIONS (EXPANDED)
# --------------------------
ANIMATIONS = [
    "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif",
    "https://media.giphy.com/media/l0HlNaQ6gWfllcjDO/giphy.gif",
    "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
    "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif",
    "https://media.giphy.com/media/3o7aD2saalBwwftFIY/giphy.gif",
    "https://media.giphy.com/media/3o7aCTPPm4OHfRLSH6/giphy.gif",  # Sea turtle
    "https://media.giphy.com/media/l4FGuhL4U2WyjdkaY/giphy.gif",  # Octopus
    "https://media.giphy.com/media/3o7aD5jJzJzJZq5wM0/giphy.gif",  # Coral reef
    "https://media.giphy.com/media/3o6Zt8HWq4g9fW8t4k/giphy.gif",  # Jellyfish
    "https://media.giphy.com/media/xT0xeMA62E1XIlupj2/giphy.gif",  # Shark
]

EXTRA_ANIMATIONS = [
    "https://media.giphy.com/media/3o7aCTfyhYawdOXcFW/giphy.gif",  # Fish school
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",  # Sea horse
    "https://media.giphy.com/media/3o7aD2sG6Wf2rB3K3C/giphy.gif",  # Manta ray
    "https://media.giphy.com/media/3o7aCT8bDhf2iW0m2A/giphy.gif",  # Stingray
    "https://media.giphy.com/media/3o7aTzG6i5tXlV6C7K/giphy.gif",  # Dolphin
]

DB_PATH = "bot_hoster.db"       # SQLite database file
HEALTH_CHECK_INTERVAL = 30      # seconds
WEB_PORT = 8080                 # Port for web dashboard

# --------------------------
# DATABASE SETUP (unchanged for bots)
# --------------------------
async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Original bots table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                name TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                status TEXT DEFAULT 'stopped'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crash_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT,
                timestamp TEXT,
                event TEXT
            )
        """)
        # ADDED: userbots table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS userbots (
                name TEXT PRIMARY KEY,
                session_string TEXT NOT NULL,
                status TEXT DEFAULT 'stopped'
            )
        """)
        await db.commit()

# --------------------------
# DATABASE FUNCTIONS FOR BOTS (unchanged)
# --------------------------
async def db_add_bot(name, token):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO bots (name, token, status) VALUES (?, ?, ?)",
            (name, token, "stopped")
        )
        await db.commit()

async def db_remove_bot(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bots WHERE name = ?", (name,))
        await db.commit()

async def db_update_bot_status(name, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bots SET status = ? WHERE name = ?",
            (status, name)
        )
        await db.commit()

async def db_get_all_bots():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, token, status FROM bots")
        rows = await cursor.fetchall()
        return rows

async def db_log_crash(bot_name, event):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO crash_log (bot_name, timestamp, event) VALUES (?, ?, ?)",
            (bot_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), event)
        )
        await db.commit()

async def db_get_recent_logs(limit=5):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT bot_name, timestamp, event FROM crash_log ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()

# ADDED: Database functions for userbots
async def db_add_userbot(name, session_string):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO userbots (name, session_string, status) VALUES (?, ?, ?)",
            (name, session_string, "stopped")
        )
        await db.commit()

async def db_remove_userbot(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM userbots WHERE name = ?", (name,))
        await db.commit()

async def db_update_userbot_status(name, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE userbots SET status = ? WHERE name = ?",
            (status, name)
        )
        await db.commit()

async def db_get_all_userbots():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, session_string, status FROM userbots")
        rows = await cursor.fetchall()
        return rows

# --------------------------
# BOT MANAGER CLASS (Enhanced) - unchanged
# --------------------------
class BotManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self.bot_info: Dict[str, dict] = {}

    async def load_from_db(self):
        rows = await db_get_all_bots()
        for name, token, status in rows:
            client = Client(
                name=f"hosted_{name}",
                api_id=MASTER_API_ID,
                api_hash=MASTER_API_HASH,
                bot_token=token,
                in_memory=True
            )
            self.clients[name] = client
            self.bot_info[name] = {
                "token": token,
                "status": status,
                "client": client
            }
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
        client = Client(
            name=f"hosted_{name}",
            api_id=MASTER_API_ID,
            api_hash=MASTER_API_HASH,
            bot_token=token,
            in_memory=True
        )
        self.clients[name] = client
        self.bot_info[name] = {
            "token": token,
            "status": "stopped",
            "client": client
        }
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
                    print(f"⚠️ Health check: {name} is down. Restarting...")
                    await db_log_crash(name, "Detected down by health check")
                    success, msg = await self.restart_bot(name)
                    if success:
                        await db_log_crash(name, f"Auto-restarted successfully")
                    else:
                        await db_log_crash(name, f"Auto-restart failed: {msg}")

# Initialize bot manager
manager = BotManager()

# ADDED: Userbot Manager Class
class UserbotManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self.userbot_info: Dict[str, dict] = {}

    async def load_from_db(self):
        rows = await db_get_all_userbots()
        for name, session_string, status in rows:
            client = Client(
                name=f"hosted_userbot_{name}",
                api_id=MASTER_API_ID,
                api_hash=MASTER_API_HASH,
                session_string=session_string,
                in_memory=True
            )
            self.clients[name] = client
            self.userbot_info[name] = {
                "session_string": session_string,
                "status": status,
                "client": client
            }
            if status == "running":
                try:
                    await client.start()
                    self.userbot_info[name]["status"] = "running"
                except Exception as e:
                    await db_log_crash(f"userbot:{name}", f"Failed to auto-start on load: {e}")
                    self.userbot_info[name]["status"] = "stopped"
                    await db_update_userbot_status(name, "stopped")

    async def add_userbot(self, name: str, session_string: str):
        if name in self.userbot_info:
            return False, "Userbot name already exists."
        client = Client(
            name=f"hosted_userbot_{name}",
            api_id=MASTER_API_ID,
            api_hash=MASTER_API_HASH,
            session_string=session_string,
            in_memory=True
        )
        self.clients[name] = client
        self.userbot_info[name] = {
            "session_string": session_string,
            "status": "stopped",
            "client": client
        }
        await db_add_userbot(name, session_string)
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

    def get_status(self) -> str:
        if not self.userbot_info:
            return "No userbots hosted yet."
        lines = []
        for name, info in self.userbot_info.items():
            status_emoji = "🟢" if info["status"] == "running" else "🔴"
            lines.append(f"{status_emoji} **{name}** - {info['status']}")
        return "\n".join(lines)

    def list_userbot_names(self):
        return list(self.userbot_info.keys())

    async def health_check(self):
        for name, info in self.userbot_info.items():
            if info["status"] == "running":
                client = self.clients.get(name)
                if client and not client.is_initialized:
                    print(f"⚠️ Health check: userbot {name} is down. Restarting...")
                    await db_log_crash(f"userbot:{name}", "Detected down by health check")
                    success, msg = await self.restart_userbot(name)
                    if success:
                        await db_log_crash(f"userbot:{name}", "Auto-restarted successfully")
                    else:
                        await db_log_crash(f"userbot:{name}", f"Auto-restart failed: {msg}")

# Initialize userbot manager
userbot_manager = UserbotManager()

# --------------------------
# MASTER CLIENT SETUP (unchanged)
# --------------------------
if MASTER_BOT_TOKEN:
    master = Client(
        "master_bot",
        api_id=MASTER_API_ID,
        api_hash=MASTER_API_HASH,
        bot_token=MASTER_BOT_TOKEN
    )
elif MASTER_SESSION_STRING:
    master = Client(
        "master_userbot",
        api_id=MASTER_API_ID,
        api_hash=MASTER_API_HASH,
        session_string=MASTER_SESSION_STRING
    )
else:
    print("Please set MASTER_BOT_TOKEN or MASTER_SESSION_STRING.")
    sys.exit(1)

# --------------------------
# HELPER FUNCTIONS (unchanged)
# --------------------------
async def send_animation(message: Message):
    gif_url = random.choice(ANIMATIONS)
    await message.reply_animation(
        animation=gif_url,
        caption="🌊 **Aquatic Power!**",
        parse_mode=ParseMode.MARKDOWN
    )

async def send_extra_animation(message: Message):
    gif_url = random.choice(EXTRA_ANIMATIONS)
    await message.reply_animation(
        animation=gif_url,
        caption="🐠 **Extra Aquatic Animation!**",
        parse_mode=ParseMode.MARKDOWN
    )

# --------------------------
# INLINE KEYBOARDS (updated)
# --------------------------
def main_menu_keyboard():
    buttons = [
        # Existing bot buttons
        [InlineKeyboardButton("📋 List Bots", callback_data="list_bots"),
         InlineKeyboardButton("➕ Add Bot", callback_data="add_bot")],
        [InlineKeyboardButton("▶️ Start Bot", callback_data="start_bot"),
         InlineKeyboardButton("⏹️ Stop Bot", callback_data="stop_bot")],
        [InlineKeyboardButton("🔄 Restart Bot", callback_data="restart_bot"),
         InlineKeyboardButton("🗑️ Remove Bot", callback_data="remove_bot")],
        # ADDED: Userbot buttons
        [InlineKeyboardButton("👥 List Userbots", callback_data="list_userbots"),
         InlineKeyboardButton("➕ Add Userbot", callback_data="add_userbot")],
        [InlineKeyboardButton("▶️ Start Userbot", callback_data="start_userbot"),
         InlineKeyboardButton("⏹️ Stop Userbot", callback_data="stop_userbot")],
        [InlineKeyboardButton("🔄 Restart Userbot", callback_data="restart_userbot"),
         InlineKeyboardButton("🗑️ Remove Userbot", callback_data="remove_userbot")],
        # Existing extra buttons
        [InlineKeyboardButton("🏓 Ping", callback_data="ping"),
         InlineKeyboardButton("🎬 Animation", callback_data="animation")],
        [InlineKeyboardButton("🎞️ More Animations", callback_data="extra_animation"),
         InlineKeyboardButton("❤️ Health", callback_data="health")],
        [InlineKeyboardButton("🌐 Web Dashboard", callback_data="web")],
    ]
    return InlineKeyboardMarkup(buttons)

def back_to_main():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]]
    )

def bot_selection_keyboard(action: str):
    bot_names = manager.list_bot_names()
    if not bot_names:
        return None, "No bots available. Add a bot first."
    buttons = []
    for name in bot_names:
        buttons.append([InlineKeyboardButton(name, callback_data=f"{action}:{name}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons), None

# ADDED: Userbot selection keyboard
def userbot_selection_keyboard(action: str):
    names = userbot_manager.list_userbot_names()
    if not names:
        return None, "No userbots available. Add a userbot first."
    buttons = []
    for name in names:
        buttons.append([InlineKeyboardButton(name, callback_data=f"ub_{action}:{name}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons), None

# --------------------------
# WEB DASHBOARD (aiohttp) - ENHANCED WITH USERBOTS
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
            max-width: 900px;
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
                // Render bots
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
                // Render userbots
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
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }

        async function controlBot(action, name) {
            try {
                const response = await fetch(`/api/${action}/${name}`, { method: 'POST' });
                const result = await response.json();
                alert(result.message || result.error);
                fetchStatus();
            } catch (error) {
                console.error('Error controlling bot:', error);
                alert('Failed to perform action');
            }
        }

        // ADDED: controlUserbot function
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
    bots = []
    for name, info in manager.bot_info.items():
        bots.append({"name": name, "status": info["status"]})
    userbots = []
    for name, info in userbot_manager.userbot_info.items():
        userbots.append({"name": name, "status": info["status"]})
    return web.json_response({"bots": bots, "userbots": userbots})

# Existing bot API handlers
async def handle_api_start(request):
    bot_name = request.match_info['name']
    success, msg = await manager.start_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_stop(request):
    bot_name = request.match_info['name']
    success, msg = await manager.stop_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_restart(request):
    bot_name = request.match_info['name']
    success, msg = await manager.restart_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

async def handle_api_remove(request):
    bot_name = request.match_info['name']
    success, msg = await manager.remove_bot(bot_name)
    return web.json_response({"success": success, "message": msg})

# ADDED: Userbot API handlers
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

def create_web_app():
    app = web.Application()
    app.router.add_get('/', handle_web_index)
    app.router.add_get('/api/status', handle_api_status)
    # Bot routes
    app.router.add_post('/api/start/{name}', handle_api_start)
    app.router.add_post('/api/stop/{name}', handle_api_stop)
    app.router.add_post('/api/restart/{name}', handle_api_restart)
    app.router.add_post('/api/remove/{name}', handle_api_remove)
    # ADDED: Userbot routes
    app.router.add_post('/api/userbot/start/{name}', handle_api_userbot_start)
    app.router.add_post('/api/userbot/stop/{name}', handle_api_userbot_stop)
    app.router.add_post('/api/userbot/restart/{name}', handle_api_userbot_restart)
    app.router.add_post('/api/userbot/remove/{name}', handle_api_userbot_remove)
    return app

async def start_web_server():
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)
    await site.start()
    print(f"🌐 Web dashboard running on http://0.0.0.0:{WEB_PORT}")

# --------------------------
# MASTER COMMAND HANDLERS (existing bot commands + new userbot commands)
# --------------------------
@master.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await send_animation(message)
    await message.reply_text(
        "**🌊 Welcome to the Super Duper Bot Hoster!**\n"
        "Manage your hosted bots and userbots with the menu below:",
        reply_markup=main_menu_keyboard(),
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
- `/health` - View health status & recent crash logs
- `/ping` - Check master bot latency
- `/animation` - Send a random aquatic GIF
- `/extra_animation` - Send from extended animation set
- `/web` or `/dashboard` - Get web dashboard link

**👥 Userbot Commands (ADDED)**
- `/adduserbot <name> <session_string>` - Add a userbot
- `/removeuserbot <name>` - Remove a userbot
- `/startuserbot <name>` - Start a userbot
- `/stopuserbot <name>` - Stop a userbot
- `/restartuserbot <name>` - Restart a userbot
- `/listuserbots` - List all userbots and status
"""
    await message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

@master.on_message(filters.command("extra_animation"))
async def extra_animation_command(client, message):
    await send_extra_animation(message)

@master.on_message(filters.command(["web", "dashboard"]))
async def web_command(client, message):
    await message.reply_text(
        f"🌐 **Web Dashboard:**\nhttp://localhost:{WEB_PORT}\n"
        "Open in browser to see animated status and control both bots and userbots.",
        parse_mode=ParseMode.MARKDOWN
    )

@master.on_message(filters.command("health"))
async def health_command(client, message):
    await manager.health_check()
    await userbot_manager.health_check()  # ADDED: health check for userbots
    status_text = manager.get_status() + "\n\n**Userbots:**\n" + userbot_manager.get_status()
    logs = await db_get_recent_logs(5)
    log_text = "\n".join([f"`{log[0]}` - {log[1]}: {log[2]}" for log in logs]) if logs else "No recent logs."
    await message.reply_text(
        f"**❤️ Health Check Completed**\n\n**Current Status:**\n{status_text}\n\n**Recent Logs:**\n{log_text}",
        parse_mode=ParseMode.MARKDOWN
    )

# Existing bot commands (unchanged)
@master.on_message(filters.command("addbot"))
async def addbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply_text("Usage: `/addbot <name> <token>`")
            return
        name = parts[1]
        token = parts[2]
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
    await message.reply_text(f"**📋 Hosted Bots:**\n{status_text}",
                             parse_mode=ParseMode.MARKDOWN)

# ADDED: Userbot commands
@master.on_message(filters.command("adduserbot"))
async def adduserbot_command(client, message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply_text("Usage: `/adduserbot <name> <session_string>`")
            return
        name = parts[1]
        session_string = parts[2]
        success, msg = await userbot_manager.add_userbot(name, session_string)
        await message.reply_text(msg)
    except Exception as e:
        await message.reply_text(f"Error: {e}")

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
    status_text = userbot_manager.get_status()
    await message.reply_text(f"**👥 Hosted Userbots:**\n{status_text}",
                             parse_mode=ParseMode.MARKDOWN)

@master.on_message(filters.command("ping"))
async def ping_command(client, message):
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    latency = round((time.time() - start) * 1000, 2)
    await msg.edit_text(f"🏓 **Pong!**\nLatency: `{latency} ms`",
                        parse_mode=ParseMode.MARKDOWN)

@master.on_message(filters.command("animation"))
async def animation_command(client, message):
    await send_animation(message)

# --------------------------
# CALLBACK QUERY HANDLERS (enhanced with userbot callbacks)
# --------------------------
@master.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data
    await callback_query.answer()

    # Existing handlers...
    if data == "main_menu":
        await callback_query.message.edit_text(
            "**🌊 Main Menu**\nChoose an option:",
            reply_markup=main_menu_keyboard(),
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
        action_map = {
            "start_bot": "start",
            "stop_bot": "stop",
            "restart_bot": "restart",
            "remove_bot": "remove"
        }
        action = action_map[data]
        kb, error = bot_selection_keyboard(action)
        if error:
            await callback_query.message.edit_text(error, reply_markup=back_to_main())
        else:
            await callback_query.message.edit_text(
                f"Select a bot to {action}:",
                reply_markup=kb
            )
    elif data.startswith("start:") or data.startswith("stop:") or \
         data.startswith("restart:") or data.startswith("remove:"):
        action, bot_name = data.split(":", 1)
        if action == "start":
            success, msg = await manager.start_bot(bot_name)
        elif action == "stop":
            success, msg = await manager.stop_bot(bot_name)
        elif action == "restart":
            success, msg = await manager.restart_bot(bot_name)
        elif action == "remove":
            success, msg = await manager.remove_bot(bot_name)
        await callback_query.message.edit_text(
            msg,
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "ping":
        start = time.time()
        await callback_query.message.edit_text("🏓 Pinging...")
        latency = round((time.time() - start) * 1000, 2)
        await callback_query.message.edit_text(
            f"🏓 **Pong!**\nLatency: `{latency} ms`",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "animation":
        gif_url = random.choice(ANIMATIONS)
        await callback_query.message.reply_animation(
            animation=gif_url,
            caption="🌊 **Aquatic Power!**",
            parse_mode=ParseMode.MARKDOWN
        )
        await callback_query.message.edit_text(
            "🎬 **Animation sent!**",
            reply_markup=back_to_main()
        )
    elif data == "extra_animation":
        gif_url = random.choice(EXTRA_ANIMATIONS)
        await callback_query.message.reply_animation(
            animation=gif_url,
            caption="🐠 **Extra Aquatic Animation!**",
            parse_mode=ParseMode.MARKDOWN
        )
        await callback_query.message.edit_text(
            "🎞️ **Extra animation sent!**",
            reply_markup=back_to_main()
        )
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
            f"🌐 **Web Dashboard:**\nhttp://localhost:{WEB_PORT}\n\nYou can control bots and userbots from the browser now!",
            reply_markup=back_to_main()
        )
    elif data == "help":
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
- `/health` - View health status & recent crash logs
- `/ping` - Check master bot latency
- `/animation` - Send a random aquatic GIF
- `/extra_animation` - Send from extended animation set
- `/web` or `/dashboard` - Get web dashboard link

**👥 Userbot Commands (ADDED)**
- `/adduserbot <name> <session_string>` - Add a userbot
- `/removeuserbot <name>` - Remove a userbot
- `/startuserbot <name>` - Start a userbot
- `/stopuserbot <name>` - Stop a userbot
- `/restartuserbot <name>` - Restart a userbot
- `/listuserbots` - List all userbots and status
"""
        await callback_query.message.edit_text(
            help_text,
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    # ADDED: Userbot callback handlers
    elif data == "list_userbots":
        status_text = userbot_manager.get_status()
        await callback_query.message.edit_text(
            f"**👥 Hosted Userbots:**\n{status_text}",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "add_userbot":
        await callback_query.message.edit_text(
            "➕ To add a userbot, use command:\n`/adduserbot <name> <session_string>`",
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data in ["start_userbot", "stop_userbot", "restart_userbot", "remove_userbot"]:
        action_map = {
            "start_userbot": "start",
            "stop_userbot": "stop",
            "restart_userbot": "restart",
            "remove_userbot": "remove"
        }
        action = action_map[data]
        kb, error = userbot_selection_keyboard(action)
        if error:
            await callback_query.message.edit_text(error, reply_markup=back_to_main())
        else:
            await callback_query.message.edit_text(
                f"Select a userbot to {action}:",
                reply_markup=kb
            )
    elif data.startswith("ub_start:") or data.startswith("ub_stop:") or \
         data.startswith("ub_restart:") or data.startswith("ub_remove:"):
        action, name = data.split(":", 1)[0].replace("ub_", ""), data.split(":", 1)[1]
        if action == "start":
            success, msg = await userbot_manager.start_userbot(name)
        elif action == "stop":
            success, msg = await userbot_manager.stop_userbot(name)
        elif action == "restart":
            success, msg = await userbot_manager.restart_userbot(name)
        elif action == "remove":
            success, msg = await userbot_manager.remove_userbot(name)
        await callback_query.message.edit_text(
            msg,
            reply_markup=back_to_main(),
            parse_mode=ParseMode.MARKDOWN
        )

# --------------------------
# BACKGROUND HEALTH CHECK LOOP
# --------------------------
async def health_check_loop():
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        try:
            await manager.health_check()
            await userbot_manager.health_check()  # ADDED
        except Exception as e:
            print(f"Health check error: {e}")

# --------------------------
# MAIN ENTRY POINT
# --------------------------
async def main():
    print("🌊 Starting Super Duper Bot Hoster...")
    await init_db()
    await manager.load_from_db()
    await userbot_manager.load_from_db()  # ADDED: load userbots
    await master.start()
    asyncio.create_task(health_check_loop())
    asyncio.create_task(start_web_server())
    print("✅ Master control is running. Press Ctrl+C to stop.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
