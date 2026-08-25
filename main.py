import os
import sys
import re
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

api_id_env = os.environ.get("TELEGRAM_API_ID")
api_hash = os.environ.get("TELEGRAM_API_HASH")
session_str = os.environ.get("TELEGRAM_SESSION")
target_group_secret = os.environ.get("TARGET_GROUP", "").strip()

if not api_id_env or not api_hash or not session_str:
    print("Error: Missing required environment credentials.")
    sys.exit(1)

try:
    api_id = int(api_id_env)
except ValueError:
    print("Error: TELEGRAM_API_ID must be an integer.")
    sys.exit(1)

client = TelegramClient(StringSession(session_str), api_id, api_hash)
me = None

async def init_bot():
    global me
    me = await client.get_me()
    print(f"==================================================")
    print(f"Userbot active as {me.first_name} [ID: {me.id}]")
    print(f"==================================================")
    try:
        await client.send_message("me", "🚀 **יוזרבוט חיפוש הסרטים פעיל במצב טקסט חופשי!**")
    except Exception:
        pass

@client.on(events.NewMessage())
async def handle_movie_request(event):
    global me
    if not me:
        return

    # Check if message is in the target group or in Saved Messages
    if target_group_secret:
        is_private_self = event.is_private and (event.chat_id == me.id)
        is_target_group = False
        try:
            if event.is_group or event.is_channel:
                chat = await event.get_chat()
                title = getattr(chat, "title", "") or ""
                if target_group_secret.lower() in title.lower():
                    is_target_group = True
        except Exception:
            pass

        if not is_private_self and not is_target_group:
            return

    raw_text = (event.raw_text or "").strip()
    if not raw_text:
        return

    # Don't respond to status messages sent by the bot itself that start with 🔎, 🎬, ❌, ⚠️, 🚀
    if event.sender_id == me.id and raw_text.startswith(("🔎", "🎬", "❌", "⚠️", "🚀")):
        return

    # Clean query from common prefixes if present, but accept pure movie name!
    cleaned = re.sub(r'^(?:(?:היי\s+)?ישראל\s*[:,-]?\s*|(?:[./]?(?:סרט|חפש|movie))\s*[:,-]?\s*|(?:תביא\s+(?:לי\s+)?(?:את\s+)?(?:ה)?סרט\s*)|(?:אפשר\s+(?:את\s+)?(?:ה)?סרט\s*))', '', raw_text, flags=re.IGNORECASE).strip()
    query = cleaned if cleaned else raw_text

    # Skip if query is too short or is a link/URL
    if len(query) < 2 or query.startswith("http://") or query.startswith("https://") or query.startswith("t.me/"):
        return

    # Send temporary status reply
    status_msg = None
    try:
        status_msg = await event.reply(f"🔎 מחפש את **'{query}'** בערוצים...")
    except Exception:
        pass

    found_media = None

    try:
        # Tier 1: Global Search across all joined chats/channels
        async for msg in client.iter_messages(None, search=query, limit=70):
            if msg.media and (msg.video or msg.document):
                if msg.document:
                    mime = msg.document.mime_type or ""
                    size_mb = (msg.document.size or 0) / (1024 * 1024)
                    if 'video' in mime or mime == 'application/octet-stream' or size_mb > 3:
                        found_media = msg.media
                        break
                elif msg.video:
                    found_media = msg.media
                    break

        # Tier 2: Deep Channel Search if not found in global search
        if not found_media:
            async for dialog in client.iter_dialogs(limit=50):
                if dialog.is_channel or dialog.is_group:
                    if dialog.id == event.chat_id:
                        continue
                    try:
                        async for ch_msg in client.iter_messages(dialog.id, search=query, limit=15):
                            if ch_msg.media and (ch_msg.video or ch_msg.document):
                                found_media = ch_msg.media
                                break
                    except Exception:
                        continue
                    if found_media:
                        break

        # Send media directly without forward tag
        if found_media:
            caption = f"🎬 **הסרט:** `{query}`\n\n🍿 צפייה מהנה!"
            await client.send_file(
                event.chat_id,
                found_media,
                caption=caption,
                reply_to=event.id
            )
            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
        else:
            if status_msg:
                await status_msg.edit(f"❌ לא נמצא סרט התואם לחיפוש: **'{query}'**.")

    except Exception:
        if status_msg:
            try:
                await status_msg.edit("⚠️ אירעה שגיאה זמנית במהלך החיפוש.")
            except Exception:
                pass

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("FATAL: Session string is not authorized.")
        sys.exit(1)

    await init_bot()
    print("Userbot is listening in free-text mode 24/7...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
