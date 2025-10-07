# Ad Broadcasting Bot

A Telegram bot for broadcasting ads to groups with phone number authentication.

## Features

- Phone number + OTP authentication (no API required)
- Works in ALL countries
- Create text, image, and video ads
- Manual group management
- 120-second broadcast intervals
- Infinite broadcasting cycles

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your bot token in the `ad.py` file:
   ```python
   AD_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
   ```

3. Run the bot:
   ```bash
   python ad.py
   ```

## Deployment on Render

The bot is configured to work on Render with the provided `start.sh` script.

## Usage

1. Start the bot with `/start`
2. Login with your phone number
3. Create ads using the menu options
4. Add groups manually
5. Start broadcasting to all groups

## Troubleshooting

If you encounter the `AttributeError: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'` error, make sure you're using python-telegram-bot version 20.7 or compatible.
