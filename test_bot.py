#!/usr/bin/env python3
"""
Simple test script to check if python-telegram-bot works
"""

import asyncio
from telegram.ext import Application

# Use a dummy token for testing
TOKEN = "1234567890:ABCDEF1234567890abcdef1234567890abcd"

async def test_bot():
    try:
        print("Testing bot creation...")
        application = Application.builder().token(TOKEN).build()
        print("Bot created successfully!")
        return True
    except Exception as e:
        print(f"Error creating bot: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_bot())