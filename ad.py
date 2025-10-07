#!/usr/bin/env python3
"""
Ad Broadcasting Bot - Render Compatible Version
Phone Number + OTP Authentication
Python 3.12.1 Compatible
"""

import os
import json
import asyncio
import time
import sqlite3
import random
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
from flask import Flask, request

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

# ---------------- CONFIG ----------------
AD_BOT_TOKEN = "7398078402:AAGXTBxjuLt1q-4vhxKI0SbC3kmq2jQIFwY"

# Ad broadcasting settings
BROADCAST_INTERVAL = 120  # 120 seconds between cycles

# OTP settings
OTP_EXPIRY_MINUTES = 10
OTP_LENGTH = 6

# Database and storage paths
BASE_DIR = os.path.join(os.getcwd(), "ad_bot_data")
DB_PATH = os.path.join(BASE_DIR, "users.db")
ADS_DIR = os.path.join(BASE_DIR, "ads")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(ADS_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Ad Broadcasting Bot is running successfully on Render! 🚀"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def run_flask():
    """Run Flask server"""
    app.run(host="0.0.0.0", port=10000, debug=False, use_reloader=False)

# ---------------- DATABASE SETUP ----------------
def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table with phone authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            phone_number TEXT UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # OTP table for authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            otp_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_used BOOLEAN DEFAULT 0
        )
    ''')
    
    # Ads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ad_type TEXT,
            message_text TEXT,
            media_file TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_broadcasting BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Groups table - users manually add groups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id TEXT,
            group_title TEXT,
            is_active BOOLEAN DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_database()

# ---------------- DATABASE FUNCTIONS ----------------
def get_db_connection():
    return sqlite3.connect(DB_PATH)

def add_user(user_id: int, phone_number: str):
    """Add or update user in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, phone_number, last_login)
        VALUES (?, ?, ?)
    ''', (user_id, phone_number, datetime.now()))
    
    conn.commit()
    conn.close()

def get_user(user_id: int) -> Optional[dict]:
    """Get user from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'user_id': row[1],
            'phone_number': row[2],
            'is_active': bool(row[3]),
            'created_at': row[4],
            'last_login': row[5]
        }
    return None

# ---------------- OTP MANAGEMENT ----------------
def generate_otp() -> str:
    """Generate a random OTP code"""
    return ''.join([str(random.randint(0, 9)) for _ in range(OTP_LENGTH)])

def save_otp(phone_number: str, otp_code: str):
    """Save OTP to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clear old OTPs for this phone number
    cursor.execute('DELETE FROM otps WHERE phone_number = ?', (phone_number,))
    
    # Save new OTP
    cursor.execute('''
        INSERT INTO otps (phone_number, otp_code)
        VALUES (?, ?)
    ''', (phone_number, otp_code))
    
    conn.commit()
    conn.close()

def verify_otp(phone_number: str, otp_code: str) -> bool:
    """Verify OTP code"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM otps 
        WHERE phone_number = ? AND otp_code = ? AND is_used = 0
        AND created_at > datetime('now', ?)
    ''', (phone_number, otp_code, f'-{OTP_EXPIRY_MINUTES} minutes'))
    
    row = cursor.fetchone()
    
    if row:
        # Mark OTP as used
        cursor.execute('UPDATE otps SET is_used = 1 WHERE id = ?', (row[0],))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

# ---------------- AD MANAGEMENT ----------------
def save_ad(user_id: int, ad_type: str, message_text: str, media_file: str = None):
    """Save ad to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO ads (user_id, ad_type, message_text, media_file)
        VALUES (?, ?, ?, ?)
    ''', (user_id, ad_type, message_text, media_file))
    
    ad_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ad_id

def get_user_ads(user_id: int) -> List[dict]:
    """Get all ads for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM ads WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    
    ads = []
    for row in cursor.fetchall():
        ads.append({
            'id': row[0],
            'user_id': row[1],
            'ad_type': row[2],
            'message_text': row[3],
            'media_file': row[4],
            'is_active': bool(row[5]),
            'is_broadcasting': bool(row[6]),
            'created_at': row[7]
        })
    conn.close()
    return ads

def set_ad_broadcasting(ad_id: int, broadcasting: bool):
    """Set ad broadcasting status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE ads SET is_broadcasting = ? WHERE id = ?', (1 if broadcasting else 0, ad_id))
    conn.commit()
    conn.close()

# ---------------- GROUP MANAGEMENT ----------------
def save_group(user_id: int, group_id: str, group_title: str):
    """Save group to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if group exists
    cursor.execute('SELECT id FROM groups WHERE user_id = ? AND group_id = ?', (user_id, group_id))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO groups (user_id, group_id, group_title)
            VALUES (?, ?, ?)
        ''', (user_id, group_id, group_title))
    
    conn.commit()
    conn.close()

