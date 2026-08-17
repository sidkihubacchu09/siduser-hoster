import telebot
import requests
import sqlite3
import time
import json
from telebot import types

# ============================================
# CONFIG
# ============================================
BOT_TOKEN = "8732063177:AAFjqxNLHh0moa_8daUbThK3zVoi_B6wXSU"

# SastaOTP API key
SASTA_API_KEY = "stp_0ac4e9ace00367b27b27afe499242f59e73c405035866819"
SASTA_BASE_URL = "https://sastasms.pro/stubs/handler_api.php"

ADMIN_ID = 2119464081
ADMIN_CHAT_ID = -1003941256566
UPI_ID = "7722026588@ptaxis"

# ============================================
# BOT INIT
# ============================================
bot = telebot.TeleBot(BOT_TOKEN)

# ============================================
# DATABASE
# ============================================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# Users table
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)
''')

# Payments table
cursor.execute('''
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    status TEXT,
    screenshot TEXT
)
''')

# Activations table (stores purchased numbers)
cursor.execute('''
CREATE TABLE IF NOT EXISTS activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    activation_id TEXT,
    order_id INTEGER,
    number TEXT,
    service TEXT,
    country TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()

# ============================================
# HELPER: SastaOTP API CALL (FIXED)
# ============================================
def sasta_api_call(params):
    """Make a GET request to SastaOTP API with api_key automatically added."""
    params["api_key"] = SASTA_API_KEY
    try:
        resp = requests.get(SASTA_BASE_URL, params=params, timeout=15)
        if resp.status_code == 200:
            # Try JSON first
            try:
                return resp.json()
            except:
                # Handle plain text responses like "ACCESS_BALANCE:125.50"
                text = resp.text.strip()
                if ':' in text:
                    parts = text.split(':', 1)
                    return {"status": "OK", parts[0]: parts[1]}
                else:
                    return {"status": "ERROR", "message": text}
        else:
            return {"status": "ERROR", "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

# ============================================
# START
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0))
        conn.commit()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 Balance", "👛 Wallet")
    markup.row("📲 Buy Number", "📩 Check SMS")
    markup.row("➕ Add Funds")

    # Send animated welcome
    try:
        bot.send_animation(
            message.chat.id,
            animation="https://media.giphy.com/media/RDZo7znAdn2u7sAcWH/giphy.gif",
            caption="🔥 <b>Welcome to SastaOTP Bot</b>\n"
                    "✦ ── ── ── ── ── ── ✦\n"
                    "⚡ Fast & cheap virtual numbers\n"
                    "💎 24/7 OTP delivery",
            parse_mode="HTML"
        )
    except:
        pass

    bot.send_message(
        message.chat.id,
        "◈ <b>ADVANCED OTP BOT</b> ◈\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        "✨ Choose an option from the menu below.",
        reply_markup=markup,
        parse_mode="HTML"
    )

# ============================================
# FIND IDS
# ============================================
@bot.message_handler(commands=['id'])
def get_ids(message):
    text = (
        f"👤 <b>User ID:</b> <code>{message.from_user.id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{message.chat.id}</code>"
    )
    bot.reply_to(message, text, parse_mode="HTML")

