import logging
import sqlite3
import asyncio
import imghdr_py as imghdr
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError, FloodWaitError, PhoneCodeExpiredError
import re

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

# Global variables
user_sessions = {}
broadcast_tasks = {}

# ===== DATABASE FUNCTIONS =====
def init_database():
    """Initialize the SQLite database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone_number TEXT,
            session_string TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            ad_message TEXT DEFAULT 'Welcome to our service! 🚀',
            cycle_interval INTEGER DEFAULT 120,
            is_broadcasting BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Groups table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
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
        )
    ''')
    
    # Analytics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            analytic_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            messages_sent INTEGER DEFAULT 0,
            groups_reached INTEGER DEFAULT 0,
            date DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def get_user(user_id):
    """Get user from database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, last_name):
    """Create new user in database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    
    # Create default settings
    cursor.execute('''
        INSERT OR IGNORE INTO settings (user_id) VALUES (?)
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def get_user_settings(user_id):
    """Get user settings"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    conn.close()
    return settings

def update_ad_message(user_id, message):
    """Update ad message"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE settings SET ad_message = ? WHERE user_id = ?', (message, user_id))
    conn.commit()
    conn.close()

def update_interval(user_id, interval):
    """Update cycle interval"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE settings SET cycle_interval = ? WHERE user_id = ?', (interval, user_id))
    conn.commit()
    conn.close()

def update_broadcast_status(user_id, status):
    """Update broadcast status"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE settings SET is_broadcasting = ? WHERE user_id = ?', (status, user_id))
    conn.commit()
    conn.close()

def get_accounts_count(user_id):
    """Get number of accounts for user"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM accounts WHERE user_id = ? AND is_active = 1', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_accounts(user_id):
    """Get all accounts for user"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE user_id = ? AND is_active = 1', (user_id,))
    accounts = cursor.fetchall()
    conn.close()
    return accounts

def add_account(user_id, phone_number, session_string):
    """Add new account with session string"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO accounts (user_id, phone_number, session_string) 
        VALUES (?, ?, ?)
    ''', (user_id, phone_number, session_string))
    conn.commit()
    conn.close()

def get_groups_count(user_id):
    """Get number of groups for user"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM groups WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_groups(user_id):
    """Get all groups for user"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM groups WHERE user_id = ?', (user_id,))
    groups = cursor.fetchall()
    conn.close()
    return groups

def add_group(user_id, account_id, group_name, group_username, group_id_num, member_count):
    """Add group to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO groups (user_id, account_id, group_name, group_username, group_id_num, member_count)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, account_id, group_name, group_username, group_id_num, member_count))
    conn.commit()
    conn.close()

def get_analytics(user_id):
    """Get user analytics"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(messages_sent), SUM(groups_reached) 
        FROM analytics WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result or (0, 0)

def update_analytics(user_id, messages_sent, groups_reached):
    """Update analytics"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO analytics (user_id, messages_sent, groups_reached)
        VALUES (?, ?, ?)
    ''', (user_id, messages_sent, groups_reached))
    conn.commit()
    conn.close()

# ===== TELEGRAM CLIENT FUNCTIONS =====
async def create_telegram_client():
    """Create Telegram client with proper configuration"""
    return TelegramClient(
        StringSession(),
        API_ID,
        API_HASH,
        device_model="Samsung Galaxy S21",
        system_version="Android 12",
        app_version="8.7.2",
        lang_code="en",
        system_lang_code="en-US"
    )

