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

# --------------------------------------------
# PRICE / BUTTON HELPERS
# --------------------------------------------
def to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def get_country_api_variants(country_code):
    """Try the common country representations used by compatible SastaSMS APIs.
    The dashboard is country-specific, while the API may accept a calling code,
    ISO-2 code, or country name. We keep the user's visible country selection unchanged.
    """
    country_map = {
        "91": ["91", "IN", "in", "India", "india"],
        "1": ["1", "US", "us", "USA", "usa"],
        "44": ["44", "GB", "gb", "UK", "uk", "United Kingdom", "united kingdom"],
        "7": ["7", "RU", "ru", "Russia", "russia"],
        "61": ["61", "AU", "au", "Australia", "australia"],
        "49": ["49", "DE", "de", "Germany", "germany"],
        "33": ["33", "FR", "fr", "France", "france"],
        "34": ["34", "ES", "es", "Spain", "spain"],
        "55": ["55", "BR", "br", "Brazil", "brazil"],
    }
    variants = country_map.get(str(country_code), [str(country_code)])
    # Canada and USA share calling code 1, so add Canada variants only when needed
    if str(country_code) == "1":
        variants += ["CA", "ca", "Canada", "canada"]
    return list(dict.fromkeys(variants))


def extract_price_pairs(data, service, requested_country):
    """Extract (price, operator) pairs from several possible API response layouts."""
    if not isinstance(data, dict) or data.get("status") == "ERROR":
        return []

    country_str = str(requested_country)
    service_str = str(service)
    results = []

    # Prefer the exact requested country block when it exists.
    # If the response clearly contains many country blocks and the requested country
    # is absent, do NOT fall back to the global service price (for example a cheap
    # Telegram price from another country).
    targets = []
    country_blocks = [k for k, v in data.items() if isinstance(v, dict) and str(k).isdigit()]
    has_multiple_countries = len(country_blocks) > 1

    if isinstance(data.get(country_str), dict):
        targets.append((data[country_str], "any"))
    elif not has_multiple_countries and isinstance(data.get(service_str), dict):
        targets.append((data[service_str], "any"))

    if not has_multiple_countries:
        targets.append((data, "any"))

    visited = set()

    def add_price(value, operator="any", count=None):
        p = to_float(value, None)
        if p is None or p <= 0:
            return
        # Some panel/API responses omit count. A real price is still useful; stock is
        # confirmed by getNumber during purchase.
        if count is not None:
            try:
                if int(float(count)) <= 0:
                    return
            except (TypeError, ValueError):
                pass
        results.append((p, operator))

    def scan(obj, current_operator="any", depth=0):
        if not isinstance(obj, dict) or depth > 8:
            return
        marker = id(obj)
        if marker in visited:
            return
        visited.add(marker)

        # Direct price object: {cost/price/amount, count}
        direct = None
        for key in ("cost", "price", "amount"):
            if key in obj:
                direct = obj[key]
                break
        if direct is not None:
            add_price(direct, current_operator, obj.get("count"))

        for k, v in obj.items():
            if k in ("cost", "price", "amount", "count", "status", "message"):
                continue

            # Price -> count format, e.g. {"49.79": 3}
            if isinstance(v, (int, float, str)):
                p = to_float(k, None)
                if p is not None:
                    add_price(p, current_operator, v)
                continue

            if isinstance(v, dict):
                next_operator = current_operator
                if str(k) not in (country_str, service_str):
                    next_operator = str(k)
                scan(v, next_operator, depth + 1)

    for target, op in targets:
        scan(target, op)

    unique = {}
    for price, operator in results:
        # Keep the first operator for each exact price.
        unique.setdefault(round(price, 8), operator)
    return sorted(((p, op) for p, op in unique.items()), key=lambda x: x[0])


def get_all_prices(service, country):
    """Return sorted live prices for the selected service/country."""
    best = []
    for api_country in get_country_api_variants(country):
        data = sasta_api_call({
            "action": "getPrices",
            "service": service,
            "country": api_country,
            "format": "json"
        })
        prices = extract_price_pairs(data, service, api_country)
        if prices:
            best = prices
            break
    return best


def get_panel_price_info(service, country):
    """Get the cheapest live price, operator, and API country representation."""
    for api_country in get_country_api_variants(country):
        data = sasta_api_call({
            "action": "getPrices",
            "service": service,
            "country": api_country,
            "format": "json"
        })
        prices = extract_price_pairs(data, service, api_country)
        if prices:
            return prices[0][0], prices[0][1], api_country
    return None, "any", None

def build_service_keyboard(animation_frame=0):
    markup = types.InlineKeyboardMarkup(row_width=2)
    frames = ("⚡", "✨", "💠", "✨")
    logo = frames[animation_frame % len(frames)]

    for name, code in SERVICES.items():
        text = f"{logo} {name}" if animation_frame % 2 == 0 else f"{name} {logo}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f"service_{code}"))

    markup.add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back"))
    return markup