# ============================================
# WALLET (Local balance)
# ============================================
@bot.message_handler(func=lambda m: m.text == "👛 Wallet")
def wallet(message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0
    bot.reply_to(
        message,
        f"<b>💰 Wallet Balance</b>\n"
        f"✦ ── ── ── ── ✦\n"
        f"<code>{balance:.2f}</code> INR",
        parse_mode="HTML"
    )

# ============================================
# API BALANCE (SastaOTP) - FIXED
# ============================================
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def api_balance(message):
    data = sasta_api_call({"action": "getBalance"})
    if data.get("status") == "OK":
        # Balance might be in 'balance' key or the plain text part
        bal = data.get("balance")
        if bal is None:
            # If it came from plain text, it might be under the action name
            bal = data.get("ACCESS_BALANCE")
        if bal is None:
            bal = 0.0
        currency = data.get("currency", "INR")
        bot.reply_to(
            message,
            f"<b>🌐 SastaOTP Balance</b>\n"
            f"✦ ── ── ── ── ✦\n"
            f"<code>{bal}</code> {currency}",
            parse_mode="HTML"
        )
    else:
        bot.reply_to(message, f"❌ <b>Error:</b> {data.get('message', 'Unknown')}", parse_mode="HTML")

# ============================================
# ADD FUNDS (UPI)
# ============================================
@bot.message_handler(func=lambda m: m.text == "➕ Add Funds")
def add_funds(message):
    text = (
        f"💳 <b>Send Payment via UPI</b>\n"
        f"✦ ── ── ── ── ✦\n"
        f"🏦 <b>UPI ID:</b> <code>{UPI_ID}</code>\n\n"
        f"📸 After payment, send a <b>screenshot</b> of the transaction.\n"
        f"✅ Admin will approve and add funds to your wallet."
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# ============================================
# PAYMENT SCREENSHOT HANDLER - FIXED
# ============================================
@bot.message_handler(content_types=['photo'])
def payment_photo(message):
    user_id = message.from_user.id
    file_id = message.photo[-1].file_id

    cursor.execute(
        "INSERT INTO payments (user_id, amount, status, screenshot) VALUES (?, ?, ?, ?)",
        (user_id, 100, "pending", file_id)
    )
    conn.commit()
    payment_id = cursor.lastrowid

    markup = types.InlineKeyboardMarkup()
    approve_btn = types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{payment_id}_{user_id}")
    reject_btn = types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{payment_id}_{user_id}")
    markup.add(approve_btn, reject_btn)

    caption = (
        f"📥 <b>New Payment Request</b>\n"
        f"✦ ── ── ── ── ✦\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🆔 <b>Payment ID:</b> <code>{payment_id}</code>\n"
        f"💰 <b>Amount:</b> 100 INR"
    )

    try:
        # Try sending to admin group first
        bot.send_photo(ADMIN_CHAT_ID, file_id, caption=caption, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        # If group fails, send directly to admin's private chat
        try:
            bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception as e2:
            bot.reply_to(message, f"⚠️ Could not notify admin. Error: {e2}")
            return

    bot.reply_to(message, "✅ <b>Payment submitted!</b>\n⏳ Waiting for admin approval.", parse_mode="HTML")

# ============================================
# ADMIN APPROVE / REJECT
# ============================================
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    data = call.data

    if data.startswith("approve"):
        _, payment_id, user_id = data.split("_")
        amount = 100

        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        row = cursor.fetchone()
        if row:
            new_balance = row[0] + amount
            cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
        else:
            cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, amount))

        cursor.execute("UPDATE payments SET status='approved' WHERE payment_id=?", (payment_id,))
        conn.commit()

        bot.send_message(int(user_id), f"✅ <b>Payment Approved!</b>\n💰 <code>{amount}</code> INR added to your wallet.", parse_mode="HTML")
        bot.answer_callback_query(call.id, "✅ Approved")

    elif data.startswith("reject"):
        _, payment_id, user_id = data.split("_")
        cursor.execute("UPDATE payments SET status='rejected' WHERE payment_id=?", (payment_id,))
        conn.commit()
        bot.send_message(int(user_id), "❌ <b>Payment Rejected.</b>", parse_mode="HTML")
        bot.answer_callback_query(call.id, "❌ Rejected")

# ============================================
# BUY NUMBER (SastaOTP)
# ============================================
@bot.message_handler(func=lambda m: m.text == "📲 Buy Number")
def buy_number(message):
    user_id = message.from_user.id

    # Check user balance
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    if balance < 1:
        bot.reply_to(message, "❌ <b>Insufficient wallet balance.</b>\nPlease add funds via ➕ Add Funds.", parse_mode="HTML")
        return

    # For simplicity, we hardcode service='tg' and country='91' (India)
    service = "tg"
    country = "91"

    data = sasta_api_call({
        "action": "getNumber",
        "service": service,
        "country": country,
        "format": "json"
    })

    if data.get("status") != "OK":
        bot.reply_to(
            message,
            f"❌ <b>Failed to get number:</b>\n<code>{data.get('message', 'Unknown error')}</code>",
            parse_mode="HTML"
        )
        return

    activation_id = data.get("activation_id")
    order_id = data.get("order_id")
    number = data.get("number")
    price = data.get("price", 0.0)

    # Deduct from user's wallet
    new_balance = balance - price
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

    # Store activation in database
    cursor.execute(
        "INSERT INTO activations (user_id, activation_id, order_id, number, service, country, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, activation_id, order_id, number, service, country, "active")
    )
    conn.commit()

    # Send confirmation
    text = (
        f"✅ <b>Number Purchased!</b>\n"
        f"✦ ── ── ── ── ── ✦\n"
        f"📞 <b>Number:</b> <code>{number}</code>\n"
        f"🆔 <b>Activation ID:</b> <code>{activation_id}</code>\n"
        f"🔢 <b>Order ID:</b> <code>{order_id}</code>\n"
        f"💰 <b>Price:</b> <code>{price:.2f}</code> INR\n"
        f"💳 <b>New Balance:</b> <code>{new_balance:.2f}</code> INR\n\n"
        f"📩 Use <b>Check SMS</b> and send the Activation ID to get your OTP."
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# ============================================
# CHECK SMS (SastaOTP)
# ============================================
@bot.message_handler(func=lambda m: m.text == "📩 Check SMS")
def check_sms(message):
    msg = bot.reply_to(message, "📨 <b>Send your Activation ID</b> (or Order ID) to retrieve SMS.", parse_mode="HTML")
    bot.register_next_step_handler(msg, fetch_sms)

def fetch_sms(message):
    user_input = message.text.strip()
    user_id = message.from_user.id

    # Try to find activation in DB by activation_id or order_id
    cursor.execute(
        "SELECT activation_id FROM activations WHERE (activation_id=? OR order_id=?) AND user_id=?",
        (user_input, user_input, user_id)
    )
    row = cursor.fetchone()
    if not row:
        bot.reply_to(message, "❌ <b>No activation found</b> with that ID.\nMake sure you own this number.", parse_mode="HTML")
        return

    activation_id = row[0]

    # Call SastaOTP getStatus
    data = sasta_api_call({
        "action": "getStatus",
        "id": activation_id
    })

    status = data.get("status")
    if status == "STATUS_OK" or status == "OK":
        code = data.get("code") or data.get("sms") or data.get("message")
        if code:
            bot.reply_to(
                message,
                f"📩 <b>SMS Received</b>\n"
                f"✦ ── ── ── ── ✦\n"
                f"🔑 <b>OTP Code:</b> <code>{code}</code>",
                parse_mode="HTML"
            )
        else:
            bot.reply_to(message, "⌛ <b>No SMS yet.</b>\nPlease wait and try again later.", parse_mode="HTML")
    elif "WAIT" in status or status == "STATUS_WAIT_CODE":
        bot.reply_to(message, "⏳ <b>Waiting for SMS...</b>\nWe'll notify you when it arrives.\nUse /check again later.", parse_mode="HTML")
    else:
        bot.reply_to(
            message,
            f"❌ <b>Error:</b> {data.get('message', 'Unknown response')}\n{json.dumps(data, indent=2)}",
            parse_mode="HTML"
        )

# ============================================
# ADMIN: USERS COUNT
# ============================================
@bot.message_handler(commands=['users'])
def users(message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    bot.reply_to(message, f"👥 <b>Total Users:</b> <code>{total}</code>", parse_mode="HTML")

# ============================================
# ADMIN: BROADCAST
# ============================================
@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.reply_to(message, "📢 <b>Send your broadcast message</b> (HTML allowed)", parse_mode="HTML")
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    success = 0
    for user in users:
        try:
            bot.send_message(user[0], message.text, parse_mode="HTML")
            success += 1
        except:
            pass
    bot.reply_to(message, f"✅ <b>Broadcast sent to</b> <code>{success}</code> users.", parse_mode="HTML")

# ============================================
# RUN
# ============================================
print("🔥 SastaOTP Bot is running...")
bot.infinity_polling()
