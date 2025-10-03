import os
import logging
import asyncio
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import concurrent.futures

# Environment variabledan token olish
BOT_TOKEN = os.getenv('7950519911:AAGq6z-AfvPLJ_47_v1Q1uzauCBuQA_Upks')

# Global progress dictionary
download_progress = {}

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Progress callback funksiyasi
def progress_hook(d, chat_id):
    if d['status'] == 'downloading':
        if '_percent_str' in d:
            percent = d['_percent_str'].strip()
            download_progress[chat_id] = percent
    elif d['status'] == 'finished':
        download_progress[chat_id] = "100%"

# Progress bar yaratish
def create_progress_bar(percent_str):
    try:
        if '%' in percent_str:
            percent = float(percent_str.replace('%', '').strip())
        else:
            percent = 0
        
        bars = int(percent / 5)
        progress_bar = "🟢" * bars + "⚪" * (20 - bars)
        return progress_bar
    except:
        return "🟢⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪"

# Yuklash funksiyasi
def download_video(url, chat_id):
    ydl_opts = {
        'outtmpl': 'downloads/%(title).100s.%(ext)s',
        'format': 'best[filesize<50M]',
        'quiet': False,
        'noprogress': False,
        'progress_hooks': [lambda d: progress_hook(d, chat_id)],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info
    except Exception as e:
        logging.error(f"Yuklab olishda xatolik: {e}")
        return None

# Progress yangilash funksiyasi
async def update_progress(chat_id, context, message_id):
    last_percent = ""
    for _ in range(150):  # 5 daqiqa (2 soniya * 150 = 300 soniya)
        await asyncio.sleep(2)
        current_percent = download_progress.get(chat_id, "")
        
        if current_percent != last_percent:
            progress_bar = create_progress_bar(current_percent)
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"📥 **Video Yuklanmoqda...**\n\n{progress_bar}\n\n**Progress: {current_percent}**"
                )
                last_percent = current_percent
            except Exception as e:
                logging.error(f"Progress yangilashda xatolik: {e}")
        
        if current_percent == "100%" or current_percent == "":
            break

# Asosiy menyu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📹 Video Yuklash", callback_data="download_video")],
        [InlineKeyboardButton("📞 Qo'llanma", callback_data="help"),
         InlineKeyboardButton("ℹ️ Bot Haqida", callback_data="about")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎬 **Video Yuklovchi Botga Xush Kelibsiz!**\n\n"
        "Yuqori sifatli videolarni tez yuklab olish uchun mo'ljallangan bot.\n\n"
        "📹 **Qo'llab-quvvatlanadigan platformalar:**\n"
        "• YouTube\n• TikTok\n• Instagram\n• Facebook\n• Twitter\n\n"
        "Quyidagi menyudan kerakli amalni tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Callback query handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "download_video":
        await query.edit_message_text(
            "📹 **Video Yuklash**\n\n"
            "Video havolasini yuboring:\n\n"
            "🌐 **Qo'llab-quvvatlanadigan saytlar:**\n"
            "• YouTube\n• TikTok\n• Instagram\n• Facebook\n• Twitter"
        )
    
    elif data == "help":
        await query.edit_message_text(
            "📞 **Qo'llanma**\n\n"
            "1. Video yuklash uchun video havolasini yuboring\n"
            "2. Bot video formatini avtomatik tanlaydi\n"
            "3. Yuklash progressi real-time ko'rsatiladi\n"
            "4. Maksimal fayl hajmi: 50MB\n\n"
            "⚡ **Tezlik uchun maslahatlar:**\n"
            "• Kichikroq videolar tezroq yuklanadi\n"
            "• Tez internet ulanishidan foydalaning"
        )
    
    elif data == "about":
        await query.edit_message_text(
            "ℹ️ **Bot Haqida**\n\n"
            "🎬 **Video Yuklovchi Bot**\n"
            "Version: 2.0\n\n"
            "⚡ **Xususiyatlar:**\n"
            "• Tez yuklash\n"
            "• Real-time progress\n"
            "• Ko'p platforma qo'llab-quvvatlash\n"
            "• Zamonaviy interfeys"
        )

# Video yuklash handler
async def handle_video_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    chat_id = update.message.chat_id
    
    # URL tekshirish
    supported_domains = ['youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com', 
                         'facebook.com', 'twitter.com', 'x.com']
    
    if not any(domain in url for domain in supported_domains):
        await update.message.reply_text(
            "❌ **Noto'g'ri havola!**\n\n"
            "Quyidagi platformalardan video havolasini yuboring:\n"
            "YouTube, TikTok, Instagram, Facebook, Twitter"
        )
        return
    
    # Yuklash boshlash xabari
    progress_msg = await update.message.reply_text(
        "🔍 **Video tahlil qilinmoqda...**\n\n"
        "⏳ Iltimos kuting..."
    )
    
    try:
        # Progress yangilashni boshlash
        progress_task = asyncio.create_task(update_progress(chat_id, context, progress_msg.message_id))
        
        # Yuklashni boshqa threadda boshlash
        def download_task():
            download_progress[chat_id] = "0%"
            return download_video(url, chat_id)
        
        # Thread orqali yuklash
        with concurrent.futures.ThreadPoolExecutor() as executor:
            video_info = await asyncio.get_event_loop().run_in_executor(executor, download_task)
        
        # Progress taskni to'xtatish
        progress_task.cancel()
        
        if video_info:
            filename = f"downloads/{video_info['title']}.{video_info['ext']}"
            
            # Fayl mavjudligini tekshirish
            if not os.path.exists(filename):
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg.message_id,
                    text="❌ **Video fayli topilmadi!**\n\nBoshqa video yuboring."
                )
                return
            
            # Fayl hajmini tekshirish
            file_size = os.path.getsize(filename)
            if file_size > 50 * 1024 * 1024:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg.message_id,
                    text="❌ **Video hajmi 50MB dan katta!**\n\nBoshqa video yuboring."
                )
                os.remove(filename)
                return
            
            # Yuklash tugallandi xabari
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text="✅ **Video Muvaffaqiyatli Yuklandi!**\n\n📤 Jo'natilmoqda..."
            )
            
            # Videoni yuborish
            try:
                with open(filename, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"🎬 **{video_info['title']}**\n\n"
                               f"⏱ **Davomiylik:** {video_info.get('duration_string', 'Noma\'lum')}\n"
                               f"📦 **Hajm:** {file_size // (1024*1024)}MB\n\n"
                               f"✅ @VideoYuklovchiBot"
                    )
            except Exception as e:
                await update.message.reply_text(f"❌ Video yuborishda xatolik: {str(e)}")
            
            # Faylni o'chirish
            try:
                os.remove(filename)
            except:
                pass
            
        else:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text="❌ **Video yuklab olinmadi!**\n\n"
                     "Iltimos:\n"
                     "• Havolani tekshiring\n"
                     "• Boshqa video yuboring\n"
                     "• Keyinroq qayta urinib ko'ring"
            )
    
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text="❌ **Xatolik yuz berdi!**\n\n"
                     "Iltimos, qayta urinib ko'ring."
            )
        except:
            await update.message.reply_text("❌ Xatolik yuz berdi! Qayta urinib ko'ring.")
    
    finally:
        # Progressni tozalash
        if chat_id in download_progress:
            del download_progress[chat_id]

# Asosiy funksiya
async def main():
    # Katalog yaratish
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # Botni yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video_download))
    
    # Botni ishga tushirish
    print("🚀 Tezkor Video Bot ishga tushdi...")
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
