import os
import sys
import re
import asyncio
import time
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

# Async Task Queue for handling many users simultaneously
request_queue = asyncio.Queue()

# Pending user selections: (chat_id, user_id) -> {'results': [msg1, msg2, ...], 'time': float}
pending_selections = {}

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

def get_file_name_and_size(msg):
    """Extract clean title and formatted size from a message's media."""
    size_str = ""
    name_str = ""
    
    if msg.document:
        size_bytes = msg.document.size or 0
        if size_bytes > 1024 * 1024 * 1024:
            size_str = f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.0f} MB"
            
        for attr in getattr(msg.document, 'attributes', []):
            if hasattr(attr, 'file_name') and attr.file_name:
                name_str = attr.file_name
                break

    if not name_str and msg.message:
        # First line of caption
        name_str = msg.message.split('\n')[0].strip()

    if not name_str:
        name_str = "קובץ וידאו"

    # Clean name extension
    name_str = re.sub(r'\.(mp4|mkv|avi|mov|wmv)$', '', name_str, flags=re.IGNORECASE)
    return name_str[:45], size_str

async def init_bot():
    global me
    me = await client.get_me()
    print(f"==================================================")
    print(f"Userbot active as {me.first_name} [ID: {me.id}]")
    print(f"Target Group Filter: {'CONFIGURED' if target_group_secret else 'NONE'}")
    print(f"==================================================")

async def is_valid_target_group(event):
    """Strictly verify that the event is ONLY from the configured secret target group."""
    if not target_group_secret:
        return True
    
    if not (event.is_group or event.is_channel):
        return False
        
    try:
        chat = await event.get_chat()
        title = getattr(chat, "title", "") or ""
        return target_group_secret.lower() in title.lower()
    except Exception:
        return False

async def process_movie_search(event, query):
    """Search for movies with multi-result selection and instant sending."""
    status_msg = None
    try:
        status_msg = await event.reply("🔎 מכין לך את הסרט...")
    except Exception as e:
        print(f"Could not send reply status: {e}")

    found_messages = []
    seen_ids = set()

    try:
        # Tier 1: Fast Global Search (Collect up to 6 unique results)
        async for msg in client.iter_messages(None, search=query, limit=80):
            if msg.media and (msg.video or msg.document):
                if msg.id not in seen_ids:
                    if msg.document:
                        mime = msg.document.mime_type or ""
                        size_mb = (msg.document.size or 0) / (1024 * 1024)
                        if 'video' in mime or mime == 'application/octet-stream' or size_mb > 3:
                            found_messages.append(msg)
                            seen_ids.add(msg.id)
                    elif msg.video:
                        found_messages.append(msg)
                        seen_ids.add(msg.id)
                        
            if len(found_messages) >= 6:
                break

        # Tier 2: Deep Channel Search if few or no results found
        if len(found_messages) < 2:
            async for dialog in client.iter_dialogs(limit=40):
                if dialog.is_channel or dialog.is_group:
                    if dialog.id == event.chat_id:
                        continue
                    try:
                        async for ch_msg in client.iter_messages(dialog.id, search=query, limit=10):
                            if ch_msg.media and (ch_msg.video or ch_msg.document) and ch_msg.id not in seen_ids:
                                found_messages.append(ch_msg)
                                seen_ids.add(ch_msg.id)
                                if len(found_messages) >= 6:
                                    break
                    except Exception:
                        continue
                    if len(found_messages) >= 6:
                        break

        # Case 1: Exactly 1 result -> Send immediately!
        if len(found_messages) == 1:
            chosen = found_messages[0]
            name, size = get_file_name_and_size(chosen)
            caption = f"🎬 **הסרט:** `{query}`\n📦 **גודל:** `{size}`\n\n🍿 צפייה מהנה!"
            
            await client.send_file(
                event.chat_id,
                chosen.media,
                caption=caption,
                reply_to=event.id
            )
            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass

        # Case 2: Multiple results (2-6) -> Present interactive numbered list!
        elif len(found_messages) > 1:
            user_key = (event.chat_id, event.sender_id)
            pending_selections[user_key] = {
                'results': found_messages,
                'time': time.time(),
                'query': query
            }

            options_text = [f"🍿 **נמצאו {len(found_messages)} תוצאות עבור '{query}':**\n"]
            for idx, msg in enumerate(found_messages):
                name, size = get_file_name_and_size(msg)
                emoji = NUMBER_EMOJIS[idx] if idx < len(NUMBER_EMOJIS) else f"{idx+1}."
                size_info = f" `[{size}]`" if size else ""
                options_text.append(f"{emoji} **{name}**{size_info}")

            options_text.append("\n👇 **השב להודעה זו עם המספר המבוקש (1-{})**".format(len(found_messages)))
            
            menu_text = "\n".join(options_text)
            if status_msg:
                await status_msg.edit(menu_text)
            else:
                await event.reply(menu_text)

        # Case 3: No results found
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

