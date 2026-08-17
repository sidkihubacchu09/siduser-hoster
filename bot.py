import telebot
import requests
import sqlite3
import time
import json
import threading
from telebot import types

# ============================================
# CONFIG
# ============================================
BOT_TOKEN = "8732063177:AAFjqxNLHh0moa_8daUbThK3zVoi_B6wXSU"

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

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    status TEXT,
    screenshot TEXT
)
''')

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
# HELPERS
# ============================================
def sasta_api_call(params):
    params["api_key"] = SASTA_API_KEY
    try:
        resp = requests.get(SASTA_BASE_URL, params=params, timeout=15)
        if resp.status_code == 200:
            try:
                return resp.json()
            except:
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
# ANIMATED MENU
# ============================================
# Emoji sets for each button (cycle through these)
EMOJI_SETS = {
    "balance": ["💰", "💎", "🪙"],
    "wallet": ["👛", "👜", "💼"],
    "buy": ["📲", "📱", "📞"],
    "check": ["📩", "📨", "📧"],
    "add": ["➕", "✨", "💳"],
}

# Store animation threads and control flags
animations = {}  # chat_id -> {"thread": thread, "stop": False, "message_id": msg_id}

def build_menu_keyboard(emoji_idx):
    """Build the inline keyboard with current emojis at given index."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton(
        f"{EMOJI_SETS['balance'][emoji_idx % len(EMOJI_SETS['balance'])]} Balance",
        callback_data="menu_balance"
    )
    btn2 = types.InlineKeyboardButton(
        f"{EMOJI_SETS['wallet'][emoji_idx % len(EMOJI_SETS['wallet'])]} Wallet",
        callback_data="menu_wallet"
    )
    btn3 = types.InlineKeyboardButton(
        f"{EMOJI_SETS['buy'][emoji_idx % len(EMOJI_SETS['buy'])]} Buy Number",
        callback_data="menu_buy"
    )
    btn4 = types.InlineKeyboardButton(
        f"{EMOJI_SETS['check'][emoji_idx % len(EMOJI_SETS['check'])]} Check SMS",
        callback_data="menu_check"
    )
    btn5 = types.InlineKeyboardButton(
        f"{EMOJI_SETS['add'][emoji_idx % len(EMOJI_SETS['add'])]} Add Funds",
        callback_data="menu_add"
    )
    markup.add(btn1, btn2, btn3, btn4, btn5)
    return markup

def animate_menu(chat_id, message_id):
    """Background thread: updates the menu message every 2 seconds."""
    idx = 0
    while animations.get(chat_id, {}).get("stop", False) is False:
        try:
            new_markup = build_menu_keyboard(idx)
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=new_markup)
            idx += 1
            time.sleep(2)
        except Exception:
            # Message might be deleted or bot can't edit; stop animation
            break
    # Clean up when loop ends
    if chat_id in animations:
        animations[chat_id]["stop"] = True
        animations[chat_id]["thread"] = None

def start_animation(chat_id, message_id):
    """Start the animation for a given menu message."""
    # Stop any previous animation for this chat
    if chat_id in animations:
        animations[chat_id]["stop"] = True
        if animations[chat_id]["thread"] and animations[chat_id]["thread"].is_alive():
            animations[chat_id]["thread"].join(timeout=1)
    # Start new thread
    animations[chat_id] = {
        "stop": False,
        "message_id": message_id,
        "thread": threading.Thread(target=animate_menu, args=(chat_id, message_id), daemon=True)
    }
    animations[chat_id]["thread"].start()

def stop_animation(chat_id):
    """Stop the animation for a chat."""
    if chat_id in animations:
        animations[chat_id]["stop"] = True
        # Let the thread exit naturally

# ============================================
# COUNTRIES FOR NUMBER PURCHASE
# ============================================
COUNTRIES = {
    "🇮🇳 India": "91",
    "🇺🇸 USA": "1",
    "🇬🇧 UK": "44",
    "🇷🇺 Russia": "7",
    "🇨🇦 Canada": "1",
    "🇦🇺 Australia": "61",
    "🇩🇪 Germany": "49",
    "🇫🇷 France": "33",
    "🇪🇸 Spain": "34",
    "🇧🇷 Brazil": "55",
}

def show_country_selection(chat_id, user_id):
    """Show an inline keyboard with country options."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, code in COUNTRIES.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"country_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back"))
    bot.send_message(chat_id, "🌍 <b>Select your country:</b>", reply_markup=markup, parse_mode="HTML")

# ============================================
# START
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0))
        conn.commit()

    # Send welcome animation (optional)
    try:
        bot.send_animation(
            chat_id,
            animation="https://media.giphy.com/media/RDZo7znAdn2u7sAcWH/giphy.gif",
            caption="🔥 <b>Welcome to SastaOTP Bot</b>\n"
                    "✦ ── ── ── ── ── ── ✦\n"
                    "⚡ Fast & cheap virtual numbers\n"
                    "💎 24/7 OTP delivery",
            parse_mode="HTML"
        )
    except:
        pass

    # Send the animated menu
    msg = bot.send_message(
        chat_id,
        "◈ <b>ADVANCED OTP BOT</b> ◈\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        "✨ Choose an option below:",
        reply_markup=build_menu_keyboard(0),
        parse_mode="HTML"
    )
    start_animation(chat_id, msg.message_id)

# ============================================
# ID COMMAND
# ============================================
@bot.message_handler(commands=['id'])
def get_ids(message):
    text = (
        f"👤 <b>User ID:</b> <code>{message.from_user.id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{message.chat.id}</code>"
    )
    bot.reply_to(message, text, parse_mode="HTML")

# ============================================
# MENU CALLBACKS
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def menu_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    # Stop animation for this chat
    stop_animation(chat_id)

    if data == "menu_balance":
        # Show API balance
        api_balance_callback(call)
    elif data == "menu_wallet":
        wallet_callback(call)
    elif data == "menu_buy":
        buy_number_callback(call)
    elif data == "menu_check":
        check_sms_callback(call)
    elif data == "menu_add":
        add_funds_callback(call)
    elif data == "menu_back":
        # Return to main menu (send new menu and restart animation)
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "◈ <b>ADVANCED OTP BOT</b> ◈\n"
            "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            "✨ Choose an option below:",
            reply_markup=build_menu_keyboard(0),
            parse_mode="HTML"
        )
        start_animation(chat_id, msg.message_id)

    bot.answer_callback_query(call.id)

def api_balance_callback(call):
    chat_id = call.message.chat.id
    data = sasta_api_call({"action": "getBalance"})
    if data.get("status") == "OK":
        bal = data.get("balance") or data.get("ACCESS_BALANCE") or 0.0
        currency = data.get("currency", "INR")
        bot.send_message(
            chat_id,
            f"<b>🌐 SastaOTP Balance</b>\n✦ ── ── ── ── ✦\n<code>{bal}</code> {currency}",
            parse_mode="HTML"
        )
    else:
        bot.send_message(chat_id, f"❌ <b>Error:</b> {data.get('message', 'Unknown')}", parse_mode="HTML")

def wallet_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0
    bot.send_message(
        chat_id,
        f"<b>💰 Wallet Balance</b>\n✦ ── ── ── ── ✦\n<code>{balance:.2f}</code> INR",
        parse_mode="HTML"
    )

def buy_number_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # Check local balance first
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    if balance < 1:
        bot.send_message(chat_id, "❌ <b>Insufficient wallet balance.</b>\nPlease add funds via ➕ Add Funds.", parse_mode="HTML")
        return

    # Show country selection
    show_country_selection(chat_id, user_id)

def check_sms_callback(call):
    chat_id = call.message.chat.id
    msg = bot.send_message(chat_id, "📨 <b>Send your Activation ID</b> (or Order ID) to retrieve SMS.", parse_mode="HTML")
    bot.register_next_step_handler(msg, fetch_sms)

def add_funds_callback(call):
    chat_id = call.message.chat.id
    text = (
        f"💳 <b>Send Payment via UPI</b>\n✦ ── ── ── ── ✦\n"
        f"🏦 <b>UPI ID:</b> <code>{UPI_ID}</code>\n\n"
        f"📸 After payment, send a <b>screenshot</b> of the transaction.\n"
        f"✅ Admin will approve and add funds to your wallet."
    )
    bot.send_message(chat_id, text, parse_mode="HTML")

# ============================================
# COUNTRY SELECTION CALLBACK
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def country_selected(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    country_code = call.data.split("_")[1]

    # Stop animation if any
    stop_animation(chat_id)

    # Proceed to buy number with selected country
    process_buy_number(chat_id, user_id, country_code)
    bot.answer_callback_query(call.id)

def process_buy_number(chat_id, user_id, country_code):
    """Call SastaOTP getNumber with selected country."""
    service = "tg"  # hardcoded as before

    data = sasta_api_call({
        "action": "getNumber",
        "service": service,
        "country": country_code,
        "format": "json"
    })

    if data.get("status") != "OK":
        bot.send_message(
            chat_id,
            f"❌ <b>Failed to get number:</b>\n<code>{data.get('message', 'Unknown error')}</code>",
            parse_mode="HTML"
        )
        return

    activation_id = data.get("activation_id")
    order_id = data.get("order_id")
    number = data.get("number")
    price = float(data.get("price", 0.0))

    # Deduct from user's wallet
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0
    new_balance = balance - price
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

    # Store activation
    cursor.execute(
        "INSERT INTO activations (user_id, activation_id, order_id, number, service, country, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, activation_id, order_id, number, service, country_code, "active")
    )
    conn.commit()

    text = (
        f"✅ <b>Number Purchased!</b>\n✦ ── ── ── ── ── ✦\n"
        f"📞 <b>Number:</b> <code>{number}</code>\n"
        f"🆔 <b>Activation ID:</b> <code>{activation_id}</code>\n"
        f"🔢 <b>Order ID:</b> <code>{order_id}</code>\n"
        f"💰 <b>Price:</b> <code>{price:.2f}</code> INR\n"
        f"💳 <b>New Balance:</b> <code>{new_balance:.2f}</code> INR\n\n"
        f"📩 Use <b>Check SMS</b> and send the Activation ID to get your OTP."
    )
    bot.send_message(chat_id, text, parse_mode="HTML")

# ============================================
# CHECK SMS (text input)
# ============================================
def fetch_sms(message):
    user_input = message.text.strip()
    user_id = message.from_user.id
    chat_id = message.chat.id

    cursor.execute(
        "SELECT activation_id FROM activations WHERE (activation_id=? OR order_id=?) AND user_id=?",
        (user_input, user_input, user_id)
    )
    row = cursor.fetchone()
    if not row:
        bot.reply_to(message, "❌ <b>No activation found</b> with that ID.\nMake sure you own this number.", parse_mode="HTML")
        return

    activation_id = row[0]

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
                f"📩 <b>SMS Received</b>\n✦ ── ── ── ── ✦\n🔑 <b>OTP Code:</b> <code>{code}</code>",
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
# PAYMENT SCREENSHOT HANDLER
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
        f"📥 <b>New Payment Request</b>\n✦ ── ── ── ── ✦\n"
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🆔 <b>Payment ID:</b> <code>{payment_id}</code>\n"
        f"💰 <b>Amount:</b> 100 INR"
    )

    try:
        bot.send_photo(ADMIN_CHAT_ID, file_id, caption=caption, reply_markup=markup, parse_mode="HTML")
    except Exception:
        try:
            bot.send_photo(ADMIN_ID, file_id, caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception as e2:
            bot.reply_to(message, f"⚠️ Could not notify admin. Error: {e2}")
            return

    bot.reply_to(message, "✅ <b>Payment submitted!</b>\n⏳ Waiting for admin approval.", parse_mode="HTML")

# ============================================
# ADMIN APPROVE / REJECT CALLBACKS
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve") or call.data.startswith("reject"))
def admin_payment_callback(call):
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
# ADMIN COMMANDS
# ============================================
@bot.message_handler(commands=['users'])
def users(message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    bot.reply_to(message, f"👥 <b>Total Users:</b> <code>{total}</code>", parse_mode="HTML")

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
print("🔥 SastaOTP Bot is running with animated menu and country selection...")
bot.infinity_polling()
