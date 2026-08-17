import telebot
import requests
import sqlite3
import json
from telebot import types

# ============================================
# CONFIG
# ============================================
BOT_TOKEN = "8732063177:AAFjqxNLHh0moa_8daUbThK3zVoi_B6wXSU"
API_KEY = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE4MTAzMTA2ODUsImlhdCI6MTc3ODc3NDY4NSwicmF5IjoiNTgzYWVkN2M3NGJkZWJiMjY5ZGVmZTQ0YWJkZDkzMjYiLCJzdWIiOjQwNzA0Nzh9.Ug1AK9DI7Yz4fUPFGQaOpzMolLX2IaY5rGgr_dL98Z2oIZIFwzsVKUckSq7TRjKFRhfuK8mLbk5pVwAa-R1wkwNBrua-0rKDjzVWZdDQ-9Kygpmw46HIBqxJ3MvSKeYutbJtsZyVKpUG5WLSNL08JkDKBfTLfOBw3dGZyj8hJzzP01N0gCvIsqm0cMkPNyTQpMPAbYHjPq9JzEsdIZ2lb5WDryCcB6FCOyWeRT-sA1pIfTwv63UR_l0oShA0XH0jwzNqeKRjj291V9PvbWMg0gnH2or_-H_Q6dct4V7M8Tsr36CR_LhDEOfL18DjAbVfWGN0o_k7YPkdVg1aanBGbQ"

ADMIN_ID = 2119464081
ADMIN_CHAT_ID = -1003941256566
UPI_ID = "mr.sid@ptyes"

# ============================================
# BOT INIT
# ============================================
bot = telebot.TeleBot(BOT_TOKEN)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

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
    order_id TEXT,
    number TEXT,
    service TEXT,
    country TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# ============================================
# HELPERS: 5SIM API
# ============================================
def get_5sim_balance():
    try:
        r = requests.get("https://5sim.net/v1/user/profile", headers=headers)
        data = r.json()
        return data.get("balance", 0.0)
    except:
        return None

def get_5sim_prices(service, country):
    """Fetch price for a given service and country. Returns price as float or None."""
    try:
        # 5SIM price endpoint: /v1/guest/prices?country=india&operator=any
        url = f"https://5sim.net/v1/guest/prices?country={country}&operator=any"
        r = requests.get(url, headers=headers)
        data = r.json()
        # Data structure: { "country": { "operator": { "service": price } } }
        # We want price for the specified service
        price = data.get(country, {}).get("any", {}).get(service)
        if price is not None:
            return float(price)
        return None
    except:
        return None

def buy_5sim_number(service, country):
    """Purchase a number. Returns dict with order_id, phone, price."""
    url = f"https://5sim.net/v1/user/buy/activation/{country}/any/{service}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}: {r.text}"}
    data = r.json()
    if 'id' not in data:
        return {"error": f"API error: {data}"}
    return {
        "order_id": data['id'],
        "phone": data['phone'],
        "price": float(data.get('price', 0.0))
    }

def check_5sim_sms(order_id):
    """Check SMS for a given order ID. Returns list of SMS codes."""
    url = f"https://5sim.net/v1/user/check/{order_id}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}
    data = r.json()
    sms_list = data.get('sms', [])
    codes = [sms.get('code', '') for sms in sms_list if sms.get('code')]
    return {"codes": codes}

# ============================================
# SERVICES & COUNTRIES (mapped to 5SIM names)
# ============================================
SERVICES = {
    "Telegram": "telegram",
    "WhatsApp": "whatsapp",
    "Instagram": "instagram",
    "Facebook": "facebook",
    "Google": "google",
    "Amazon": "amazon",
    "Uber": "uber",
}

# 5SIM uses country names like "india", "usa", etc.
COUNTRIES = {
    "🇮🇳 India": "india",
    "🇺🇸 USA": "usa",
    "🇬🇧 UK": "uk",
    "🇷🇺 Russia": "russia",
    "🇨🇦 Canada": "canada",
    "🇦🇺 Australia": "australia",
    "🇩🇪 Germany": "germany",
    "🇫🇷 France": "france",
    "🇪🇸 Spain": "spain",
    "🇧🇷 Brazil": "brazil",
}