def get_user_groups(user_id: int) -> List[dict]:
    """Get all groups for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM groups WHERE user_id = ? AND is_active = 1', (user_id,))
    
    groups = []
    for row in cursor.fetchall():
        groups.append({
            'id': row[0],
            'user_id': row[1],
            'group_id': row[2],
            'group_title': row[3],
            'is_active': bool(row[4]),
            'added_at': row[5]
        })
    conn.close()
    return groups

# ---------------- AD BROADCASTING SYSTEM ----------------
class AdBroadcaster:
    def __init__(self):
        self.broadcasting_tasks = {}
    
    async def start_broadcasting(self, user_id: int, ad_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Start broadcasting ad to all groups"""
        try:
            user = get_user(user_id)
            if not user:
                await context.bot.send_message(user_id, "❌ User not found. Please login first.")
                return False
            
            ads = get_user_ads(user_id)
            ad = next((a for a in ads if a['id'] == ad_id), None)
            if not ad:
                await context.bot.send_message(user_id, "❌ Ad not found.")
                return False
            
            groups = get_user_groups(user_id)
            if not groups:
                await context.bot.send_message(user_id, "❌ No groups found. Please add groups first.")
                return False
            
            # Set ad as broadcasting
            set_ad_broadcasting(ad_id, True)
            
            # Start broadcasting task
            task = asyncio.create_task(self._broadcast_loop(user_id, ad_id, context))
            self.broadcasting_tasks[ad_id] = task
            
            await context.bot.send_message(
                user_id,
                f"🚀 Started broadcasting Ad #{ad_id} to {len(groups)} groups\n"
                f"📊 Interval: {BROADCAST_INTERVAL} seconds\n"
                f"🔄 Running infinite cycles..."
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting broadcast: {e}")
            await context.bot.send_message(user_id, f"❌ Error starting broadcast: {str(e)}")
            return False
    
    async def stop_broadcasting(self, user_id: int, ad_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Stop broadcasting ad"""
        try:
            if ad_id in self.broadcasting_tasks:
                self.broadcasting_tasks[ad_id].cancel()
                del self.broadcasting_tasks[ad_id]
            
            set_ad_broadcasting(ad_id, False)
            
            await context.bot.send_message(user_id, f"🛑 Stopped broadcasting Ad #{ad_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping broadcast: {e}")
            await context.bot.send_message(user_id, f"❌ Error stopping broadcast: {str(e)}")
            return False
    
    async def _broadcast_loop(self, user_id: int, ad_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Main broadcasting loop"""
        user = get_user(user_id)
        ads = get_user_ads(user_id)
        ad = next((a for a in ads if a['id'] == ad_id), None)
        
        if not user or not ad:
            return
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                groups = get_user_groups(user_id)
                
                await context.bot.send_message(
                    user_id,
                    f"🔄 Starting broadcast cycle #{cycle_count}\n"
                    f"📊 Sending to {len(groups)} groups\n"
                    f"⏰ Next cycle in {BROADCAST_INTERVAL} seconds"
                )
                
                # Send ad to all groups
                success_count = 0
                fail_count = 0
                
                for group in groups:
                    try:
                        await self._send_ad_to_group(context, ad, group)
                        success_count += 1
                        # Small delay between groups to avoid rate limits
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        fail_count += 1
                        logger.error(f"Error sending to group {group['group_id']}: {e}")
                
                # Send cycle report
                await context.bot.send_message(
                    user_id,
                    f"📊 Cycle #{cycle_count} Complete:\n"
                    f"✅ Success: {success_count}\n"
                    f"❌ Failed: {fail_count}\n"
                    f"⏳ Next cycle in {BROADCAST_INTERVAL} seconds"
                )
                
                # Wait for next cycle
                await asyncio.sleep(BROADCAST_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info(f"Broadcasting for ad #{ad_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Error in broadcast cycle: {e}")
                await asyncio.sleep(BROADCAST_INTERVAL)
    
    async def _send_ad_to_group(self, context: ContextTypes.DEFAULT_TYPE, ad: dict, group: dict):
        """Send ad to a specific group"""
        try:
            group_id = group['group_id']
            
            if ad['ad_type'] == 'text':
                await context.bot.send_message(
                    chat_id=group_id,
                    text=ad['message_text'],
                    parse_mode='HTML'
                )
            elif ad['ad_type'] == 'image' and ad['media_file']:
                file_path = os.path.join(ADS_DIR, ad['media_file'])
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as photo:
                        await context.bot.send_photo(
                            chat_id=group_id,
                            photo=photo,
                            caption=ad['message_text'],
                            parse_mode='HTML'
                        )
                else:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text=ad['message_text'],
                        parse_mode='HTML'
                    )
            elif ad['ad_type'] == 'video' and ad['media_file']:
                file_path = os.path.join(ADS_DIR, ad['media_file'])
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as video:
                        await context.bot.send_video(
                            chat_id=group_id,
                            video=video,
                            caption=ad['message_text'],
                            parse_mode='HTML'
                        )
                else:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text=ad['message_text'],
                        parse_mode='HTML'
                    )
            
            logger.info(f"Sent ad to group {group_id}")
            
        except Exception as e:
            logger.error(f"Failed to send ad to group {group['group_id']}: {e}")
            raise

# Initialize broadcaster
broadcaster = AdBroadcaster()

# ---------------- STATE MANAGEMENT ----------------
user_states = {}
ad_temp_data = {}
user_otp_data = {}

# ---------------- KEYBOARD GENERATORS ----------------
def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Login with Phone", callback_data="start_login")],
        [InlineKeyboardButton("📊 My Account", callback_data="account_info")],
        [InlineKeyboardButton("📢 Create Ad", callback_data="create_ad")],
        [InlineKeyboardButton("📋 My Ads", callback_data="my_ads")],
        [InlineKeyboardButton("👥 Manage Groups", callback_data="manage_groups")],
        [InlineKeyboardButton("🚀 Broadcast Control", callback_data="broadcast_control")]
    ])