def build_country_keyboard(animation_frame=0):
    markup = types.InlineKeyboardMarkup(row_width=2)
    frames = ("⚡", "✨", "💠", "✨")
    logo = frames[animation_frame % len(frames)]

    for name, code in COUNTRIES.items():
        text = f"{logo} {name}" if animation_frame % 2 == 0 else f"{name} {logo}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f"country_{code}"))

    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="service_back"))
    return markup

# Message-id -> animation token. A new callback cancels the old animation.
button_animation_tokens = {}

def animate_button_logo(chat_id, message_id, keyboard_builder, frames=4, delay=0.45):
    token = object()
    button_animation_tokens[message_id] = token

    def worker():
        try:
            for frame in range(1, frames + 1):
                time.sleep(delay)
                if button_animation_tokens.get(message_id) is not token:
                    break
                bot.edit_message_reply_markup(
                    chat_id,
                    message_id,
                    reply_markup=keyboard_builder(frame)
                )
        except Exception:
            pass
        finally:
            if button_animation_tokens.get(message_id) is token:
                button_animation_tokens.pop(message_id, None)

    threading.Thread(target=worker, daemon=True).start()

def cancel_button_animation(message_id):
    button_animation_tokens.pop(message_id, None)

# ============================================
# SERVICES & COUNTRIES
# ============================================
SERVICES = {
    "Telegram": "tg",
    "WhatsApp": "wa",
    "Instagram": "ig",
    "Facebook": "fb",
    "Google": "go",
    "Amazon": "am",
    "Uber": "ub",
}

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

user_selection = {}

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
            caption="🔥 <b>Welcome to SastaOTP Bot</b>\n"
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
        f"<b>💰 Wallet Balance</b>\n✦ ── ── ── ── ✦\n<code>{balance:.2f}</code> INR",
        parse_mode="HTML"
    )