# Temporary storage for user selections
user_selection = {}  # user_id -> {"service": code, "country": code, "price": float}

# ============================================
# REPLY KEYBOARD (MAIN MENU)
# ============================================
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💰 Balance", "👛 Wallet")
    markup.row("📲 Buy Number", "📩 Check SMS")
    markup.row("➕ Add Funds")
    return markup

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

    try:
        bot.send_animation(
            chat_id,
            animation="https://media.giphy.com/media/RDZo7znAdn2u7sAcWH/giphy.gif",
            caption="🔥 <b>Welcome to Advanced 5SIM Bot</b>\n"
                    "✦ ── ── ── ── ── ── ✦\n"
                    "⚡ Fast & cheap virtual numbers\n"
                    "💎 24/7 OTP delivery",
            parse_mode="HTML"
        )
    except:
        pass

    bot.send_message(
        chat_id,
        "◈ <b>ADVANCED OTP BOT</b> ◈\n"
        "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
        "✨ Choose an option from the menu below.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

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
        f"<b>💰 Wallet Balance</b>\n✦ ── ── ── ── ✦\n<code>{balance:.2f}</code> USD",
        parse_mode="HTML"
    )

# ============================================
# API BALANCE (5SIM)
# ============================================
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def api_balance(message):
    bal = get_5sim_balance()
    if bal is None:
        bot.reply_to(message, "❌ Failed to fetch API balance.")
    else:
        bot.reply_to(
            message,
            f"<b>🌐 5SIM Balance</b>\n✦ ── ── ── ── ✦\n<code>{bal:.2f}</code> USD",
            parse_mode="HTML"
        )

# ============================================
# ADD FUNDS (UPI)
# ============================================
@bot.message_handler(func=lambda m: m.text == "➕ Add Funds")
def add_funds(message):
    text = (
        f"💳 <b>Send Payment via UPI</b>\n✦ ── ── ── ── ✦\n"
        f"🏦 <b>UPI ID:</b> <code>{UPI_ID}</code>\n\n"
        f"📸 After payment, send a <b>screenshot</b> of the transaction.\n"
        f"✅ Admin will approve and add funds to your wallet."
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# ============================================
# BUY NUMBER FLOW
# ============================================
@bot.message_handler(func=lambda m: m.text == "📲 Buy Number")
def buy_number(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    if balance < 0.01:
        bot.reply_to(message, "❌ <b>Insufficient wallet balance.</b>\nPlease add funds via ➕ Add Funds.", parse_mode="HTML")
        return

    # Show service selection
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, code in SERVICES.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"service_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back"))
    bot.send_message(chat_id, "📱 <b>Select the service:</b>", reply_markup=markup, parse_mode="HTML")

