import os
import sys
import re
import asyncio
import traceback
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
        await client.send_message("me", "🚀 **יוזרבוט הסרטים פעיל ומוכן לקבל בקשות!**")
    except Exception:
        pass

@client.on(events.NewMessage())
async def handle_movie_request(event):
    global me
    if not me:
        return

    # Check if message is in target group or in Saved Messages
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

    # Don't respond to status messages sent by the bot
    if event.sender_id == me.id and raw_text.startswith(("🔎", "🎬", "❌", "⚠️", "🚀")):
        return

    # Clean query from common prefixes if present, but accept pure movie name!
    cleaned = re.sub(r'^(?:(?:היי\s+)?ישראל\s*[:,-]?\s*|(?:[./]?(?:סרט|חפש|movie))\s*[:,-]?\s*|(?:תביא\s+(?:לי\s+)?(?:את\s+)?(?:ה)?סרט\s*)|(?:אפשר\s+(?:את\s+)?(?:ה)?סרט\s*))', '', raw_text, flags=re.IGNORECASE).strip()
    query = cleaned if cleaned else raw_text

    # Skip if query is too short or is a link/URL
    if len(query) < 2 or query.startswith("http://") or query.startswith("https://") or query.startswith("t.me/"):
        return

    print(f"[REQUEST] Searching movie for query: '{query}'")

    # Send temporary status reply: "מכין לך את הסרט..."
    status_msg = None
    try:
        status_msg = await event.reply("🔎 מכין לך את הסרט...")
    except Exception as e:
        print(f"Could not send reply status: {e}")

    found_msg = None

    try:
        # Tier 1: Global Search across all joined chats/channels
        async for msg in client.iter_messages(None, search=query, limit=70):
            if msg.media and (msg.video or msg.document):
                if msg.document:
                    mime = msg.document.mime_type or ""
                    size_mb = (msg.document.size or 0) / (1024 * 1024)
                    if 'video' in mime or mime == 'application/octet-stream' or size_mb > 3:
                        found_msg = msg
                        break
                elif msg.video:
                    found_msg = msg
                    break

        # Tier 2: Deep Channel Search if not found in global search
        if not found_msg:
            async for dialog in client.iter_dialogs(limit=50):
                if dialog.is_channel or dialog.is_group:
                    if dialog.id == event.chat_id:
                        continue
                    try:
                        async for ch_msg in client.iter_messages(dialog.id, search=query, limit=15):
                            if ch_msg.media and (ch_msg.video or ch_msg.document):
                                found_msg = ch_msg
                                break
                    except Exception:
                        continue
                    if found_msg:
                        break

        # Send media directly without forward tag
        if found_msg:
            caption = f"🎬 **הסרט:** `{query}`\n\n🍿 צפייה מהנה!"
            
            # Try sending via media reference
            sent = False
            try:
                await client.send_file(
                    event.chat_id,
                    found_msg.media,
                    caption=caption,
                    reply_to=event.id
                )
                sent = True
            except Exception as send_err:
                print(f"send_file failed with media: {send_err}, trying msg directly...")
                try:
                    await client.send_file(
                        event.chat_id,
                        found_msg,
                        caption=caption,
                        reply_to=event.id
                    )
                    sent = True
                except Exception as send_err2:
                    print(f"send_file with msg failed: {send_err2}")

            if sent and status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            elif not sent and status_msg:
                await status_msg.edit(f"⚠️ לא ניתן להעביר את הסרט (ייתכן שהערוץ חסום להעברה).")
        else:
            if status_msg:
                await status_msg.edit(f"❌ לא נמצא סרט התואם לחיפוש: **'{query}'**.")

    except Exception as e:
        traceback.print_exc()
        if status_msg:
            try:
                await status_msg.edit(f"❌ לא נמצא סרט התואם לחיפוש: **'{query}'**.")
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
