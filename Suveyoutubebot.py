import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Bot tokenini o'rnating
BOT_TOKEN = "7950519911:AAGq6z-AfvPLJ_47_v1Q1uzauCBuQA_Upks"

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **YouTube Video Yuklovchi Bot**\n\n"
        "YouTube videolarini yuklab olish uchun video havolasini yuboring.\n\n"
        "📹 **Qo'llanma:**\n"
        "1. YouTube video havolasini nusxalang\n"
        "2. Bu botga yuboring\n"
        "3. Video avtomatik yuklanadi\n\n"
        "⚠️ **Eslatma:** Faqat shaxsiy foydalanish uchun!"
    )

# YouTube video yuklab olish
def download_youtube_video(url):
    # Yuklab olish sozlamalari
    ydl_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'format': 'best[filesize<50M]',  # 50MB dan kichik videolar
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info
    except Exception as e:
        logging.error(f"Yuklab olishda xatolik: {e}")
        return None

# Xabarlarni qayta ishlash
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.message.chat_id
    
    # YouTube havolasini tekshirish
    if 'youtube.com' not in user_message and 'youtu.be' not in user_message:
        await update.message.reply_text(
            "❌ **Iltimos, YouTube video havolasini yuboring!**\n\n"
            "Misol: https://www.youtube.com/watch?v=...\n"
            "Yoki: https://youtu.be/..."
        )
        return
    
    # Yuklash boshlanganligi haqida xabar
    progress_msg = await update.message.reply_text("📥 Video yuklanmoqda... Iltimos kuting!")
    
    try:
        # Videoni yuklab olish
        video_info = download_youtube_video(user_message)
        
        if video_info:
            # Yuklangan fayl yo'li
            filename = f"downloads/{video_info['title']}.{video_info['ext']}"
            
            # Yuklash muvaffaqiyatli xabari
            await progress_msg.edit_text("✅ Video yuklandi! Jo'natilmoqda...")
            
            # Faylni yuborish
            with open(filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"🎬 **{video_info['title']}**\n\n"
                           f"✅ @YouTubeVideoYuklovchiBot"
                )
            
            # Faylni o'chirish
            try:
                os.remove(filename)
            except:
                pass
            
        else:
            await progress_msg.edit_text(
                "❌ **Video yuklab olinmadi!**\n\n"
                "Sabablari:\n"
                "• Video mavjud emas\n"
                "• Video hajmi 50MB dan katta\n"
                "• Xususiy video\n"
                "• Tarmoq xatosi\n\n"
                "Boshqa video yuboring."
            )
    
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await progress_msg.edit_text(
            "❌ **Xatolik yuz berdi!**\n\n"
            "Iltimos, keyinroq qayta urinib ko'ring yoki boshqa video yuboring."
        )

# Asosiy funksiya
def main():
    # Yuklab olish katalogini yaratish
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # Botni yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Botni ishga tushirish
    print("🤖 YouTube Video Bot ishga tushdi...")
    application.run_polling()

if __name__ == '__main__':
    main()

