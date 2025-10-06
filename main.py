import logging
import sqlite3
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError, FloodWaitError, PhoneCodeExpiredError

# ===== CONFIGURATION =====
BOT_TOKEN = "8440425262:AAEXO7zBqDcizTE6QDJyqQy5gnZjZHmxp0k"
API_ID = 24990959
API_HASH = "686baf9f2da85c2bac5b420848e648bf"
DB_NAME = "aftab_bot.db"
ADMIN_USERNAME = "azttech"

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global session storage
user_sessions = {}
broadcast_tasks = {}

# ===== DATABASE =====
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
        account_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        phone_number TEXT,
        session_string TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER PRIMARY KEY,
        ad_message TEXT DEFAULT 'Welcome to our service! 🚀',
        cycle_interval INTEGER DEFAULT 120,
        is_broadcasting BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        account_id INTEGER,
        group_name TEXT,
        group_username TEXT,
        group_id_num INTEGER,
        member_count INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (account_id) REFERENCES accounts (account_id)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS analytics (
        analytic_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        messages_sent INTEGER DEFAULT 0,
        groups_reached INTEGER DEFAULT 0,
        date DATE DEFAULT CURRENT_DATE,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

# ===== DATABASE HELPERS =====
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
                   (user_id, username, first_name, last_name))
    cursor.execute('INSERT OR IGNORE INTO settings (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def get_user_settings(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    conn.close()
    return settings

def update_ad_message(user_id, message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE settings SET ad_message = ? WHERE user_id = ?', (message, user_id))
    conn.commit()
    conn.close()

def update_interval(user_id, interval):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE settings SET cycle_interval = ? WHERE user_id = ?', (interval, user_id))
    conn.commit()
    conn.close()

def update_broadcast_status(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE settings SET is_broadcasting = ? WHERE user_id = ?', (status, user_id))
    conn.commit()
    conn.close()

def get_accounts_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM accounts WHERE user_id = ? AND is_active = 1', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_accounts(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE user_id = ? AND is_active = 1', (user_id,))
    accounts = cursor.fetchall()
    conn.close()
    return accounts

def add_account(user_id, phone_number, session_string):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO accounts (user_id, phone_number, session_string) VALUES (?, ?, ?)',
                   (user_id, phone_number, session_string))
    conn.commit()
    conn.close()

def get_groups_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM groups WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_groups(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM groups WHERE user_id = ?', (user_id,))
    groups = cursor.fetchall()
    conn.close()
    return groups

def add_group(user_id, account_id, group_name, group_username, group_id_num, member_count):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO groups (user_id, account_id, group_name, group_username, group_id_num, member_count) VALUES (?, ?, ?, ?, ?, ?)',
                   (user_id, account_id, group_name, group_username, group_id_num, member_count))
    conn.commit()
    conn.close()

def get_analytics(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(messages_sent), SUM(groups_reached) FROM analytics WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result or (0, 0)

def update_analytics(user_id, messages_sent, groups_reached):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO analytics (user_id, messages_sent, groups_reached) VALUES (?, ?, ?)',
                   (user_id, messages_sent, groups_reached))
    conn.commit()
    conn.close()

# ===== TELEGRAM CLIENT =====
async def create_telegram_client():
    return TelegramClient(StringSession(), API_ID, API_HASH,
                          device_model="Samsung Galaxy S21",
                          system_version="Android 12",
                          app_version="8.7.2",
                          lang_code="en",
                          system_lang_code="en-US")

# ===== OTP, 2FA, SESSION FUNCTIONS =====
async def cleanup_user_session(user_id):
    if user_id in user_sessions:
        session_data = user_sessions[user_id]
        client = session_data.get("client")
        if client:
            try: await client.disconnect()
            except: pass
        del user_sessions[user_id]

async def send_otp_code(phone_number, user_id, update: Update):
    try:
        await cleanup_user_session(user_id)
        client = await create_telegram_client()
        await client.connect()
        if await client.is_user_authorized():
            await update.message.reply_text("❌ Phone already authorized in another session.")
            await client.disconnect()
            return False
        sent_code = await client.send_code_request(phone_number)
        user_sessions[user_id] = {"type":"awaiting_code","client":client,"phone":phone_number,"phone_code_hash":sent_code.phone_code_hash,"attempts":0,"created_at":datetime.now()}
        await update.message.reply_text(f"✅ OTP sent to {phone_number}. Enter code:")
        return True
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending OTP: {e}")
        return False

async def verify_otp_code(user_id, code, update: Update):
    try:
        if user_id not in user_sessions: return False
        session_data = user_sessions[user_id]
        client = session_data["client"]
        phone = session_data["phone"]
        phone_code_hash = session_data["phone_code_hash"]
        if datetime.now() - session_data["created_at"] > timedelta(minutes=5):
            await update.message.reply_text("❌ Code expired. Send again.")
            await cleanup_user_session(user_id)
            return False
        session_data["attempts"] += 1
        result = await client.sign_in(phone, code, phone_code_hash)
        session_string = client.session.save()
        add_account(user_id, phone, session_string)
        await client.disconnect()
        await cleanup_user_session(user_id)
        await update.message.reply_text("✅ Account Added Successfully!")
        return True
    except SessionPasswordNeededError:
        await update.message.reply_text("🔒 2FA required. Send password:")
        user_sessions[user_id]["type"]="awaiting_password"
    except PhoneCodeInvalidError:
        await update.message.reply_text("❌ Invalid code. Try again.")
    except PhoneCodeExpiredError:
        await update_message.reply_text("❌ Code expired. Send again.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_2fa_password(user_id, password, update: Update):
    session_data = user_sessions.get(user_id)
    if not session_data: return
    client = session_data["client"]
    phone = session_data["phone"]
    try:
        result = await client.sign_in(password=password)
        session_string = client.session.save()
        add_account(user_id, phone, session_string)
        await client.disconnect()
        await cleanup_user_session(user_id)
        await update.message.reply_text("✅ 2FA completed, account added!")
    except Exception as e:
        await update.message.reply_text(f"❌ 2FA failed: {e}")

# ===== BROADCAST =====
async def get_groups_from_account(session_string):
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.start()
        groups=[]
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                entity=dialog.entity
                groups.append({"id":entity.id,"name":dialog.name,"username":getattr(entity,'username',None),"participants_count":getattr(entity,'participants_count',0)})
        await client.disconnect()
        return groups
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        return []

async def send_broadcast_to_groups(session_string, message, user_id):
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.start()
        groups_sent=0
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                try: 
                    await client.send_message(dialog.entity,message)
                    groups_sent+=1
                    await asyncio.sleep(1)
                except: continue
        await client.disconnect()
        if groups_sent>0: update_analytics(user_id,groups_sent,groups_sent)
        return groups_sent
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return 0

async def start_broadcast_task(user_id, interval, message, accounts):
    while user_id in broadcast_tasks and broadcast_tasks[user_id]['running']:
        for account in accounts:
            if not broadcast_tasks[user_id]['running']: break
            session_string=account[3]
            await send_broadcast_to_groups(session_string,message,user_id)
        await asyncio.sleep(interval)

# ===== DASHBOARD =====
async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id=update.effective_user.id
    create_user(user_id,update.effective_user.username,update.effective_user.first_name,update.effective_user.last_name)
    settings=get_user_settings(user_id)
    accounts_count=get_accounts_count(user_id)
    groups_count=get_groups_count(user_id)
    messages_sent,groups_reached=get_analytics(user_id)
    current_time=datetime.now().strftime("%I:%M %p")
    is_broadcasting=user_id in broadcast_tasks and broadcast_tasks[user_id]['running']
    dashboard_text=f"""
🤖 AFTAB PERSONAL AD BOT

👥 Accounts: {accounts_count} / 10  
📢 Message: {'Set ✓' if settings and settings[1] else 'Not Set'}  
⏰ Interval: {settings[2] if settings else 120}s  
📡 Status: {'Running 🔥' if is_broadcasting else 'Stopped 💤'}  
👥 Groups: {groups_count}

{current_time}
---
""".strip()
    keyboard=[
        [InlineKeyboardButton("👥 Add Account",callback_data="add_account"),InlineKeyboardButton("🌟 My Accounts",callback_data="my_accounts")],
        [InlineKeyboardButton("📢 Set Message",callback_data="set_ad_message"),InlineKeyboardButton("⏰ Set Interval",callback_data="set_interval")],
        [InlineKeyboardButton("🔄 Scan Groups",callback_data="scan_groups"),InlineKeyboardButton("👥 My Groups",callback_data="my_groups")],
        [InlineKeyboardButton("🚀 Start",callback_data="start_broadcast"),InlineKeyboardButton("🛑 Stop",callback_data="stop_broadcast")],
        [InlineKeyboardButton("📊 Analytics",callback_data="analytics")]
    ]
    await update.message.reply_text(dashboard_text,reply_markup=InlineKeyboardMarkup(keyboard))

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_dashboard(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id=update.effective_user.id
    text=update.message.text
    session_data=user_sessions.get(user_id)
    if session_data:
        if session_data["type"]=="awaiting_code":
            await verify_otp_code(user_id,text,update)
        elif session_data["type"]=="awaiting_password":
            await handle_2fa_password(user_id,text,update)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data=query.data
    user_id=query.from_user.id
    if data=="add_account":
        await query.message.reply_text("Send phone number with country code, e.g., +919876543210")
    elif data=="my_accounts":
        accounts=get_user_accounts(user_id)
        text="💼 Your Accounts:\n"+("\n".join([f"{i+1}. {a[2]}" for i,a in enumerate(accounts)]) if accounts else "None")
        await query.message.reply_text(text)
    elif data=="start_broadcast":
        settings=get_user_settings(user_id)
        accounts=get_user_accounts(user_id)
        if not accounts: await query.message.reply_text("❌ Add accounts first."); return
        message=settings[1] if settings else "Welcome!"
        interval=settings[2] if settings else 120
        broadcast_tasks[user_id]={"running":True}
        asyncio.create_task(start_broadcast_task(user_id,interval,message,accounts))
        await query.message.reply_text("✅ Broadcast started!")
    elif data=="stop_broadcast":
        if user_id in broadcast_tasks:
            broadcast_tasks[user_id]["running"]=False
            await query.message.reply_text("🛑 Broadcast stopped.")
    elif data=="analytics":
        messages_sent,groups_reached=get_analytics(user_id)
        await query.message.reply_text(f"📊 Analytics:\nMessages Sent: {messages_sent}\nGroups Reached: {groups_reached}")
    else:
        await query.message.reply_text("⚠️ Not implemented yet.")

# ===== MAIN =====
def main():
    init_database()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Bot starting...")
    application.run_polling()

if __name__=="__main__":
    main()
