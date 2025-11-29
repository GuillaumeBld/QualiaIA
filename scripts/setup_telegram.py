#!/usr/bin/env python3
"""
QualiaIA Telegram Bot Setup Helper

Guides you through setting up a Telegram bot for QualiaIA.

Usage:
    python scripts/setup_telegram.py
"""

import sys

def main():
    print("=" * 60)
    print("QualiaIA Telegram Bot Setup")
    print("=" * 60)
    print()
    
    print("📱 STEP 1: Create a Telegram Bot")
    print("-" * 40)
    print("1. Open Telegram and search for @BotFather")
    print("2. Send /newbot")
    print("3. Choose a name (e.g., 'QualiaIA Controller')")
    print("4. Choose a username (must end in 'bot', e.g., 'qualiaIA_bot')")
    print("5. Copy the bot token")
    print()
    
    bot_token = input("Enter your bot token: ").strip()
    
    if not bot_token or ":" not in bot_token:
        print("\n❌ Invalid token format. Should look like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        sys.exit(1)
    
    print()
    print("📱 STEP 2: Get Your User ID")
    print("-" * 40)
    print("1. Open Telegram and search for @userinfobot")
    print("2. Send any message")
    print("3. It will reply with your user ID")
    print()
    
    user_ids = input("Enter your user ID(s) (comma-separated for multiple): ").strip()
    
    if not user_ids:
        print("\n❌ User ID required")
        sys.exit(1)
    
    # Validate user IDs
    try:
        ids = [int(x.strip()) for x in user_ids.split(",")]
    except ValueError:
        print("\n❌ Invalid user ID format. Should be numbers.")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("✅ CONFIGURATION COMPLETE")
    print("=" * 60)
    print()
    print("Add these to your .env file:")
    print()
    print(f"TELEGRAM_BOT_TOKEN={bot_token}")
    print(f"TELEGRAM_AUTHORIZED_USER_IDS={','.join(str(i) for i in ids)}")
    print()
    print("-" * 40)
    print("Or add to config/config.yaml:")
    print()
    print("communication:")
    print("  telegram:")
    print(f'    bot_token: "{bot_token}"')
    print(f'    authorized_user_ids: [{", ".join(str(i) for i in ids)}]')
    print()
    print("=" * 60)
    print()
    print("🎉 Your Telegram bot is ready!")
    print()
    print("Test it by:")
    print("1. Open Telegram and search for your bot")
    print("2. Send /start")
    print("3. Run QualiaIA: python -m src.main")
    print()


if __name__ == "__main__":
    main()