async def send_otp_code(phone_number, user_id, update: Update):
    """Send OTP code request and handle verification"""
    try:
        # Clean up any existing session
        await cleanup_user_session(user_id)

        # Create new client instance
        client = await create_telegram_client()
        await client.connect()

        # Check if already authorized
        if await client.is_user_authorized():
            await update.message.reply_text(
                "❌ This phone number is already authorized in another session.\n\n"
                "Please use a different phone number."
            )
            await client.disconnect()
            return False

        # Send code request
        try:
            sent_code = await client.send_code_request(phone_number)
            logger.info(f"OTP sent to {phone_number}")
        except PhoneNumberInvalidError:
            await update.message.reply_text(
                "❌ Invalid phone number format.\n\n"
                "Please use format: +1234567890"
            )
            await client.disconnect()
            return False
        except FloodWaitError as e:
            wait_time = e.seconds
            await update.message.reply_text(
                f"❌ Too many attempts. Please wait {wait_time} seconds."
            )
            await client.disconnect()
            return False
        except Exception as e:
            error_msg = str(e)
            await update.message.reply_text(
                f"❌ Error: {error_msg}\n\n"
                "Please try again or contact admin."
            )
            await client.disconnect()
            return False

        # Store session data
        user_sessions[user_id] = {
            "type": "awaiting_code",
            "phone": phone_number,
            "client": client,
            "sent_code": sent_code,
            "attempts": 0,
            "created_at": datetime.now(),
            "phone_code_hash": sent_code.phone_code_hash
        }

        await update.message.reply_text(
            f"✅ Code sent to {phone_number}\n\n"
            f"📱 Enter the 5-digit code:\n\n"
            f"⏰ Code valid for 5 minutes\n"
            f"🔄 Send 'resend' for new code\n"
            f"❌ Send 'cancel' to stop\n\n"
            f"Example: 12345"
        )

        return True

    except Exception as e:
        logger.error(f"Error in send_otp_code: {e}")
        await update.message.reply_text(
            "❌ Connection error. Please try again."
        )
        return False

async def resend_otp_code(user_id, update: Update):
    """Resend OTP code with new client instance"""
    try:
        if user_id not in user_sessions:
            await update.message.reply_text("❌ Session expired. Start over with /start")
            return False

        session_data = user_sessions[user_id]
        phone = session_data["phone"]
        
        # Create completely new client for resend
        await cleanup_user_session(user_id)
        
        client = await create_telegram_client()
        await client.connect()

        # Resend code
        try:
            sent_code = await client.send_code_request(phone)
            logger.info(f"OTP resent to {phone}")
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error resending: {str(e)}"
            )
            await client.disconnect()
            return False

        # Update session data with new client
        user_sessions[user_id] = {
            "type": "awaiting_code",
            "phone": phone,
            "client": client,
            "sent_code": sent_code,
            "attempts": 0,
            "created_at": datetime.now(),
            "phone_code_hash": sent_code.phone_code_hash
        }

        await update.message.reply_text(
            f"✅ New code sent to {phone}\n\n"
            f"📱 Enter the new 5-digit code:\n\n"
            f"⏰ Code valid for 5 minutes\n"
            f"Example: 12345"
        )

        return True

    except Exception as e:
        logger.error(f"Error resending OTP: {e}")
        await update.message.reply_text(
            "❌ Error resending code. Start over with /start"
        )
        return False

async def verify_otp_code(user_id, code, update: Update):
    """Verify OTP code and create session"""
    try:
        if user_id not in user_sessions:
            await update.message.reply_text("❌ Session expired. Start over with /start")
            return False

        session_data = user_sessions[user_id]
        client = session_data["client"]
        phone = session_data["phone"]
        phone_code_hash = session_data["phone_code_hash"]

        # Check if code expired (5 minutes)
        if datetime.now() - session_data["created_at"] > timedelta(minutes=5):
            await update.message.reply_text(
                "❌ Code expired! Getting new code...\n\n"
                "Please wait..."
            )
            # Auto-resend instead of asking user
            success = await resend_otp_code(user_id, update)
            return False

        # Increment attempts
        user_sessions[user_id]["attempts"] += 1

        # Verify the code
        try:
            result = await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            # If we get here, login was successful
            session_string = client.session.save()
            add_account(user_id, phone, session_string)
            await client.disconnect()
            await cleanup_user_session(user_id)

            await update.message.reply_text(
                "🎉 Account Added Successfully!\n\n"
                "✅ Your account has been authenticated.\n"
                "📊 You can now scan groups and start broadcasting."
            )
            await show_dashboard(update, None)
            return True
            
        except SessionPasswordNeededError:
            await update.message.reply_text(
                "🔒 2-Step Verification enabled.\n\n"
                "Please enter your password:"
            )
            user_sessions[user_id]["type"] = "awaiting_password"
            return False
            
        except PhoneCodeInvalidError:
            remaining_attempts = 5 - session_data["attempts"]
            if remaining_attempts > 0:
                await update.message.reply_text(
                    f"❌ Invalid code. {remaining_attempts} attempts left.\n\n"
                    f"Please try again:"
                )
                return False
            else:
                await update.message.reply_text(
                    "❌ Too many failed attempts. Start over with /start"
                )
                await cleanup_user_session(user_id)
                return False
                
        except PhoneCodeExpiredError:
            await update.message.reply_text(
                "❌ Code expired! Getting new code...\n\n"
                "Please wait..."
            )
            # Auto-resend
            success = await resend_otp_code(user_id, update)
            return False
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'session' in error_msg and 'expired' in error_msg:
                await update.message.reply_text(
                    "🔄 Session expired. Getting new code...\n\n"
                    "Please wait..."
                )
                success = await resend_otp_code(user_id, update)
                return False
            else:
                await update.message.reply_text(
                    f"❌ Verification failed: {str(e)}\n\n"
                    "Please try 'resend' for a new code."
                )
                return False

    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        await update.message.reply_text(
            f"❌ Error: {str(e)}\n\n"
            "Please try 'resend' for a new code."
        )
        return False

