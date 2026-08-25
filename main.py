import os
import sys
import re
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Load credentials from environment variables
api_id_env = os.environ.get("TELEGRAM_API_ID")
api_hash = os.environ.get("TELEGRAM_API_HASH")
session_str = os.environ.get("TELEGRAM_SESSION")

if not api_id_env or not api_hash or not session_str:
    print("Error: Missing environment variables.")
    sys.exit(1)

try:
    api_id = int(api_id_env)
except ValueError:
    print("Error: TELEGRAM_API_ID must be an integer!")
    sys.exit(1)

print("Initializing Telethon client with StringSession...")
client = TelegramClient(StringSession(session_str), api_id, api_hash)

me = None

async def init_bot():
    global me
    me = await client.get_me()
    print(f"==================================================")
    print(f"Logged in successfully as {me.first_name} (@{me.username or 'NoUsername'}) [ID: {me.id}]")
    print(f"==================================================")
    try:
        await client.send_message("me", f"🚀 **יוזרבוט חיפוש הסרטים הופעל בהצלחה ב-GitHub Actions!**\n\nמחובר כ: {me.first_name}")
    except Exception as e:
        print(f"Notice: Could not send Saved Messages notification: {e}")

@client.on(events.NewMessage(incoming=True))
async def handle_movie_request(event):
    global me
    if not me:
        return

    text = (event.raw_text or "").strip()
    if not text:
        return

    is_requested = False
    query = ""

    # Match mention: @username <query> or @username סרט <query>
    if me.username:
        mention_pattern = rf"@{me.username}\s+(?:סרט\s+)?(.+)"
        match = re.match(mention_pattern, text, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            is_requested = True

    # Match commands: .סרט <שם>, /סרט <שם>, סרט <שם>, .חפש <שם>, /חפש <שם>
    if not is_requested:
        for prefix in [".סרט ", "/סרט ", "סרט ", ".חפש ", "/חפש "]:
            if text.startswith(prefix):
                parts = text.split(" ", 1)
                if len(parts) > 1 and parts[1].strip():
                    query = parts[1].strip()
                    is_requested = True
                break

    if not is_requested or not query:
        return

    print(f"[REQUEST] Incoming search for '{query}' from user {event.sender_id} in chat {event.chat_id}")

    # Send temporary searching status message
    try:
        status_msg = await event.reply(f"🔎 מחפש את הסרט **'{query}'** בערוצים, אנא המתן...")
    except Exception as e:
        print(f"Could not send reply status: {e}")
        status_msg = None

    found_media = None

    try:
        # Search globally across all chats/channels the user is joined in
        async for msg in client.iter_messages(None, search=query, limit=100):
            if msg.media and (msg.video or msg.document):
                if msg.document:
                    mime = msg.document.mime_type or ""
                    size_mb = (msg.document.size or 0) / (1024 * 1024)
                    if 'video' in mime or mime == 'application/octet-stream' or size_mb > 5:
                        found_media = msg.media
                        break
                elif msg.video:
                    found_media = msg.media
                    break

        if found_media:
            caption = f"🎬 **הסרט שנמצא:** `{query}`\n\n🍿 צפייה מהנה!"
            # Direct media forwarding without download/upload and without 'Forwarded from'
            await client.send_file(
                event.chat_id,
                found_media,
                caption=caption,
                reply_to=event.id
            )
            if status_msg:
                await status_msg.delete()
            print(f"[SUCCESS] Sent movie '{query}' to chat {event.chat_id}")
        else:
            if status_msg:
                await status_msg.edit(f"❌ לא נמצא סרט התואם לחיפוש: **'{query}'**.\nבדוק את האיות או נסה שם אחר.")
            print(f"[NOT FOUND] Movie '{query}' was not found in any chat.")

    except Exception as e:
        print(f"[ERROR] Exception during search/send: {e}")
        if status_msg:
            try:
                await status_msg.edit("⚠️ אירעה שגיאה זמנית במהלך החיפוש.")
            except Exception:
                pass

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("FATAL: Session string is not authorized or expired! Please regenerate.")
        sys.exit(1)

    await init_bot()
    print("Userbot is actively listening for requests 24/7...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
