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

If you encounter the `AttributeError: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'` error, this is typically caused by version incompatibilities with the python-telegram-bot library.

We've implemented several fixes:

1. **Library Version**: Downgraded to python-telegram-bot==20.3 for better stability
2. **Event Loop Handling**: Added proper event loop management for Render deployment
3. **Polling Configuration**: Added `close_loop=False` parameter to prevent event loop issues
4. **Error Handling**: Enhanced error handling with detailed logging
5. **Dependency Management**: Forced reinstallation of dependencies in start.sh
6. **Python Version**: Specified Python 3.11.9 for better compatibility

### Common deployment issues:

- **Make sure your Render environment uses Python 3.11.9**
- **Ensure requirements.txt specifies the correct library versions**
- **Check that the bot token is properly set in the AD_BOT_TOKEN variable**
- **Verify that all dependencies install correctly**

### If the issue persists:

1. Check the Render logs for specific error messages
2. Ensure you're using the exact versions specified in requirements.txt:
   - Flask==2.3.2
   - python-telegram-bot==20.3
   - httpx==0.25.2

3. Try running the version_check.py script to diagnose library issues:
   ```bash
   python version_check.py
   ```

4. You can also run the test_bot.py script to test basic bot functionality:
   ```bash
   python test_bot.py
   ```

### Additional debugging:

The application now includes enhanced logging to help diagnose issues:
- Version information is printed at startup
- Handler registration status is logged
- Detailed error messages are provided for common failure points

If you continue to experience issues, please check the Render logs for the complete error traceback and ensure all environment variables are properly configured.