async def handle_2fa_password(user_id, password, update: Update):
    """Handle 2FA password"""
    try:
        if user_id not in user_sessions:
            await update.message.reply_text("❌ Session expired. Start over.")
            return False

        session_data = user_sessions[user_id]
        client = session_data["client"]
        phone = session_data["phone"]

        result = await client.sign_in(password=password)
        
        session_string = client.session.save()
        add_account(user_id, phone, session_string)
        await client.disconnect()
        await cleanup_user_session(user_id)

        await update.message.reply_text(
            "🎉 Account Added Successfully!\n\n"
            "✅ 2-Step Verification completed.\n"
            "📊 You can now scan groups and start broadcasting."
        )
        await show_dashboard(update, None)
        return True

    except Exception as e:
        logger.error(f"Error handling 2FA: {e}")
        await update.message.reply_text(
            f"❌ 2FA failed: {str(e)}\n\n"
            "Please check password and try again."
        )
        return False

async def cleanup_user_session(user_id):
    """Clean up user session"""
    try:
        if user_id in user_sessions:
            session_data = user_sessions[user_id]
            if 'client' in session_data:
                try:
                    await session_data['client'].disconnect()
                except:
                    pass
            del user_sessions[user_id]
    except Exception as e:
        logger.error(f"Error cleaning up session: {e}")

async def get_groups_from_account(session_string):
    """Get all groups from an account"""
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.start()
        
        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                entity = dialog.entity
                groups.append({
                    'id': entity.id,
                    'name': dialog.name,
                    'username': getattr(entity, 'username', None),
                    'participants_count': getattr(entity, 'participants_count', 0)
                })
        
        await client.disconnect()
        return groups
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        return []

async def send_broadcast_to_groups(session_string, message, user_id):
    """Send broadcast message to all groups"""
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.start()
        
        groups_sent = 0
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                try:
                    await client.send_message(dialog.entity, message)
                    groups_sent += 1
                    await asyncio.sleep(1)  # Reduced delay
                except Exception as e:
                    continue
        
        await client.disconnect()
        
        if groups_sent > 0:
            update_analytics(user_id, groups_sent, groups_sent)
        
        return groups_sent
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
        return 0

# ===== BROADCAST TASK =====
async def start_broadcast_task(user_id, interval, message, accounts):
    """Start broadcasting task"""
    while user_id in broadcast_tasks and broadcast_tasks[user_id]['running']:
        try:
            total_groups_sent = 0
            for account in accounts:
                if not broadcast_tasks[user_id]['running']:
                    break
                    
                session_string = account[3]
                groups_sent = await send_broadcast_to_groups(session_string, message, user_id)
                total_groups_sent += groups_sent
            
            await asyncio.sleep(interval)
            
        except Exception as e:
            logger.error(f"Error in broadcast task: {e}")
            await asyncio.sleep(30)

# ===== DASHBOARD FUNCTIONS =====
async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main dashboard"""
    user_id = update.effective_user.id
    create_user(user_id, update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
    
    settings = get_user_settings(user_id)
    accounts_count = get_accounts_count(user_id)
    groups_count = get_groups_count(user_id)
    messages_sent, groups_reached = get_analytics(user_id)
    
    current_time = datetime.now().strftime("%I:%M %p")
    
    is_broadcasting = user_id in broadcast_tasks and broadcast_tasks[user_id]['running']
    has_message = settings and settings[1] and len(settings[1]) > 5
    
    dashboard_text = f"""
