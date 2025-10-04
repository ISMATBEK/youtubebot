import os
import logging
import asyncio
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("7950519911:AAGq6z-AfvPLJ_47_v1Q1uzauCBuQA_Upks")

if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN topilmadi! Iltimos, Render.com da environment variable qo‘shing.")
    exit(1)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Progressni saqlash uchun lug‘at
download_progress = {}

# YouTube yuklab olish funksiyasi
def download_video(url, chat_id):
    ydl_opts = {
        'outtmpl': f'downloads/{chat_id}_%(title)s.%(ext)s',
        'format': 'best[filesize<50M]',
        'progress_hooks': [lambda d: progress_hook(d, chat_id)],
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info

# Yuklab olish progressini kuzatish
def progress_hook(d, chat_id):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '').strip()
        download_progress[chat_id] = percent
    elif d['status'] == 'finished':
        download_progress[chat_id] = "100%"

# Progress bar yasash
def progress_bar(percent_str):
    try:
        val = float(percent_str.replace('%', ''))
    except:
        val = 0
    bars = int(val / 5)
    return "🟩" * bars + "⬜" * (20 - bars)

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 YouTube Yuklovchi Botga xush kelibsiz!\n\n"
        "Menga YouTube video havolasini yuboring — men sizga 50MB gacha bo‘lgan videoni yuboraman."
    )

# Progressni yangilovchi fon vazifa
async def show_progress(chat_id, context, msg_id):
    old = ""
    for _ in range(150):
        await asyncio.sleep(2)
        cur = download_progress.get(chat_id, "")
        if cur and cur != old:
            bar = progress_bar(cur)
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=f"📥 Yuklanmoqda...\n{bar}\nProgress: {cur}"
                )
            except:
                pass
            old = cur
        if cur == "100%":
            break

# Foydalanuvchi yuborgan linkni qayta ishlash
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.message.chat_id

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ Faqat YouTube havolalarini yuboring.")
        return

    await update.message.reply_text("🔍 Video tahlil qilinmoqda...")

    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    msg = await update.message.reply_text("📥 Yuklanmoqda...")

    progress_task = asyncio.create_task(show_progress(chat_id, context, msg.message_id))

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: download_video(url, chat_id))

        progress_task.cancel()

        if not info:
            await update.message.reply_text("❌ Yuklab olishda xatolik yuz berdi.")
            return

        filename = f"downloads/{chat_id}_{info['title']}.{info['ext']}"
        if not os.path.exists(filename):
            await update.message.reply_text("❌ Fayl topilmadi.")
            return

        size = os.path.getsize(filename)
        if size > 50 * 1024 * 1024:
            await update.message.reply_text("⚠️ Video hajmi 50MB dan katta. Kichikroq video yuboring.")
            os.remove(filename)
            return

        await update.message.reply_text("✅ Yuklab olindi! Videoni yuboryapman...")
        with open(filename, "rb") as video:
            await update.message.reply_video(video=video, caption=f"🎬 {info['title']}")

        os.remove(filename)

    except Exception as e:
        logger.error(e)
        await update.message.reply_text("❌ Xatolik yuz berdi. Keyinroq urinib ko‘ring.")
    finally:
        if chat_id in download_progress:
            del download_progress[chat_id]

# Asosiy ishga tushirish funksiyasi
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    print("🚀 Bot ishga tushdi...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
