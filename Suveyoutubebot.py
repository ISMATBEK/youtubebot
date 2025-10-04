import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Tokenni to‘g‘ridan-to‘g‘ri yozing yoki environmentdan oling
BOT_TOKEN = os.getenv("7950519911:AAGq6z-AfvPLJ_47_v1Q1uzauCBuQA_Upks")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

SUPPORTED_DOMAINS = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com"]

def download_video(url):
    try:
        os.makedirs("downloads", exist_ok=True)
        ydl_opts = {
            "outtmpl": "downloads/%(title).100s.%(ext)s",
            "format": "best[filesize<50M]",
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info), info
    except Exception as e:
        logging.error(f"Yuklab olishda xatolik: {e}")
        return None, None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men video yuklab beruvchi botman.\n"
        "Menga YouTube, TikTok yoki Instagram video havolasini yuboring 🎬"
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not any(domain in url for domain in SUPPORTED_DOMAINS):
        await update.message.reply_text("❌ Faqat YouTube, TikTok yoki Instagram havolalari qabul qilinadi!")
        return

    await update.message.reply_text("📥 Video yuklanmoqda... Iltimos, kuting ⏳")

    filename, info = download_video(url)

    if not filename or not os.path.exists(filename):
        await update.message.reply_text("❌ Video yuklab olishda xatolik yuz berdi.")
        return

    size = os.path.getsize(filename)
    if size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ Video hajmi 50MB dan katta, uni yuborib bo‘lmaydi.")
        os.remove(filename)
        return

    try:
        await update.message.reply_video(
            video=open(filename, "rb"),
            caption=f"🎬 {info.get('title', 'Video')} | ✅ Yuklab olindi @VideoYuklovchiBot orqali"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Video yuborishda xatolik: {e}")

    try:
        os.remove(filename)
    except:
        pass


def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video))

    print("🚀 Bot Render’da ishga tushdi!")
    application.run_polling()


if __name__ == "__main__":
    main()