# ============================================
# API BALANCE (SastaOTP)
# ============================================
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def api_balance(message):
    data = sasta_api_call({"action": "getBalance"})
    if data.get("status") == "OK":
        bal = data.get("balance") or data.get("ACCESS_BALANCE") or 0.0
        currency = data.get("currency", "INR")
        bot.reply_to(
            message,
            f"<b>🌐 SastaOTP Balance</b>\n✦ ── ── ── ── ✦\n<code>{bal}</code> {currency}",
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

    if balance < 1:
        bot.reply_to(message, "❌ <b>Insufficient wallet balance.</b>\nPlease add funds via ➕ Add Funds.", parse_mode="HTML")
        return

    sent = bot.send_message(
        chat_id,
        "📱 <b>Select the service:</b>",
        reply_markup=build_service_keyboard(0),
        parse_mode="HTML"
    )
    animate_button_logo(chat_id, sent.message_id, build_service_keyboard)

# ============================================
# SERVICE SELECTION CALLBACK
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def service_selected(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    service_code = call.data.split("_")[1]

    cancel_button_animation(call.message.message_id)

    if user_id not in user_selection:
        user_selection[user_id] = {}
    user_selection[user_id]["service"] = service_code

    bot.edit_message_text(
        "🌍 <b>Select your country:</b>",
        chat_id,
        call.message.message_id,
        reply_markup=build_country_keyboard(0),
        parse_mode="HTML"
    )
    animate_button_logo(chat_id, call.message.message_id, build_country_keyboard)
    bot.answer_callback_query(call.id)

# ============================================
# COUNTRY SELECTION CALLBACK
# ============================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("country_"))
def country_selected(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    country_code = call.data.split("_")[1]

    cancel_button_animation(call.message.message_id)

    user_selection[user_id]["country"] = country_code

    service = user_selection[user_id]["service"]
    service_name = [name for name, code in SERVICES.items() if code == service][0]

    # Checks cheapest price first
    panel_price, best_operator, api_country = get_panel_price_info(service, country_code)
    
    if panel_price is None:
        bot.edit_message_text(
            "❌ <b>Out of Stock</b>\n"
            "There are currently 0 numbers available for this country/service.\n\n"
            "Please try a different option.",
            chat_id,
            call.message.message_id,
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)
        return

    user_selection[user_id]["panel_price"] = panel_price
    user_selection[user_id]["operator"] = best_operator
    user_selection[user_id]["api_country"] = api_country

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Confirm", callback_data="confirm_buy"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_buy"))

    bot.edit_message_text(
        f"📞 <b>Service:</b> {service_name}\n🌍 <b>Country:</b> {country_code}\n\n"
        f"💰 <b>Best Available Price:</b> <code>{panel_price:.2f}</code> INR\n\n"
        f"Confirm purchase?",
        chat_id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)

# ============================================
# CONFIRM / CANCEL BUY (WITH SMART FALLBACK)
# ============================================
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_buy", "cancel_buy", "confirm_fallback_buy"])
def confirm_cancel_buy(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if call.data == "cancel_buy":
        bot.edit_message_text("❌ Purchase cancelled.", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
        if user_id in user_selection:
            del user_selection[user_id]
        return

    if user_id not in user_selection:
        bot.answer_callback_query(call.id, "Session expired. Please select again.", show_alert=True)
        return

    service = user_selection[user_id]["service"]
    country = user_selection[user_id]["country"]
    panel_price = user_selection[user_id].get("panel_price")
    operator = user_selection[user_id].get("operator", "any")
    api_country = user_selection[user_id].get("api_country", country)

    # Step 1: Request the currently selected cheapest route. Do not send a stale
    # maxPrice value; the panel price is used for selection and the API confirms stock.
    number_params = {
        "action": "getNumber",
        "service": service,
        "country": api_country,
        "operator": operator,
        "format": "json"
    }
    data = sasta_api_call(number_params)

    # Step 2: If the cheapest route is unavailable, refresh the panel and try only
    # the next-cheapest live option. Never jump directly to a high-priced option.
    if data.get("status") != "OK":
        err_msg = str(data.get("message", "")).lower()
        if call.data != "confirm_fallback_buy" and "balance" not in err_msg and "key" not in err_msg:
            refreshed = []
            for candidate_country in get_country_api_variants(country):
                fresh_data = sasta_api_call({
                    "action": "getPrices",
                    "service": service,
                    "country": candidate_country,
                    "format": "json"
                })
                prices = extract_price_pairs(fresh_data, service, candidate_country)
                if prices:
                    refreshed = [(p, op, candidate_country) for p, op in prices]
                    break

            # Pick only the immediate next price above the failed price.
            current_price = panel_price or 0
            next_candidates = [item for item in refreshed if item[0] > current_price + 0.000001]
            if next_candidates:
                current_panel_price, next_operator, next_country = next_candidates[0]
                user_selection[user_id]["panel_price"] = current_panel_price
                user_selection[user_id]["operator"] = next_operator
                user_selection[user_id]["api_country"] = next_country

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✅ Confirm at Next Price", callback_data="confirm_fallback_buy"))
                markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_buy"))

                bot.edit_message_text(
                    f"⚠️ <b>Cheapest route ({current_price:.2f} INR) is unavailable.</b>\n\n"
                    f"📊 <b>Next Live Panel Price:</b> <code>{current_panel_price:.2f}</code> INR\n\n"
                    f"Would you like to continue at this next price?",
                    chat_id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                bot.answer_callback_query(call.id)
                return

        bot.edit_message_text(
            f"❌ <b>Failed to get number:</b>\n<code>{data.get('message', 'Unknown error')}</code>",
            chat_id, call.message.message_id, parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)
        if user_id in user_selection:
            del user_selection[user_id]
        return

    activation_id = data.get("activation_id")
    order_id = data.get("order_id")
    number = data.get("number")
    price = to_float(data.get("price"), None)
    if price is None or price <= 0:
        price = to_float(panel_price, None)

    if price is None or price <= 0:
        bot.edit_message_text("❌ <b>Invalid price returned by the API.</b>", chat_id, call.message.message_id, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        if user_id in user_selection:
            del user_selection[user_id]
        return

    # Check user balance
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    if balance < price:
        bot.edit_message_text(
            f"❌ <b>Insufficient balance.</b>\nRequired: <code>{price:.2f}</code> INR\nYour balance: <code>{balance:.2f}</code> INR",
            chat_id, call.message.message_id, parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)
        if user_id in user_selection:
            del user_selection[user_id]
        return

    # Deduct balance
    new_balance = balance - price
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))

    # Store activation
    cursor.execute(
        "INSERT INTO activations (user_id, activation_id, order_id, number, service, country, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, activation_id, order_id, number, service, country, "active")
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
    bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(call.id)

    if user_id in user_selection:
        del user_selection[user_id]

# ============================================
# CHECK SMS (text input)
# ============================================
@bot.message_handler(func=lambda m: m.text == "📩 Check SMS")
def check_sms(message):
    msg = bot.reply_to(message, "📨 <b>Send your Activation ID</b> (or Order ID) to retrieve SMS.", parse_mode="HTML")
    bot.register_next_step_handler(msg, fetch_sms)

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
# BACK TO MENU (inline callback)
# ============================================
@bot.callback_query_handler(func=lambda call: call.data == "menu_back" or call.data == "service_back")
def back_to_menu(call):
    chat_id = call.message.chat.id
    bot.edit_message_text("↩️ Returned to menu.", chat_id, call.message.message_id)
    bot.answer_callback_query(call.id)

# ============================================
# RUN
# ============================================
print("🔥 SastaOTP Bot is running with Smart Cheap -> Current Panel Price Fallback...")
bot.infinity_polling()
