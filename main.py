import os
import sys
import re
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

client = TelegramClient(StringSession(session_str), api_id, api_hash)

# Get the bot's username and ID on startup
me = None

async def init_bot():
    global me
    me = await client.get_me()
    print(f"Logged in as {me.first_name} (@{me.username or 'NoUsername'})")
    await client.send_message("me", f"🚀 מנוע חיפוש הסרטים הופעל בהצלחה עבור @{me.username or me.first_name}!")

@client.on(events.NewMessage(incoming=True))
async def handle_movie_request(event):
    global me
    if not me:
        return
        
    text = event.raw_text.strip()
    if not text:
        return

    # Check if the userbot was mentioned or if command was used
    is_requested = False
    query = ""

    # Match mention
    mention_pattern = rf"@{me.username}\s+(.+)" if me.username else None
    if mention_pattern and re.match(mention_pattern, text, re.IGNORECASE):
        match = re.match(mention_pattern, text, re.IGNORECASE)
        query = match.group(1).strip()
        is_requested = True
    # Match command: .סרט <שם> or /סרט <שם> or סרט <שם> (only if it starts with 'סרט ')
    elif text.startswith((".סרט ", "/סרט ", "סרט ")):
        # Extract query
        parts = text.split(" ", 1)
        if len(parts) > 1:
            query = parts[1].strip()
            is_requested = True

    if not is_requested or not query:
        return

    print(f"Received search request for: '{query}' in chat {event.chat_id}")
    
    # Send a temporary "searching" message
    status_msg = await event.reply("🔎 מחפש את הסרט עבורך, אנא המתן...")

    found_media = None

    try:
        # Search globally across all dialogs
        async for msg in client.iter_messages(None, search=query, limit=50):
            # Check if the message has a video or file attachment
            if msg.media and (msg.video or msg.document):
                if msg.document:
                    mime = msg.document.mime_type or ""
                    size_mb = (msg.document.size or 0) / (1024 * 1024)
                    # Check if video mime type or generic bin file larger than 10MB (common for telegram movies)
                    if 'video' in mime or mime == 'application/octet-stream' or size_mb > 10:
                        found_media = msg.media
                        break
                elif msg.video:
                    found_media = msg.media
                    break

        if found_media:
            # Send the file using Telegram's direct media reference (no download/upload)
            caption = f"🎥 **הסרט שנמצא:** `{query}`\n\nבברכת צפייה מהנה! 🍿"
            await client.send_file(
                event.chat_id,
                found_media,
                caption=caption,
                reply_to=event.id
            )
            # Delete the status message
            await status_msg.delete()
            print(f"Successfully sent movie '{query}' to chat {event.chat_id}")
        else:
            await status_msg.edit(f"❌ לא נמצא סרט התואם לחיפוש: `{query}`.\nנסה לחפש בשם אחר או לבדוק שגיאות כתיב.")
            
    except Exception as e:
        print(f"Error during search/forward: {e}")
        await status_msg.edit("⚠️ אירעה שגיאה במהלך החיפוש. אנא נסה שוב מאוחר יותר.")

async def main():
    await init_bot()
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.start()
    client.loop.run_until_complete(main())