def get_ad_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Text Ad", callback_data="ad_type_text")],
        [InlineKeyboardButton("🖼️ Image + Text", callback_data="ad_type_image")],
        [InlineKeyboardButton("🎥 Video + Text", callback_data="ad_type_video")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])

def get_ads_management_keyboard(ads: List[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    
    for ad in ads[:6]:
        broadcast_status = "🟢" if ad['is_broadcasting'] else "⚪"
        ad_type_icon = "📝" if ad['ad_type'] == 'text' else "🖼️" if ad['ad_type'] == 'image' else "🎥"
        keyboard.append([InlineKeyboardButton(
            f"{broadcast_status} {ad_type_icon} Ad #{ad['id']}", 
            callback_data=f"manage_ad_{ad['id']}"
        )])
    
    keyboard.extend([
        [InlineKeyboardButton("📢 Create New Ad", callback_data="create_ad")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_ad_management_keyboard(ad_id: int, is_broadcasting: bool) -> InlineKeyboardMarkup:
    if is_broadcasting:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Stop Broadcasting", callback_data=f"stop_broadcast_{ad_id}")],
            [InlineKeyboardButton("📋 Back to Ads", callback_data="my_ads")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Start Broadcasting", callback_data=f"start_broadcast_{ad_id}")],
            [InlineKeyboardButton("📋 Back to Ads", callback_data="my_ads")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])

def get_groups_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Group", callback_data="add_group")],
        [InlineKeyboardButton("📋 My Groups", callback_data="my_groups")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])

# ---------------- MESSAGE GENERATORS ----------------
async def get_main_menu_message(user_id: int) -> str:
    user = get_user(user_id)
    
    message = "🏠 **Ad Broadcasting Bot**\n\n"
    
    if user:
        message += f"✅ **Logged in as:** {user['phone_number']}\n"
        
        ads = get_user_ads(user_id)
        groups = get_user_groups(user_id)
        active_broadcasts = len([ad for ad in ads if ad['is_broadcasting']])
        
        message += f"📊 **Stats:** {len(ads)} ads, {len(groups)} groups, {active_broadcasts} active broadcasts\n\n"
    else:
        message += "❌ **Not logged in**\n\n"
    
    message += "**Features:**\n"
    message += "• 📱 Phone number login (No API required)\n"
    message += "• 📢 Create text/image/video ads\n"
    message += "• 👥 Add groups manually\n"
    message += "• 🚀 Broadcast to all groups\n"
    message += "• ⏰ 120-second intervals\n"
    message += "• 🔄 Infinite cycles\n\n"
    
    message += "Select an option:"
    
    return message

# ---------------- COMMAND HANDLERS ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    text = await get_main_menu_message(user_id)
    keyboard = get_main_menu_keyboard()
    
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **Ad Broadcasting Bot Help**

**Simple Login:**
1. 📱 Enter your phone number
2. 🔢 Receive OTP code
3. ✅ Enter OTP to verify
4. 🚀 Start broadcasting!

**Features:**
• Works in ALL countries
• No Telegram API required
• Simple phone verification
• Manual group management
• 120-second broadcast intervals
• Infinite cycles

**Commands:**
/start - Main menu
/help - This message
/cancel - Cancel current operation
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in user_states:
        del user_states[user_id]
    if user_id in ad_temp_data:
        del ad_temp_data[user_id]
    if user_id in user_otp_data:
        del user_otp_data[user_id]
    
    await update.message.reply_text("❌ Operation cancelled.")
    
    text = await get_main_menu_message(user_id)
    keyboard = get_main_menu_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ---------------- CALLBACK QUERY HANDLER ----------------
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    try:
        if data == "main_menu":
            await show_main_menu(query)
        elif data == "account_info":
            await show_account_info(query)
        elif data == "create_ad":
            await start_create_ad(query)
        elif data == "my_ads":
            await show_my_ads(query)
        elif data == "manage_groups":
            await show_manage_groups(query)
        elif data == "broadcast_control":
            await show_broadcast_control(query)
        elif data == "start_login":
            await start_login_process(query)
        
        # Ad creation
        elif data.startswith("ad_type_"):
            ad_type = data[8:]
            await handle_ad_type_selection(query, ad_type)
        elif data.startswith("manage_ad_"):
            ad_id = int(data[10:])
            await manage_ad(query, ad_id)
        elif data.startswith("start_broadcast_"):
            ad_id = int(data[16:])
            await start_broadcast_ad(query, ad_id, context)
        elif data.startswith("stop_broadcast_"):
            ad_id = int(data[15:])
            await stop_broadcast_ad(query, ad_id, context)
        
        # Group management
        elif data == "add_group":
            await start_add_group(query)
        elif data == "my_groups":
            await show_my_groups(query)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            await query.edit_message_text(f"❌ Error: {str(e)}")
        except Exception:
            pass

# ---------------- UI HANDLERS ----------------
async def show_main_menu(query):
    user_id = query.from_user.id
    text = await get_main_menu_message(user_id)
    keyboard = get_main_menu_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def show_account_info(query):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        text = "❌ You are not logged in. Please login first."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Login", callback_data="start_login")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return
    
    ads = get_user_ads(user_id)
    groups = get_user_groups(user_id)
    active_broadcasts = len([ad for ad in ads if ad['is_broadcasting']])
    
    message = "📊 **Account Information**\n\n"
    message += f"📱 **Phone:** {user['phone_number']}\n"
    message += f"🆔 **User ID:** {user['user_id']}\n"
    message += f"📅 **Registered:** {user['created_at'][:16]}\n"
    message += f"🔐 **Last Login:** {user['last_login'][:16] if user['last_login'] else 'N/A'}\n\n"
    
    message += "📈 **Statistics:**\n"
    message += f"• **Total Ads:** {len(ads)}\n"
    message += f"• **Active Broadcasts:** {active_broadcasts}\n"
    message += f"• **Groups:** {len(groups)}\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])
    
    await query.edit_message_text(message, reply_markup=keyboard, parse_mode="Markdown")

async def start_login_process(query):
    user_id = query.from_user.id
    user_states[user_id] = "waiting_phone"
    
    text = "📱 **Phone Login**\n\n"
    text += "Please send your phone number in international format:\n"
    text += "Example: `+1234567890` or `1234567890`\n\n"
    text += "We'll send you an OTP code to verify your number.\n\n"
    text += "Send /cancel to cancel login."
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
    ])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def start_create_ad(query):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        text = "❌ You need to login first to create ads."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Login", callback_data="start_login")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return
    
    text = "📢 **Create New Ad**\n\n"
    text += "Select the type of ad you want to create:\n\n"
    text += "• 📝 **Text Ad** - Simple text message\n"
    text += "• 🖼️ **Image Ad** - Image with caption\n"
    text += "• 🎥 **Video Ad** - Video with description\n"
    
    keyboard = get_ad_type_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def handle_ad_type_selection(query, ad_type: str):
    user_id = query.from_user.id
    user_states[user_id] = f"waiting_ad_{ad_type}"
    ad_temp_data[user_id] = {'type': ad_type}
    
    if ad_type == 'text':
        text = "📝 **Create Text Ad**\n\n"
        text += "Please send the text message for your ad.\n\n"
        text += "**Tips:**\n"
        text += "• Use HTML formatting: <b>bold</b>, <i>italic</i>\n"
        text += "• Keep it engaging and clear\n"
        text += "• Include a call-to-action\n\n"
        text += "Send /cancel to cancel ad creation."
    else:
        media_type = "image" if ad_type == 'image' else "video"
        text = f"🖼️ **Create {media_type.capitalize()} Ad**\n\n"
        text += f"Please send the {media_type} for your ad first.\n\n"
        text += "Send /cancel to cancel ad creation."
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="create_ad")]
    ])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def show_my_ads(query):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        text = "❌ You need to login first to view your ads."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Login", callback_data="start_login")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return
    
    ads = get_user_ads(user_id)
    
    if not ads:
        text = "📋 **My Ads**\n\n"
        text += "You haven't created any ads yet.\n\n"
        text += "Create your first ad to start broadcasting!"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Create Ad", callback_data="create_ad")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    else:
        active_count = len([ad for ad in ads if ad['is_broadcasting']])
        text = f"📋 **My Ads**\n\n"
        text += f"Found **{len(ads)}** ads ({active_count} active broadcasts)\n\n"
        text += "Click on an ad to manage broadcasting:"
        
        keyboard = get_ads_management_keyboard(ads)
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def manage_ad(query, ad_id: int):
    user_id = query.from_user.id
    ads = get_user_ads(user_id)
    ad = next((a for a in ads if a['id'] == ad_id), None)
    
    if not ad:
        await query.edit_message_text("❌ Ad not found.")
        return
    
    ad_type_icon = "📝" if ad['ad_type'] == 'text' else "🖼️" if ad['ad_type'] == 'image' else "🎥"
    broadcast_status = "🟢 BROADCASTING" if ad['is_broadcasting'] else "⚪ STOPPED"
    
    text = f"{ad_type_icon} **Ad Management**\n\n"
    text += f"**ID:** #{ad['id']}\n"
    text += f"**Type:** {ad['ad_type'].capitalize()}\n"
    text += f"**Status:** {broadcast_status}\n"
    text += f"**Created:** {ad['created_at'][:16]}\n\n"
    
    if ad['message_text']:
        message_preview = ad['message_text'][:100] + "..." if len(ad['message_text']) > 100 else ad['message_text']
        text += f"**Message Preview:**\n{message_preview}\n\n"
    
    if ad['is_broadcasting']:
        text += "🔄 This ad is currently being broadcast to all your groups every 120 seconds.\n\n"
        text += "Click below to stop broadcasting:"
    else:
        text += "⏸️ This ad is not currently broadcasting.\n\n"
        text += "Click below to start broadcasting to all your groups:"
    
    keyboard = get_ad_management_keyboard(ad_id, ad['is_broadcasting'])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def start_broadcast_ad(query, ad_id: int, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    success = await broadcaster.start_broadcasting(user_id, ad_id, context)
    if success:
        await manage_ad(query, ad_id)

async def stop_broadcast_ad(query, ad_id: int, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    success = await broadcaster.stop_broadcasting(user_id, ad_id, context)
    if success:
        await manage_ad(query, ad_id)

async def show_manage_groups(query):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        text = "❌ You need to login first to manage groups."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Login", callback_data="start_login")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return
    
    text = "👥 **Group Management**\n\n"
    text += "Here you can manage the groups where your ads will be broadcast.\n\n"
    text += "**Options:**\n"
    text += "• ➕ Add Group - Add a new group by ID\n"
    text += "• 📋 My Groups - View your current groups\n\n"
    text += "Your ads will be sent to all active groups."
    
    keyboard = get_groups_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def start_add_group(query):
    user_id = query.from_user.id
    user_states[user_id] = "waiting_group_id"
    
    text = "➕ **Add Group**\n\n"
    text += "Please send the group ID where you want to broadcast ads.\n\n"
    text += "**How to get Group ID:**\n"
    text += "1. Add this bot to your group\n"
    text += "2. Send any message in the group\n"
    text += "3. Forward that message to @userinfobot\n"
    text += "4. Copy the Chat ID (a negative number)\n\n"
    text += "Send the Group ID now:\n\n"
    text += "Send /cancel to cancel."
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="manage_groups")]
    ])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def show_my_groups(query):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        text = "❌ You need to login first to view groups."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Login", callback_data="start_login")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return
    
    groups = get_user_groups(user_id)
    
    if not groups:
        text = "👥 **My Groups**\n\n"
        text += "No groups found.\n\n"
        text += "Click below to add your first group:"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Group", callback_data="add_group")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    else:
        text = f"👥 **My Groups**\n\n"
        text += f"Found **{len(groups)}** groups\n\n"
        
        for i, group in enumerate(groups):
            text += f"{i+1}. {group['group_title']} (ID: {group['group_id']})\n"
        
        text += "\nThese groups will receive your broadcast ads."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add More Groups", callback_data="add_group")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def show_broadcast_control(query):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user:
        text = "❌ You need to login first."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Login", callback_data="start_login")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return
    
    active_ads = [ad for ad in get_user_ads(user_id) if ad['is_broadcasting']]
    groups = get_user_groups(user_id)
    
    text = "🚀 **Broadcast Control Center**\n\n"
    text += f"**Active Broadcasts:** {len(active_ads)}\n"
    text += f"**Target Groups:** {len(groups)}\n"
    text += f"**Broadcast Interval:** {BROADCAST_INTERVAL} seconds\n\n"
    
    if active_ads:
        text += "**Currently Broadcasting:**\n"
        for ad in active_ads[:3]:
            ad_type_icon = "📝" if ad['ad_type'] == 'text' else "🖼️" if ad['ad_type'] == 'image' else "🎥"
            text += f"• {ad_type_icon} Ad #{ad['id']}\n"
        
        if len(active_ads) > 3:
            text += f"• ... and {len(active_ads) - 3} more\n"
    else:
        text += "No active broadcasts running.\n"
    
    text += "\nManage your broadcasts from the ads menu:"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Manage Ads", callback_data="my_ads")],
        [InlineKeyboardButton("👥 Manage Groups", callback_data="manage_groups")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ---------------- MESSAGE HANDLERS ----------------
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    text_content = update.message.text

    if user_id in user_states and user_states[user_id].startswith("waiting_"):
        state = user_states[user_id]
        
        if state == "waiting_phone":
            # Validate phone number
            phone_number = text_content.strip()
            if not phone_number:
                await update.message.reply_text("❌ Please enter a valid phone number.")
                return
            
            # Generate OTP
            otp_code = generate_otp()
            save_otp(phone_number, otp_code)
            
            # Store phone number for verification
            user_otp_data[user_id] = {
                'phone': phone_number,
                'otp': otp_code
            }
            
            user_states[user_id] = "waiting_otp"
            
            await update.message.reply_text(
                f"📱 **OTP Sent**\n\n"
                f"Phone: `{phone_number}`\n"
                f"OTP Code: `{otp_code}`\n\n"
                f"**This is a demo - in real app, OTP would be sent via SMS**\n\n"
                f"Please enter the OTP code to verify:\n\n"
                f"Send /cancel to cancel."
            )
        
        elif state == "waiting_otp":
            if user_id not in user_otp_data:
                await update.message.reply_text("❌ OTP session expired. Please start over.")
                del user_states[user_id]
                return
            
            phone_data = user_otp_data[user_id]
            entered_otp = text_content.strip()
            
            # Verify OTP
            if verify_otp(phone_data['phone'], entered_otp):
                # OTP verified - create/update user
                add_user(user_id, phone_data['phone'])
                
                del user_states[user_id]
                del user_otp_data[user_id]
                
                await update.message.reply_text(
                    f"✅ **Login Successful!**\n\n"
                    f"Welcome! You are now logged in with:\n"
                    f"📱 Phone: `{phone_data['phone']}`\n\n"
                    f"You can now create ads and start broadcasting.",
                    parse_mode="Markdown"
                )
                
                text = await get_main_menu_message(user_id)
                keyboard = get_main_menu_keyboard()
                await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "❌ Invalid OTP code. Please try again or send /cancel to start over."
                )
        
        elif state == "waiting_group_id":
            group_id = text_content.strip()
            
            if not group_id:
                await update.message.reply_text("❌ Please enter a valid group ID.")
                return
            
            # Save group with a generic title
            save_group(user_id, group_id, f"Group {group_id}")
            
            del user_states[user_id]
            
            await update.message.reply_text(
                f"✅ **Group Added Successfully!**\n\n"
                f"Group ID: `{group_id}`\n\n"
                f"This group will now receive your broadcast ads.",
                parse_mode="Markdown"
            )
            
            await show_manage_groups_from_message(update)
        
        elif state == "waiting_ad_text":
            ad_id = save_ad(user_id, 'text', text_content)
            del user_states[user_id]
            
            await update.message.reply_text(
                f"✅ **Text Ad Created!**\n\n"
                f"**Ad ID:** #{ad_id}\n\n"
                f"You can now start broadcasting this ad to all your groups.",
                parse_mode="Markdown"
            )
            
            text = await get_main_menu_message(user_id)
            keyboard = get_main_menu_keyboard()
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    
    else:
        await update.message.reply_text(
            "Send /start to see the main menu or /help for assistance."
        )

