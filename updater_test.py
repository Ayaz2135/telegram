#!/usr/bin/env python3
"""
Test script to check Updater compatibility
"""

import asyncio
from telegram.ext import ApplicationBuilder

# Use a dummy token for testing
TOKEN = "1234567890:ABCDEF1234567890abcdef1234567890abcd"

async def test_application_creation():
    try:
        print("Testing Application creation...")
        # Test the exact method used in our main code
        application = ApplicationBuilder().token(TOKEN).build()
        print("Application created successfully!")
        print(f"Application type: {type(application)}")
        
        # Test if we can access updater
        print("Testing updater access...")
        updater = application.updater
        print(f"Updater type: {type(updater)}")
        print("Updater access successful!")
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_application_creation())