# ============================================
# SERVICE SELECTION CALLBACK
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def service_selected(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    service_code = call.data.split("_")[1]

    if user_id not in user_selection:
        user_selection[user_id] = {}
    user_selection[user_id]["service"] = service_code

    # Show country selection
    markup = types.InlineKeyboardMarkup(row_width=2)
    for name, code in COUNTRIES.items():
        markup.add(types.InlineKeyboardButton(name, callback_data=f"country_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="service_back"))
    bot.edit_message_text("🌍 <b>Select your country:</b>", chat_id, call.message.message_id, reply_markup=markup, parse_mode="HTML")
    bot.answer_callback_query(call.id)

# ============================================
# COUNTRY SELECTION CALLBACK (Fetch price from 5SIM)
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def country_selected(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    country_code = call.data.split("_")[1]

    user_selection[user_id]["country"] = country_code
    service = user_selection[user_id]["service"]

    # Fetch price from 5SIM
    price = get_5sim_prices(service, country_code)

    if price is None:
        price = 0.0
        confirm_text = "⚠️ Could not fetch price. Continue anyway?"
    else:
        confirm_text = f"💰 <b>Price:</b> <code>{price:.2f}</code> USD\nConfirm purchase?"

    user_selection[user_id]["price"] = price

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Confirm", callback_data="confirm_buy"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_buy"))

    service_name = [name for name, code in SERVICES.items() if code == service][0]
    country_name = [name for name, code in COUNTRIES.items() if code == country_code][0]

    bot.edit_message_text(
        f"📞 <b>Service:</b> {service_name}\n🌍 <b>Country:</b> {country_name}\n{confirm_text}",
        chat_id, call.message.message_id, reply_markup=markup, parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# ============================================
# CONFIRM / CANCEL BUY (Purchase from 5SIM)
# ============================================
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_buy", "cancel_buy"])
def confirm_cancel_buy(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if call.data == "cancel_buy":
        bot.edit_message_text("❌ Purchase cancelled.", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
        if user_id in user_selection:
            del user_selection[user_id]
        return

    # Confirm purchase
    service = user_selection[user_id]["service"]
    country = user_selection[user_id]["country"]
    price = user_selection[user_id].get("price", 0.0)

    # Buy number from 5SIM
    result = buy_5sim_number(service, country)

    if "error" in result:
        bot.edit_message_text(
            f"❌ <b>Failed to get number:</b>\n<code>{result['error']}</code>",
            chat_id, call.message.message_id, parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)
        if user_id in user_selection:
            del user_selection[user_id]
        return

    order_id = result["order_id"]
    phone = result["phone"]
    actual_price = result["price"]

    # Use the fetched price (if available) else fallback to actual_price from buy response
    if price <= 0.0:
        price = actual_price

    # Deduct balance
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0
    new_balance = balance - price
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

    # Store activation
    cursor.execute(
        "INSERT INTO activations (user_id, order_id, number, service, country, status) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, order_id, phone, service, country, "active")
    )
    conn.commit()

    text = (
        f"✅ <b>Number Purchased!</b>\n✦ ── ── ── ── ── ✦\n"
        f"📞 <b>Number:</b> <code>{phone}</code>\n"
        f"🆔 <b>Order ID:</b> <code>{order_id}</code>\n"
        f"💰 <b>Price:</b> <code>{price:.2f}</code> USD\n"
        f"💳 <b>New Balance:</b> <code>{new_balance:.2f}</code> USD\n\n"
        f"📩 Use <b>Check SMS</b> and send the Order ID to get your OTP."
    )
    bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(call.id)

    # Clean up
    if user_id in user_selection:
        del user_selection[user_id]

# ============================================
# CHECK SMS (text input)
# ============================================
@bot.message_handler(func=lambda m: m.text == "📩 Check SMS")
def check_sms(message):
    msg = bot.reply_to(message, "📨 <b>Send your Order ID</b> to retrieve SMS.", parse_mode="HTML")
    bot.register_next_step_handler(msg, fetch_sms)

def fetch_sms(message):
    order_id = message.text.strip()
    user_id = message.from_user.id

    # Verify that this order belongs to the user (optional)
    cursor.execute(
        "SELECT order_id FROM activations WHERE order_id=? AND user_id=?",
        (order_id, user_id)
    )
    if not cursor.fetchone():
        bot.reply_to(message, "❌ <b>No activation found</b> with that Order ID.\nMake sure you own this number.", parse_mode="HTML")
        return

    result = check_5sim_sms(order_id)

    if "error" in result:
        bot.reply_to(message, f"❌ Error: {result['error']}")
        return

    codes = result["codes"]
    if not codes:
        bot.reply_to(message, "⌛ <b>No SMS yet.</b>\nPlease wait and try again later.", parse_mode="HTML")
    else:
        text = "📩 <b>SMS Received</b>\n✦ ── ── ── ── ✦\n"
        for code in codes:
            text += f"🔑 <code>{code}</code>\n"
        bot.reply_to(message, text, parse_mode="HTML")

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
        f"💰 <b>Amount:</b> 100 USD"
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

        bot.send_message(int(user_id), f"✅ <b>Payment Approved!</b>\n💰 <code>{amount}</code> USD added to your wallet.", parse_mode="HTML")
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
# BACK TO MENU (inline callback)
# ============================================
@bot.callback_query_handler(func=lambda call: call.data == "menu_back" or call.data == "service_back")
def back_to_menu(call):
    chat_id = call.message.chat.id
    bot.edit_message_text("↩️ Returned to menu.", chat_id, call.message.message_id)
    bot.answer_callback_query(call.id)
    # Send main menu again (or user can press start)

# ============================================
# RUN
# ============================================
print("🔥 Advanced 5SIM Bot is running with service/country selection...")
bot.infinity_polling()