async def show_manage_groups_from_message(update: Update):
    """Show groups menu from message handler"""
    user_id = update.effective_user.id
    groups = get_user_groups(user_id)
    
    if not groups:
        text = "👥 **My Groups**\n\nNo groups found."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Group", callback_data="add_group")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    else:
        text = f"👥 **My Groups**\n\nFound **{len(groups)}** groups"
        keyboard = get_groups_keyboard()
    
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if user_id not in user_states or not user_states[user_id].startswith("waiting_ad_"):
        return

    state = user_states[user_id]
    ad_type = state[11:]
    
    if ad_type not in ['image', 'video']:
        return

    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        file_ext = '.jpg'
    elif update.message.video:
        file = await update.message.video.get_file()
        file_ext = '.mp4'
    else:
        return

    timestamp = int(time.time())
    filename = f"ad_{user_id}_{timestamp}{file_ext}"
    file_path = os.path.join(ADS_DIR, filename)
    
    await file.download_to_drive(file_path)
    
    ad_temp_data[user_id] = {
        'type': ad_type,
        'media_file': filename,
        'file_path': file_path
    }
    user_states[user_id] = f"waiting_ad_{ad_type}_caption"
    
    await update.message.reply_text(
        f"✅ {ad_type.capitalize()} received!\n\n"
        f"Now please send the caption/text for your {ad_type} ad:\n\n"
        f"Send /cancel to cancel ad creation."
    )

