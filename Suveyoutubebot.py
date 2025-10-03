#!/usr/bin/env python
# coding: utf-8
import os
import re
import logging
import asyncio
import yt_dlp
import mimetypes
from telegram import Application, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from datetime import datetime

# ---------- USER CONFIG ----------
BOT_TOKEN = "7950519911:AAGq6z-AfvPLJ_47_v1Q1uzauCBuQA_Upks"  # <-- shu yerga tokeningizni qo'ying

# Agar Google Drive upload ishlatilsa, quyidagi muhit oʻzgaruvchisi bilan service account JSON fayl yo'lini bering:
# Windows misol: setx GOOGLE_SERVICE_ACCOUNT_FILE "C:\path\to\service_account.json"
# yoki Linux: export GOOGLE_SERVICE_ACCOUNT_FILE="/path/to/service_account.json"
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", None)
# Agar folderga yuklash kerak bo'lsa, folder id ni kiriting (yoki None bo'lsin)
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", None)
# Maksimal Telegram-ga yuboriladigan hajm (byt): 50MB
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024
# ---------------------------------

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Progress dictionary: chat_id -> percent string
download_progress = {}

# Fayl nomlarini tozalash (Windows uchun ruxsat etilmagan belgilarni almashtirish)
def clean_filename(name: str, max_len: int = 120) -> str:
    if not name:
        return "file"
    # Replace forbidden characters \ / : * ? " < > | with underscore
    cleaned = re.sub(r'[\\\/:*?"<>|]', "_", name)
    # Replace fancy quotes and pipes already covered, also strip control chars
    cleaned = re.sub(r'[\x00-\x1f]', "", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip()
    if not cleaned:
        cleaned = "file"
    return cleaned

# Progress hook - yt_dlp chaqiradi
def progress_hook(d, chat_id):
    status = d.get('status')
    if status == 'downloading':
        percent = d.get('_percent_str') or d.get('percent')
        if percent is not None:
            if isinstance(percent, (int, float)):
                percent_str = f"{percent}%"
            else:
                percent_str = str(percent).strip()
            download_progress[chat_id] = percent_str
    elif status == 'finished':
        download_progress[chat_id] = "100%"

# Yuklash funksiyasi (sync; asyncio.to_thread orqali chaqiriladi)
def download_video(url: str, chat_id: int, quality: str = 'best'):
    """
    Yuklaydi va info dict qaytaradi yoki None.
    outtmpl: downloads/<video_id>.<ext> - id asosida saqlaymiz (Windows filename muammolarini oldini oladi).
    """
    # format tanlash
    if quality == 'best':
        fmt = 'bestvideo+bestaudio/best'
    elif quality == 'fast':
        # Balanced: cheklangan balandlik (720p)
        fmt = 'best[height<=720]/best'
    elif quality == 'small':
        # kichik hajmga yo'naltirilgan (360p, filesize filter)
        fmt = 'best[height<=360][filesize<50M]/best[filesize<50M]'
    else:
        fmt = 'best'

    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',  # safe on Windows
        'format': fmt,
        'noplaylist': True,
        'quiet': False,
        'no_warnings': True,
        'progress_hooks': [lambda d: progress_hook(d, chat_id)],
        # enable retries
        'retries': 3,
        # limit filename length inside extractor if needed
        'restrictfilenames': False,  # we use id as filename, so it's okay
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info
    except Exception as e:
        logger.exception("Yuklab olishda xatolik:")
        return None

# Google Drive upload (uses service account)
def upload_to_drive(filepath: str, service_account_file: str = None, folder_id: str = None):
    """
    Faylni Google Drive ga yuklaydi va 'view' link qaytaradi.
    Talablar: google-api-python-client va google-auth kutubxonalari o'rnatilgan bo'lishi kerak.
    SERVICE_ACCOUNT_JSON fayl yo'li GOOGLE_SERVICE_ACCOUNT_FILE muhit o'zgaruvchisida ko'rsatilgan bo'lishi kerak.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except Exception as e:
        logger.exception("Google Drive kutubxonalari topilmadi. 'pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib' ni o'rnating.")
        return None

    svc_file = service_account_file or GOOGLE_SERVICE_ACCOUNT_FILE
    if not svc_file or not os.path.exists(svc_file):
        logger.error("Google service account JSON fayli topilmadi. GOOGLE_SERVICE_ACCOUNT_FILE muhit o'zgaruvchisini to'g'ri belgilang.")
        return None

    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_file(svc_file, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    file_name_on_drive = os.path.basename(filepath)
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type:
        mime_type = 'application/octet-stream'

    file_metadata = {'name': file_name_on_drive}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(filepath, mimetype=mime_type, resumable=True)

    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')

        # Set permission - anyone with link can view
        try:
            permission = {'type': 'anyone', 'role': 'reader'}
            service.permissions().create(fileId=file_id, body=permission).execute()
        except Exception:
            # Agar ruxsat qo'yolmasa ham yuklangan bo'ladi, davom etamiz
            logger.exception("Drive permission qo'yishda xato (lekin fayl yuklangan).")

        # Build shareable link
        drive_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        return drive_link
    except Exception:
        logger.exception("Google Drive ga yuklashda xatolik.")
        return None

# Progress bar yaratish (qizil to'ldirilgan belgilar)
def create_progress_bar(percent_str):
    try:
        if not percent_str:
            percent = 0.0
        elif '%' in str(percent_str):
            percent = float(str(percent_str).replace('%', '').strip())
        else:
            percent = float(percent_str)
        bars = max(0, min(20, int(percent / 5)))
        return "🔴" * bars + "⚪" * (20 - bars)
    except Exception:
        return "🔴" + "⚪" * 19

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📹 Video Yuklash", callback_data="download_video")],
        [InlineKeyboardButton("📞 Qo'llanma", callback_data="help"),
         InlineKeyboardButton("ℹ️ Bot Haqida", callback_data="about")],
        [InlineKeyboardButton("⚙️ Sozlamalar", callback_data="settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎬 **Video Yuklovchi Botga Xush Kelibsiz!**\n\n"
        "Videoni yuklash uchun avval sifatni tanlang, so'ng video havolasini yuboring.\n\n"
        "Quyidagi menyudan kerakli amalni tanlang:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Callback query handler (menu + sifat tanlash)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "download_video":
        # so'rov: sifatni tanlash
        keyboard = [
            [InlineKeyboardButton("🎯 Eng Yuqori", callback_data="sel_quality_best")],
            [InlineKeyboardButton("⚡ Tezkor (720p)", callback_data="sel_quality_fast")],
            [InlineKeyboardButton("💾 Kichik Hajm (360p)", callback_data="sel_quality_small")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "📹 **Video Yuklash**\n\n"
            "Iltimos, yuklash sifatini tanlang (keyin video havolasini yuboring):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    if data in ("sel_quality_best", "sel_quality_fast", "sel_quality_small"):
        # saqlaymiz va foydalanuvchiga URL yuborishni so'raymiz
        if data == "sel_quality_best":
            context.user_data['selected_quality'] = 'best'
            quality_text = "Eng Yuqori"
        elif data == "sel_quality_fast":
            context.user_data['selected_quality'] = 'fast'
            quality_text = "Tezkor (720p)"
        else:
            context.user_data['selected_quality'] = 'small'
            quality_text = "Kichik Hajm (360p)"

        await query.edit_message_text(
            f"🔔 **Sifat tanlandi:** {quality_text}\n\n"
            "Endi videoning havolasini yuboring (YouTube, TikTok, Instagram va hokazo).",
            parse_mode='Markdown'
        )
        # set flag that bot is awaiting url
        context.user_data['awaiting_url'] = True
        return

    # boshqa menu elementlari
    if data == "help":
        await query.edit_message_text(
            "📞 **Qo'llanma**\n\n"
            "1. Videoni yuklash uchun avval sifatni tanlang\n"
            "2. Keyin video havolasini yuboring\n"
            "3. Agar fayl <= 50MB bo'lsa, bot uni Telegram orqali yuboradi\n"
            "4. Agar fayl > 50MB bo'lsa, bot uni Google Drive ga yuklab, havolasini yuboradi\n",
            parse_mode='Markdown'
        )
    elif data == "about":
        await query.edit_message_text(
            "ℹ️ **Bot Haqida**\n\n"
            "Video Yuklovchi Bot — to'g'ridan-to'g'ri Telegram yoki Google Drive orqali yuboradi.\n"
            "Developer: @SizningUsername",
            parse_mode='Markdown'
        )
    elif data == "settings":
        keyboard = [
            [InlineKeyboardButton("📊 Yuklash Sifati", callback_data="download_video")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "⚙️ Sozlamalar: Bu yerda sifatni tanlash mumkin.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    elif data == "back_main":
        # qayta asosiy menyu
        keyboard = [
            [InlineKeyboardButton("📹 Video Yuklash", callback_data="download_video")],
            [InlineKeyboardButton("📞 Qo'llanma", callback_data="help"),
             InlineKeyboardButton("ℹ️ Bot Haqida", callback_data="about")],
            [InlineKeyboardButton("⚙️ Sozlamalar", callback_data="settings")]
        ]
        await query.edit_message_text(
            "🎬 **Video Yuklovchi Botga Xush Kelibsiz!**\n\n"
            "Yuqori sifatli videolarni tez yuklab olish uchun mo'ljallangan bot.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# Video yuklash handler - qaysi sifat tanlangan bo'lsa shunga ko'ra ishlaydi
async def handle_video_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_id = update.effective_chat.id

    # Agar bot URL kutmayotgan bo'lsa, foydalanuvchini yoʻnaltiramiz
    selected_quality = context.user_data.get('selected_quality', 'best')
    awaiting = context.user_data.get('awaiting_url', False)

    # Qo'llanma: agar foydalanuvchi hali sifat tanlamagan bo'lsa, so'rang
    if not awaiting:
        await update.message.reply_text(
            "🔔 Iltimos, avval sifatni tanlang: /start bosib menyudan 'Video Yuklash' -> sifatni tanlang, so'ng havolani yuboring."
        )
        return

    url = text
    supported_domains = ['youtube.com', 'youtu.be', 'tiktok.com', 'instagram.com',
                         'facebook.com', 'twitter.com', 'x.com', 'vimeo.com', 'dailymotion.com']
    if not any(domain in url.lower() for domain in supported_domains):
        await update.message.reply_text(
            "❌ Noto'g'ri havola! Iltimos YouTube, TikTok, Instagram, Facebook, Twitter, Vimeo yoki Dailymotion linkini yuboring."
        )
        return

    # Start progress message
    try:
        progress_msg = await update.message.reply_text(
            "🔍 Video tahlil qilinmoqda...\n⏳ Iltimos kuting...",
            parse_mode='Markdown'
        )
    except Exception:
        # agar yuborishda muammo bo'lsa, log qilamiz va davom etamiz
        logger.exception("progress_msg yuborishda xato")
        progress_msg = None

    # progress updater task
    if progress_msg:
        progress_task = asyncio.create_task(update_progress(chat_id, context, progress_msg.message_id))
    else:
        progress_task = None

    try:
        # download in background thread to not block loop
        info = await asyncio.to_thread(download_video, url, chat_id, selected_quality)

        # mark 100%
        download_progress[chat_id] = "100%"

        if not info:
            if progress_msg:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=progress_msg.message_id,
                        text="❌ Video yuklab olinmadi. Iltimos linkni tekshiring yoki keyinroq urinib ko'ring.",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
            return

        # Build local filename (we used outtmpl with id)
        video_id = info.get('id')
        video_ext = info.get('ext', 'mp4')
        local_filename = f"downloads/{video_id}.{video_ext}"

        # Safety: if file missing, attempt to find similar file
        if not os.path.exists(local_filename):
            # try to find any file starting with id
            candidates = [f for f in os.listdir('downloads') if f.startswith(video_id + ".") or f.startswith(video_id)]
            if candidates:
                local_filename = os.path.join('downloads', candidates[0])
            else:
                logger.error("Yuklangan fayl topilmadi: %s", local_filename)
                if progress_msg:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=progress_msg.message_id,
                            text="❌ Yuklangan fayl topilmadi. Iltimos keyinroq urinib ko'ring.",
                            parse_mode='Markdown'
                        )
                    except Exception:
                        pass
                return

        file_size = os.path.getsize(local_filename)

        # Agar fayl kichik (<= TELEGRAM_MAX_SIZE), Telegram orqali yuboramiz
        if file_size <= TELEGRAM_MAX_SIZE:
            # prepare caption safely (avoid backslashes in f-strings)
            title = info.get('title') or "No title"
            format_str = info.get('format') or "Noma'lum"
            duration_val = info.get('duration')
            if duration_val:
                mins = int(duration_val) // 60
                secs = int(duration_val) % 60
                duration_str = f"{mins}m {secs}s"
            else:
                duration_str = "Noma'lum"

            caption = (
                f"🎬 **{title}**\n\n"
                f"📊 **Sifat:** {format_str}\n"
                f"⏱ **Davomiylik:** {duration_str}\n"
                f"📦 **Hajm:** {file_size // (1024*1024)}MB\n\n"
                "🔴 @VideoYuklovchiBot"
            )

            # update status
            if progress_msg:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=progress_msg.message_id,
                        text="🔴 Video muvaffaqiyatli yuklandi! Jo'natilmoqda...",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass

            # send video
            try:
                with open(local_filename, 'rb') as f:
                    await update.message.reply_video(video=f, caption=caption, parse_mode='Markdown')
            except Exception:
                logger.exception("Videoni yuborishda xato")
                await update.message.reply_text("❌ Videoni yuborishda xatolik yuz berdi.")
            finally:
                # delete local file
                try:
                    os.remove(local_filename)
                except Exception:
                    pass

        else:
            # Fayl katta -> Google Drive ga yuklaymiz (agar sozlangan bo'lsa)
            if GOOGLE_SERVICE_ACCOUNT_FILE:
                # prepare nicer filename for drive based on title
                title_clean = clean_filename(info.get('title') or video_id)
                drive_fname = f"{title_clean}.{video_ext}"
                # temporarily rename local file to drive_fname for nicer name on Drive (optional)
                tmp_path = local_filename
                tmp_renamed = os.path.join('downloads', drive_fname)
                try:
                    os.replace(tmp_path, tmp_renamed)
                    local_filename = tmp_renamed
                except Exception:
                    # agar nomini oʻzgartira olmasa, davom etamiz eski nom bilan
                    logger.exception("Faylni nomini oʻzgartirishda muammo, original nom bilan yuklanadi.")

                # inform user
                if progress_msg:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=progress_msg.message_id,
                            text="📤 Fayl juda katta, Google Drive ga yuklanmoqda. Iltimos kuting...",
                            parse_mode='Markdown'
                        )
                    except Exception:
                        pass

                drive_link = await asyncio.to_thread(upload_to_drive, local_filename, GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_DRIVE_FOLDER_ID)

                if drive_link:
                    try:
                        await update.message.reply_text(
                            f"📁 Video muvaffaqiyatli Google Drive ga yuklandi:\n\n{drive_link}\n\n"
                            "Eslatma: yuklash tugagach lokal fayl o'chirildi.",
                            parse_mode='Markdown'
                        )
                    except Exception:
                        pass
                    # remove local file
                    try:
                        os.remove(local_filename)
                    except Exception:
                        pass
                else:
                    # upload failed
                    try:
                        await update.message.reply_text(
                            "❌ Google Drive ga yuklashda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.",
                            parse_mode='Markdown'
                        )
                    except Exception:
                        pass
            else:
                # Drive sozlanmagan
                try:
                    await update.message.reply_text(
                        "❌ Fayl juda katta va Google Drive sozlanmagan.\n"
                        "Iltimos, bot konfiguratsiyasiga GOOGLE_SERVICE_ACCOUNT_FILE qo'shing yoki kichikroq video yuboring.",
                        parse_mode='Markdown'
                    )
                except Exception:
                    pass
                # saqlab qo'yilgan faylni saqlab qolamiz — yoki foydalanuvchi talab qilsa o'chiramiz
    except Exception:
        logger.exception("Xatolik (handle_video_download):")
        try:
            if progress_msg:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_msg.message_id,
                    text="❌ Xatolik yuz berdi! Iltimos, qayta urinib ko'ring.",
                    parse_mode='Markdown'
                )
        except Exception:
            pass
    finally:
        # tozalash va progress task bekor qilish
        download_progress.pop(chat_id, None)
        context.user_data.pop('awaiting_url', None)
        context.user_data.pop('selected_quality', None)
        if progress_task:
            if not progress_task.done():
                progress_task.cancel()
                try:
                    await progress_task
                except Exception:
                    pass

# Progress updater (edits message with progress bar)
async def update_progress(chat_id, context, message_id):
    last_percent = None
    try:
        for _ in range(300):  # 300 * 2s = 10min limit (safeguard)
            await asyncio.sleep(2)
            current_percent = download_progress.get(chat_id, "")
            if current_percent != last_percent:
                # show progress bar
                bar = create_progress_bar(current_percent)
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"📥 Video yuklanmoqda...\n\n{bar}\n\nProgress: {current_percent}",
                    )
                except Exception:
                    # ba'zi holatlarda edit xatolik beradi (masalan, xabar o'chirilgan)
                    pass
                last_percent = current_percent
            if current_percent == "100%" or current_percent == "":
                break
    except asyncio.CancelledError:
        return

# Asosiy
def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads', exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_video_download))

    logger.info("🚀 Tezkor Video Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()



