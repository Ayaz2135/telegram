#!/usr/bin/env python3
"""
Script to check library versions
"""

import telegram
import sys

print(f"Python version: {sys.version}")
print(f"Python Telegram Bot version: {telegram.__version__}")

# Try to import Updater
try:
    from telegram.ext import Updater
    print("Updater import successful")
    
    # Try to create an updater instance
    updater = Updater(bot=None, update_queue=None)
    print("Updater creation successful")
except Exception as e:
    print(f"Error with Updater: {e}")

# Try to import Application
try:
    from telegram.ext import Application
    print("Application import successful")
except Exception as e:
    print(f"Error with Application: {e}")