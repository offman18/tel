import os
import sys

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Telethon is not installed! Installing it now...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "telethon"])
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession

print("==================================================")
print("Telegram Session String Generator (Telethon)")
print("==================================================")
print("You can get API ID and API HASH from: https://my.telegram.org")
print("==================================================")

api_id_input = input("Enter your API ID: ").strip()
if not api_id_input.isdigit():
    print("Error: API ID must be a number!")
    sys.exit(1)

api_id = int(api_id_input)
api_hash = input("Enter your API HASH: ").strip()

if not api_hash:
    print("Error: API HASH cannot be empty!")
    sys.exit(1)

print("\nStarting Telegram client... Please follow the prompts to log in.")
print("Note: If you have Two-Factor Authentication (2FA) enabled, you will be prompted for your password.")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    session_str = client.session.save()
    print("\n==================================================")
    print("SUCCESSFULLY LOGGED IN!")
    print("==================================================")
    print("Here is your TELEGRAM_SESSION string:\n")
    print(session_str)
    print("\n==================================================")
    print("IMPORTANT: Keep this session string secret! Anyone who has it can access your Telegram account.")
    print("Copy this string and use it for the TELEGRAM_SESSION secret in GitHub.")
    print("==================================================")
