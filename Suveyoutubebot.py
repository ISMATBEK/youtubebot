import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "7950519911:AAGq6z-AfvPLJ_47_v1Q1uzauCBuQA_Upks"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

ALLOWED_DOMAINS = ["youtube.com", "youtu.be", "instagram.com", "tiktok.com"]

def download_video(url):
    try:
        ydl_opts = {
            "outtmpl": "downloads/%(title).100s.%(ext)s",
            "format": "best[filesize<50M]",
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename, info
    except Exception as e:
        logging.error(f"Yuklab olishda xatolik: {e}")
        return None, None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Salom! Men video yuklab beruvchi botman.\n\n"
        "Menga YouTube, TikTok yoki Instagram video havolasini yuboring 📎"
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not any(domain in url for domain in ALLOWED_DOMAINS):
        await update.message.reply_text("❌ Faqat YouTube, TikTok va Instagram havolalari qo‘llab-quvvatlanadi!")
        return

    await update.message.reply_text("📥 Video yuklanmoqda... Iltimos kuting ⏳")

    os.makedirs("downloads", exist_ok=True)

    filename, info = download_video(url)

    if not filename or not os.path.exists(filename):
        await update.message.reply_text("❌ Video yuklab olishda xatolik yuz berdi.")
        return

    file_size = os.path.getsize(filename)
    if file_size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ Video hajmi 50MB dan katta. Iltimos, qisqaroq video yuboring.")
        os.remove(filename)
        return

    try:
        await update.message.reply_video(
            video=open(filename, "rb"),
            caption=f"🎬 {info.get('title', 'Video')}\n✅ Yuklab olindi @VideoYuklovchiBot orqali"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Video yuborishda xatolik: {str(e)}")

    try:
        os.remove(filename)
    except:
        pass


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video))

    print("🚀 Bot ishga tushdi...")
    application.run_polling()  # ✅ asyncio.run() O‘RNIGA oddiy run_polling()


if __name__ == "__main__":
    main()