async def handle_caption_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    caption = update.message.text

    if user_id not in user_states or not user_states[user_id].endswith("_caption"):
        return

    state = user_states[user_id]
    ad_type = state[11:-8]
    
    if user_id not in ad_temp_data:
        await update.message.reply_text("❌ Error: Media data lost. Please start over.")
        del user_states[user_id]
        return

    media_data = ad_temp_data[user_id]
    ad_id = save_ad(user_id, ad_type, caption, media_data['media_file'])
    
    del user_states[user_id]
    del ad_temp_data[user_id]
    
    await update.message.reply_text(
        f"✅ **{ad_type.capitalize()} Ad Created!**\n\n"
        f"**Ad ID:** #{ad_id}\n"
        f"**Type:** {ad_type.capitalize()}\n\n"
        f"You can now start broadcasting this ad to all your groups.",
        parse_mode="Markdown"
    )
    
    text = await get_main_menu_message(user_id)
    keyboard = get_main_menu_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ---------------- ERROR HANDLER ----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot"""
    try:
        if context.error:
            logger.error(f"Error: {context.error}", exc_info=True)
        else:
            logger.error("Unknown error occurred", exc_info=True)
            
        # Try to notify the user
        try:
            if update and hasattr(update, 'effective_message') and update.effective_message:
                await update.effective_message.reply_text("❌ An error occurred. Please try again.")
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
    except Exception as e:
        logger.error(f"Exception in error handler: {e}", exc_info=True)

# ---------------- BOT SETUP AND POLLING ----------------
async def run_bot():
    """Run the Telegram bot"""
    print("🤖 Starting Ad Broadcasting Bot...")
    print(f"📁 Data Directory: {BASE_DIR}")
    print(f"💾 Database: {DB_PATH}")
    print(f"⏰ Broadcast Interval: {BROADCAST_INTERVAL} seconds")
    print("🔐 Authentication: Phone Number + OTP (No API required)")
    print("🌍 Works in ALL countries")
    
    # Create application
    application = Application.builder().token(AD_BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Message handlers - order matters!
    application.add_handler(MessageHandler(filters.PHOTO, handle_media_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_media_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_caption_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    application.add_error_handler(error_handler)
    
    print("🚀 Bot is starting polling...")
    
    # Start polling with proper configuration for newer versions
    await application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

# ---------------- MAIN EXECUTION ----------------
def main():
    """Main function to run both Flask and bot"""
    print("🚀 Starting Ad Broadcasting Bot on Render...")
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask server started on port 10000")
    
    # Run bot in main thread
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