🤖 AFTAB PERSONAL AD BOT

👥 Accounts: {accounts_count} / 10  
📢 Message: {'Set ✓' if has_message else 'Not Set'}  
⏰ Interval: {settings[2] if settings else 120}s  
📡 Status: {'Running 🔥' if is_broadcasting else 'Stopped 💤'}  
👥 Groups: {groups_count}

{current_time}
---
    """.strip()
    
    keyboard = [
        [InlineKeyboardButton("👥 Add Account", callback_data="add_account"),
         InlineKeyboardButton("🌟 My Accounts", callback_data="my_accounts")],
        [InlineKeyboardButton("📢 Set Message", callback_data="set_ad_message"),
         InlineKeyboardButton("⏰ Set Interval", callback_data="set_interval")],
        [InlineKeyboardButton("🔄 Scan Groups", callback_data="scan_groups"),
         InlineKeyboardButton("👥 My Groups", callback_data="my_groups")],
        [InlineKeyboardButton("🚀 Start", callback_data="start_broadcast"),
         InlineKeyboardButton("💤 Stop", callback_data="stop_broadcast")],
        [InlineKeyboardButton("📊 Analytics", callback_data="analytics"),
         InlineKeyboardButton("📞 Contact", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(dashboard_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(dashboard_text, reply_markup=reply_markup)

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text(
        "🤖 Welcome to AFTAB PERSONAL AD BOT!\n\n"
        "✅ Fixed OTP issues\n"
        "✅ Auto code resend\n"
        "✅ Better IP handling\n\n"
        "📞 Support: @azttech"
    )
    await show_dashboard(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "refresh":
        await show_dashboard(update, context)
    
    elif data == "add_account":
        accounts_count = get_accounts_count(user_id)
        if accounts_count >= 10:
            await query.edit_message_text(
                "❌ Max 10 accounts reached!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
            )
            return
            
        await query.edit_message_text(
            "👥 Add Account\n\n"
            "📱 Send phone number:\n\n"
            "Format: +1234567890\n\n"
            "💡 Use active accounts for best results"
        )
        user_sessions[user_id] = "awaiting_phone"
    
    elif data == "my_accounts":
        accounts = get_user_accounts(user_id)
        if accounts:
            accounts_text = "🌟 My Accounts\n\n"
            for account in accounts:
                accounts_text += f"📱 {account[2]}\n"
            accounts_text += f"\nTotal: {len(accounts)}/10"
        else:
            accounts_text = "❌ No accounts yet"
        
        await query.edit_message_text(
            accounts_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
        )
    
    elif data == "set_ad_message":
        settings = get_user_settings(user_id)
        current_message = settings[1] if settings else "Not set"
        await query.edit_message_text(
            f"📢 Current: {current_message}\n\n"
            f"Send new message:"
        )
        user_sessions[user_id] = "awaiting_message"
    
    elif data == "set_interval":
        await query.edit_message_text(
            "⏰ Set Interval:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("1 min", callback_data="interval_60"),
                 InlineKeyboardButton("2 min", callback_data="interval_120")],
                [InlineKeyboardButton("5 min", callback_data="interval_300"),
                 InlineKeyboardButton("10 min", callback_data="interval_600")],
                [InlineKeyboardButton("🔙 Back", callback_data="refresh")]
            ])
        )
    
    elif data == "scan_groups":
        accounts = get_user_accounts(user_id)
        if not accounts:
            await query.edit_message_text("❌ No accounts found!")
            return
        
        await query.edit_message_text("🔄 Scanning groups...")
        
        total_groups = 0
        for account in accounts:
            groups = await get_groups_from_account(account[3])
            for group in groups:
                add_group(user_id, account[0], group['name'], group['username'], group['id'], group['participants_count'])
            total_groups += len(groups)
        
        await query.edit_message_text(
            f"✅ Found {total_groups} groups",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
        )
    
    elif data == "my_groups":
        groups = get_user_groups(user_id)
        if groups:
            groups_text = "👥 My Groups\n\n"
            for group in groups[:5]:
                group_name = group[3] or "No Name"
                members = group[6] or 0
                groups_text += f"• {group_name} ({members})\n"
            groups_text += f"\nTotal: {len(groups)} groups"
        else:
            groups_text = "❌ No groups found"
        
        await query.edit_message_text(
            groups_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
        )
    
    elif data == "start_broadcast":
        accounts = get_user_accounts(user_id)
        settings = get_user_settings(user_id)
        
        if not accounts:
            await query.edit_message_text("❌ No accounts found!")
            return
        
        if not settings or not settings[1]:
            await query.edit_message_text("❌ No message set!")
            return
        
        if user_id not in broadcast_tasks:
            broadcast_tasks[user_id] = {
                'running': True,
                'task': asyncio.create_task(
                    start_broadcast_task(user_id, settings[2], settings[1], accounts)
                )
            }
        
        update_broadcast_status(user_id, 1)
        
        await query.edit_message_text(
            f"🚀 Started!\n\n"
            f"Accounts: {len(accounts)}\n"
            f"Interval: {settings[2]}s",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
        )
    
    elif data == "stop_broadcast":
        if user_id in broadcast_tasks:
            broadcast_tasks[user_id]['running'] = False
            del broadcast_tasks[user_id]
        
        update_broadcast_status(user_id, 0)
        
        await query.edit_message_text(
            "💤 Stopped!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
        )
    
    elif data == "analytics":
        messages_sent, groups_reached = get_analytics(user_id)
        success_rate = ((groups_reached/messages_sent)*100) if messages_sent > 0 else 0
        
        await query.edit_message_text(
            f"📊 Analytics\n\n"
            f"Messages: {messages_sent}\n"
            f"Groups: {groups_reached}\n"
            f"Success: {success_rate:.1f}%",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
        )
    
    elif data.startswith("interval_"):
        interval = int(data.split("_")[1])
        update_interval(user_id, interval)
        await query.edit_message_text(
            f"✅ Interval: {interval}s",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="refresh")]])
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages"""
    user_id = update.effective_user.id
    message_text = update.message.text.strip() if update.message.text else ""
    
    if user_id in user_sessions:
        session_type = user_sessions[user_id]
        
        if session_type == "awaiting_message":
            update_ad_message(user_id, message_text)
            await update.message.reply_text("✅ Message saved!")
            del user_sessions[user_id]
            await show_dashboard(update, context)
        
        elif session_type == "awaiting_phone":
            if message_text.lower() == 'cancel':
                await cleanup_user_session(user_id)
                await update.message.reply_text("❌ Cancelled.")
                await show_dashboard(update, context)
                return
                
            if re.match(r'^\+\d{10,15}$', message_text):
                if get_accounts_count(user_id) < 10:
                    await send_otp_code(message_text, user_id, update)
                else:
                    await update.message.reply_text("❌ Account limit reached!")
                    await show_dashboard(update, context)
            else:
                await update.message.reply_text("❌ Use format: +1234567890")
        
        elif isinstance(session_type, dict) and session_type.get("type") == "awaiting_code":
            if message_text.lower() == 'cancel':
                await cleanup_user_session(user_id)
                await update.message.reply_text("❌ Cancelled.")
                await show_dashboard(update, context)
                return
                
            if message_text.lower() == 'resend':
                await update.message.reply_text("🔄 Getting new code...")
                await resend_otp_code(user_id, update)
                return
                
            if re.match(r'^\d{5,6}$', message_text):  # Allow 5-6 digit codes
                await verify_otp_code(user_id, message_text, update)
            else:
                await update.message.reply_text("❌ Enter 5-digit code or 'resend'")
        
        elif isinstance(session_type, dict) and session_type.get("type") == "awaiting_password":
            if message_text.lower() == 'cancel':
                await cleanup_user_session(user_id)
                await update.message.reply_text("❌ Cancelled.")
                await show_dashboard(update, context)
                return
                
            await handle_2fa_password(user_id, message_text, update)
    
    else:
        await show_dashboard(update, context)

# ===== MAIN FUNCTION =====
def main():
    """Start the bot"""
    # Initialize database
    init_database()
    
    try:
        # Create application with error handling
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🤖 AFTAB BOT - COMPATIBLE VERSION")
        print("✅ Fixed version compatibility")
        print("✅ Working with latest python-telegram-bot")
        print("✅ Ready for Render deployment")
        print("🚀 Starting bot...")
        
        # Start polling
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            timeout=30,
            pool_timeout=30
        )
        
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        print("Please check your BOT_TOKEN and try again.")

if __name__ == "__main__":
    main()
