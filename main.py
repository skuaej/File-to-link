import os
import asyncio
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 27479878))
API_HASH = os.environ.get("API_HASH", "05f8dc8265d4c5df6376dded1d71c0ff")
# UPDATED TOKEN
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8899757045:AAGhOlgwVYjlOVjm8PsbQkZ8oWlf-blbAx4")
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", -1004337222126))
PORT = int(os.environ.get("PORT", 8080))

# UPDATED URL
RAW_FQDN = os.environ.get("FQDN", "unfair-brittaney-uhhy5-54057e20.koyeb.app/")
FQDN = RAW_FQDN.strip("/") 

# --- INITIALIZE TELEGRAM BOT ---
# Using ":memory:" prevents SQLite lock errors on Koyeb container restarts
app = Client(
    ":memory:", 
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- TELEGRAM BOT LOGIC ---
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_files(client: Client, message: Message):
    # Forward to your specific bin channel
    forwarded_msg = await message.forward(BIN_CHANNEL)
    
    # Generate the link using your Koyeb URL
    msg_id = forwarded_msg.id
    stream_link = f"https://{FQDN}/stream/{msg_id}"
    
    await message.reply_text(
        f"**File is ready!**\n\nLink: `{stream_link}`",
        disable_web_page_preview=True
    )

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply_text("Send me a file to get a stream/download link!")

# --- WEB SERVER LOGIC ---
async def index(request):
    """Health check route for Koyeb to verify the app is alive."""
    return web.Response(text="Bot and Web Server are running successfully!")

async def stream_file(request):
    try:
        msg_id = int(request.match_info['msg_id'])
        msg = await app.get_messages(BIN_CHANNEL, msg_id)
        
        if not msg or getattr(msg, "empty", True):
            return web.Response(status=404, text="File not found")

        file = getattr(msg, msg.media.value)
        file_size = file.file_size
        file_name = getattr(file, "file_name", f"file_{msg_id}")

        headers = {
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        }
        
        range_header = request.headers.get("Range")
        if range_header:
            start, end = range_header.replace("bytes=", "").split("-")
            start = int(start)
            end = int(end) if end else file_size - 1
            length = end - start + 1
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(length)
            response = web.StreamResponse(status=206, headers=headers)
        else:
            headers["Content-Length"] = str(file_size)
            response = web.StreamResponse(status=200, headers=headers)
            start = 0

        await response.prepare(request)

        offset = start
        async for chunk in app.stream_media(msg, offset=offset):
            await response.write(chunk)
            
        return response

    except Exception as e:
        print(f"Error: {e}")
        return web.Response(status=500, text="Server Error")

# --- START SERVICES ---
async def start_services():
    await app.start()
    print("Bot Started!")

    server = web.Application()
    
    # The health check route Koyeb needs to keep the bot alive
    server.router.add_get('/', index) 
    
    # The main streaming route
    server.router.add_get('/stream/{msg_id}', stream_file)
    
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web Server running on port {PORT}")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(start_services())