async def queue_worker():
    """Background worker pool handling high traffic smoothly."""
    while True:
        try:
            event, query = await request_queue.get()
            await process_movie_search(event, query)
        except Exception as e:
            print(f"Queue Worker Exception: {e}")
        finally:
            request_queue.task_done()

@client.on(events.NewMessage())
async def message_handler(event):
    global me
    if not me:
        return

    # 1. STRICT GROUP CHECK: ONLY the configured group
    if not await is_valid_target_group(event):
        return

    raw_text = (event.raw_text or "").strip()
    if not raw_text:
        return

    # Ignore bot's own internal status messages
    if event.sender_id == me.id and raw_text.startswith(("🔎", "🎬", "❌", "⚠️", "🚀", "🍿")):
        return

    user_key = (event.chat_id, event.sender_id)

    # 2. Check if user is responding to a multi-result selection (e.g. typing '1', '2', '3')
    if user_key in pending_selections:
        selection_data = pending_selections[user_key]
        # Expire selections older than 5 minutes
        if time.time() - selection_data['time'] < 300:
            match_num = re.match(r'^([1-8])(?:\.|\)|-)?$', raw_text)
            if match_num:
                choice_idx = int(match_num.group(1)) - 1
                results = selection_data['results']
                if 0 <= choice_idx < len(results):
                    chosen_msg = results[choice_idx]
                    query = selection_data['query']
                    name, size = get_file_name_and_size(chosen_msg)
                    caption = f"🎬 **הסרט:** `{name}`\n📦 **גודל:** `{size}`\n\n🍿 צפייה מהנה!"
                    
                    # Remove from pending store
                    del pending_selections[user_key]

                    loading_msg = await event.reply("🚀 שולח לך את הסרט שנבחר...")
                    try:
                        await client.send_file(
                            event.chat_id,
                            chosen_msg.media,
                            caption=caption,
                            reply_to=event.id
                        )
                        await loading_msg.delete()
                    except Exception as e:
                        print(f"Error sending selected file: {e}")
                        await loading_msg.edit("⚠️ שגיאה בשליחת הקובץ שנבחר.")
                    return
        else:
            del pending_selections[user_key]

    # 3. Process new search request
    cleaned = re.sub(r'^(?:(?:היי\s+)?ישראל\s*[:,-]?\s*|(?:[./]?(?:סרט|חפש|movie))\s*[:,-]?\s*|(?:תביא\s+(?:לי\s+)?(?:את\s+)?(?:ה)?סרט\s*)|(?:אפשר\s+(?:את\s+)?(?:ה)?סרט\s*))', '', raw_text, flags=re.IGNORECASE).strip()
    query = cleaned if cleaned else raw_text

    # Skip invalid queries
    if len(query) < 2 or query.startswith(("http://", "https://", "t.me/")) or len(query) > 60:
        return

    # Add to queue for asynchronous multi-user processing
    await request_queue.put((event, query))

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("FATAL: Session string is not authorized.")
        sys.exit(1)

    await init_bot()
    
    # Spawn 3 concurrent background workers for heavy traffic
    for _ in range(3):
        asyncio.create_task(queue_worker())

    print("Userbot is running with Smart Queue & Multi-selection support 24/7...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
