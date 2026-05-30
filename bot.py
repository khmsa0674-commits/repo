import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
import yt_dlp
import json
import re
from pathlib import Path
import tempfile

# ─────────────────────────────────────────────
#  إعداد السجلات
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  تحميل الإعدادات
# ─────────────────────────────────────────────
from config import (
    BOT_TOKEN, ADMIN_IDS, REQUIRED_CHANNELS,
    MAX_FILE_SIZE_MB, DOWNLOAD_TIMEOUT,
    WELCOME_MESSAGE, BOT_NAME, BOT_VERSION
)
from database import Database

db = Database()

# ─────────────────────────────────────────────
#  مساعدات
# ─────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def extract_url(text: str) -> str | None:
    """استخرج أول رابط من النص."""
    pattern = r'https?://[^\s]+'
    match = re.search(pattern, text)
    return match.group(0) if match else None

def detect_platform(url: str) -> str:
    """تحديد المنصة من الرابط."""
    url_lower = url.lower()
    if any(x in url_lower for x in ['tiktok.com', 'vm.tiktok', 'vt.tiktok']):
        return 'tiktok'
    elif any(x in url_lower for x in ['instagram.com', 'instagr.am']):
        return 'instagram'
    elif any(x in url_lower for x in ['youtube.com', 'youtu.be', 'youtube-nocookie']):
        return 'youtube'
    elif any(x in url_lower for x in ['twitter.com', 'x.com', 't.co']):
        return 'twitter'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'facebook'
    return 'unknown'

def platform_emoji(platform: str) -> str:
    return {
        'tiktok': '🎵',
        'instagram': '📸',
        'youtube': '▶️',
        'twitter': '🐦',
        'facebook': '📘',
        'unknown': '🌐'
    }.get(platform, '🌐')

# ─────────────────────────────────────────────
#  التحقق من الاشتراك
# ─────────────────────────────────────────────
async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, list]:
    """تحقق إن كان المستخدم مشترك في القنوات الإجبارية."""
    if not REQUIRED_CHANNELS:
        return True, []

    channels_data = db.get_channels()
    if not channels_data:
        return True, []

    not_joined = []
    for ch in channels_data:
        try:
            member = await context.bot.get_chat_member(ch['channel_id'], user_id)
            if member.status in [ChatMember.LEFT, ChatMember.BANNED]:
                not_joined.append(ch)
        except TelegramError as e:
            logger.warning(f"خطأ التحقق من القناة {ch['channel_id']}: {e}")

    return len(not_joined) == 0, not_joined

async def send_subscription_required(update: Update, not_joined: list):
    """أرسل رسالة طلب الاشتراك."""
    buttons = []
    for ch in not_joined:
        name = ch.get('name', 'القناة')
        link = ch.get('invite_link', ch['channel_id'])
        buttons.append([InlineKeyboardButton(f"📢 {name}", url=link)])
    
    buttons.append([InlineKeyboardButton("✅ تحققت من اشتراكي", callback_data="check_sub")])
    
    text = (
        "🔒 *الاشتراك الإجباري*\n\n"
        "عشان تستخدم البوت، لازم تشترك في القنوات هذي أول:\n\n"
    )
    for ch in not_joined:
        text += f"• {ch.get('name', ch['channel_id'])}\n"
    
    text += "\nبعد الاشتراك اضغط الزر أدناه ✅"
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

# ─────────────────────────────────────────────
#  تحميل الفيديو
# ─────────────────────────────────────────────
async def download_video(url: str, platform: str) -> dict:
    """تحميل الفيديو باستخدام yt-dlp."""
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, '%(title).50s.%(ext)s')

    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[filesize<49M]/bestvideo[filesize<49M]+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': False,
        'socket_timeout': DOWNLOAD_TIMEOUT,
        'retries': 3,
        'merge_output_format': 'mp4',
        'writeinfojson': False,
        'writethumbnail': False,
        'postprocessors': [],
    }

    # إعدادات خاصة بكل منصة
    if platform == 'tiktok':
        ydl_opts.update({
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.tiktok.com/',
            }
        })
    elif platform == 'instagram':
        cookies_file = 'instagram_cookies.txt'
        if os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file
    elif platform == 'youtube':
        ydl_opts['format'] = 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        # ابحث عن الملف الفعلي
        if not os.path.exists(filename):
            for f in Path(tmp_dir).iterdir():
                if f.is_file() and f.suffix in ['.mp4', '.mkv', '.webm', '.mov']:
                    filename = str(f)
                    break

        file_size = os.path.getsize(filename) / (1024 * 1024)

        return {
            'filepath': filename,
            'title': info.get('title', 'فيديو'),
            'uploader': info.get('uploader', 'غير معروف'),
            'duration': info.get('duration', 0),
            'view_count': info.get('view_count', 0),
            'like_count': info.get('like_count', 0),
            'file_size': file_size,
            'tmp_dir': tmp_dir,
        }

def cleanup(tmp_dir: str):
    """حذف الملفات المؤقتة."""
    import shutil
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

# ─────────────────────────────────────────────
#  أوامر المستخدم
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or '', user.full_name or '')
    
    buttons = [
        [
            InlineKeyboardButton("📥 تحميل فيديو", callback_data="help_download"),
            InlineKeyboardButton("ℹ️ عن البوت", callback_data="about"),
        ],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
    ]

    welcome = WELCOME_MESSAGE.format(
        name=user.first_name,
        bot_name=BOT_NAME,
        version=BOT_VERSION
    )

    await update.message.reply_text(
        welcome,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"*🤖 {BOT_NAME} — دليل الاستخدام*\n\n"
        "📥 *كيف تحمل فيديو؟*\n"
        "فقط أرسل الرابط مباشرة وأنا راح أتكفل بالباقي!\n\n"
        "✅ *المنصات المدعومة:*\n"
        "• 🎵 TikTok — بدون علامة مائية\n"
        "• 📸 Instagram — ريلز وبوستات\n"
        "• ▶️ YouTube — حتى 720p\n"
        "• 🐦 Twitter/X\n"
        "• 📘 Facebook\n\n"
        "⚠️ *ملاحظات:*\n"
        "• الحد الأقصى للحجم: 50MB\n"
        "• الفيديو الخاص مو مدعوم\n\n"
        "🆘 مشكلة؟ تواصل مع الإدمن"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل والروابط."""
    user = update.effective_user
    text = update.message.text or ''

    # تسجيل المستخدم
    db.add_user(user.id, user.username or '', user.full_name or '')

    # استخرج الرابط
    url = extract_url(text)
    if not url:
        await update.message.reply_text(
            "📎 أرسل رابط فيديو من TikTok أو Instagram أو YouTube\n"
            "مثال: https://www.tiktok.com/..."
        )
        return

    # تحقق الاشتراك
    subscribed, not_joined = await check_subscription(user.id, context)
    if not subscribed:
        await send_subscription_required(update, not_joined)
        return

    platform = detect_platform(url)
    emoji = platform_emoji(platform)

    if platform == 'unknown':
        await update.message.reply_text(
            "❌ الرابط هذا مو مدعوم.\n"
            "المنصات المدعومة: TikTok, Instagram, YouTube, Twitter, Facebook"
        )
        return

    # رسالة الانتظار
    status_msg = await update.message.reply_text(
        f"{emoji} *جاري التحميل...*\n\n"
        f"المنصة: `{platform.upper()}`\n"
        "⏳ انتظر شوية...",
        parse_mode=ParseMode.MARKDOWN
    )

    tmp_dir = None
    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: download_video.__wrapped__(url, platform)
                if hasattr(download_video, '__wrapped__') else _sync_download(url, platform)
            ),
            timeout=DOWNLOAD_TIMEOUT + 30
        )

        tmp_dir = result['tmp_dir']
        filepath = result['filepath']
        file_size = result['file_size']

        if file_size > MAX_FILE_SIZE_MB:
            await status_msg.edit_text(
                f"❌ حجم الفيديو كبير جداً ({file_size:.1f}MB)\n"
                f"الحد الأقصى: {MAX_FILE_SIZE_MB}MB"
            )
            return

        await status_msg.edit_text(f"{emoji} *جاري الرفع...*", parse_mode=ParseMode.MARKDOWN)

        duration = result['duration']
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "غير معروف"

        caption = (
            f"{emoji} *{result['title'][:100]}*\n\n"
            f"👤 `{result['uploader']}`\n"
            f"⏱ `{duration_str}`\n"
            f"📁 `{file_size:.1f} MB`\n\n"
            f"🤖 *{BOT_NAME}*"
        )

        with open(filepath, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_file,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                supports_streaming=True,
            )

        await status_msg.delete()
        db.increment_downloads(user.id)
        db.log_download(user.id, url, platform, file_size)
        logger.info(f"✅ تحميل ناجح | user={user.id} | platform={platform} | size={file_size:.1f}MB")

    except asyncio.TimeoutError:
        await status_msg.edit_text(
            "⏰ *انتهت المهلة*\n\nالرابط يأخذ وقت طويل، جرب مرة ثانية أو جرب رابط آخر.",
            parse_mode=ParseMode.MARKDOWN
        )
    except yt_dlp.utils.DownloadError as e:
        err = str(e)
        friendly = parse_ydl_error(err)
        await status_msg.edit_text(friendly, parse_mode=ParseMode.MARKDOWN)
        logger.error(f"yt-dlp error | user={user.id} | {err[:200]}")
    except Exception as e:
        await status_msg.edit_text(
            "❌ *حدث خطأ غير متوقع*\n\nحاول مرة ثانية أو تواصل مع الإدمن.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.error(f"خطأ عام | user={user.id} | {e}", exc_info=True)
    finally:
        if tmp_dir:
            cleanup(tmp_dir)

def _sync_download(url: str, platform: str) -> dict:
    """نسخة متزامنة من download_video."""
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, '%(title).50s.%(ext)s')

    ydl_opts = {
        'outtmpl': output_template,
        'format': 'best[filesize<49M]/bestvideo[filesize<49M]+bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': False,
        'socket_timeout': DOWNLOAD_TIMEOUT,
        'retries': 3,
        'merge_output_format': 'mp4',
    }

    if platform == 'tiktok':
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
            'Referer': 'https://www.tiktok.com/',
        }
    elif platform == 'instagram':
        if os.path.exists('instagram_cookies.txt'):
            ydl_opts['cookiefile'] = 'instagram_cookies.txt'
    elif platform == 'youtube':
        ydl_opts['format'] = 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            for f in Path(tmp_dir).iterdir():
                if f.is_file() and f.suffix in ['.mp4', '.mkv', '.webm', '.mov', '.m4v']:
                    filename = str(f)
                    break

        file_size = os.path.getsize(filename) / (1024 * 1024)

        return {
            'filepath': filename,
            'title': info.get('title', 'فيديو'),
            'uploader': info.get('uploader') or info.get('channel') or 'غير معروف',
            'duration': info.get('duration', 0),
            'view_count': info.get('view_count', 0),
            'like_count': info.get('like_count', 0),
            'file_size': file_size,
            'tmp_dir': tmp_dir,
        }

def parse_ydl_error(err: str) -> str:
    """تحويل أخطاء yt-dlp إلى رسائل عربية."""
    err_lower = err.lower()
    if 'private' in err_lower or 'login' in err_lower or 'age' in err_lower:
        return "🔒 *الفيديو خاص أو يحتاج تسجيل دخول*\n\nما أقدر أحمل هذا الفيديو."
    elif 'not available' in err_lower or 'unavailable' in err_lower:
        return "🚫 *الفيديو غير متاح*\n\nممكن يكون محذوف أو محظور في منطقتك."
    elif 'copyright' in err_lower:
        return "⚖️ *الفيديو محمي بحقوق النشر*\n\nما أقدر أحمله."
    elif 'http error 429' in err_lower or 'rate' in err_lower:
        return "⏳ *طلبات كثيرة*\n\nانتظر دقيقة وحاول مرة ثانية."
    elif 'no video' in err_lower or 'no formats' in err_lower:
        return "❌ *ما فيه فيديو في هذا الرابط*\n\nتأكد من الرابط وحاول مرة ثانية."
    elif 'network' in err_lower or 'connection' in err_lower:
        return "🌐 *مشكلة في الاتصال*\n\nحاول مرة ثانية بعد قليل."
    else:
        return "❌ *فشل التحميل*\n\nتأكد من الرابط وحاول مرة ثانية.\nإذا استمرت المشكلة تواصل مع الإدمن."

# ─────────────────────────────────────────────
#  أوامر الأدمن
# ─────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ ما عندك صلاحية.")
        return

    stats = db.get_stats()
    buttons = [
        [
            InlineKeyboardButton("📢 إرسال للكل", callback_data="admin_broadcast"),
            InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton("➕ إضافة قناة", callback_data="admin_add_channel"),
            InlineKeyboardButton("🗑 حذف قناة", callback_data="admin_del_channel"),
        ],
        [
            InlineKeyboardButton("📋 القنوات", callback_data="admin_list_channels"),
            InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users"),
        ],
    ]

    text = (
        f"🛠 *لوحة التحكم — {BOT_NAME}*\n\n"
        f"👥 المستخدمين: `{stats['total_users']}`\n"
        f"📥 التحميلات: `{stats['total_downloads']}`\n"
        f"📢 القنوات: `{stats['total_channels']}`\n"
        f"🗓 اليوم: `{stats['today_downloads']}`"
    )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة لجميع المستخدمين."""
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "📢 *طريقة الاستخدام:*\n`/broadcast رسالتك هنا`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    message = ' '.join(context.args)
    users = db.get_all_users()
    total = len(users)
    success = 0
    failed = 0

    status_msg = await update.message.reply_text(
        f"📢 *جاري الإرسال...*\n0/{total}",
        parse_mode=ParseMode.MARKDOWN
    )

    for i, user_id in enumerate(users, 1):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *رسالة من الإدارة*\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            success += 1
        except TelegramError:
            failed += 1

        if i % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 *جاري الإرسال...*\n{i}/{total}\n✅ {success} | ❌ {failed}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass

        await asyncio.sleep(0.05)  # تجنب حد المعدل

    await status_msg.edit_text(
        f"✅ *اكتمل الإرسال*\n\n"
        f"📊 الإجمالي: `{total}`\n"
        f"✅ ناجح: `{success}`\n"
        f"❌ فشل: `{failed}`",
        parse_mode=ParseMode.MARKDOWN
    )

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة قناة اشتراك إجباري."""
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "📢 *طريقة الاستخدام:*\n"
            "`/addchannel @channel_username اسم_القناة`\n"
            "أو\n"
            "`/addchannel -100xxxxxxxxxx اسم_القناة`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    channel_id = context.args[0]
    name = ' '.join(context.args[1:])
    
    # محاولة الحصول على رابط الدعوة
    invite_link = channel_id
    try:
        chat = await context.bot.get_chat(channel_id)
        if chat.invite_link:
            invite_link = chat.invite_link
        elif chat.username:
            invite_link = f"https://t.me/{chat.username}"
    except TelegramError as e:
        await update.message.reply_text(
            f"⚠️ تحذير: ما قدرت أوصل للقناة.\n"
            f"تأكد إن البوت أدمن في القناة.\n\n`{e}`",
            parse_mode=ParseMode.MARKDOWN
        )

    db.add_channel(channel_id, name, invite_link)
    await update.message.reply_text(
        f"✅ *تمت إضافة القناة*\n\n"
        f"📢 الاسم: `{name}`\n"
        f"🆔 المعرف: `{channel_id}`",
        parse_mode=ParseMode.MARKDOWN
    )

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف قناة."""
    if not is_admin(update.effective_user.id):
        return

    if not context.args:
        channels = db.get_channels()
        if not channels:
            await update.message.reply_text("📭 ما في قنوات مضافة.")
            return
        
        text = "🗑 *القنوات المتاحة للحذف:*\n\n"
        for ch in channels:
            text += f"• `{ch['channel_id']}` — {ch['name']}\n"
        text += "\n`/removechannel @channel_id`"
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    channel_id = context.args[0]
    db.remove_channel(channel_id)
    await update.message.reply_text(f"✅ تم حذف القناة `{channel_id}`", parse_mode=ParseMode.MARKDOWN)

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض القنوات."""
    if not is_admin(update.effective_user.id):
        return

    channels = db.get_channels()
    if not channels:
        await update.message.reply_text("📭 ما في قنوات مضافة حتى الآن.\n\nاستخدم `/addchannel` لإضافة قناة.")
        return

    text = f"📋 *قنوات الاشتراك الإجباري ({len(channels)}):*\n\n"
    for i, ch in enumerate(channels, 1):
        text += (
            f"{i}. *{ch['name']}*\n"
            f"   🆔 `{ch['channel_id']}`\n"
            f"   🔗 {ch.get('invite_link', 'لا يوجد')}\n\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات البوت."""
    if not is_admin(update.effective_user.id):
        return

    stats = db.get_stats()
    platform_stats = db.get_platform_stats()

    platform_text = ""
    for p, count in platform_stats.items():
        emoji = platform_emoji(p)
        platform_text += f"{emoji} {p.upper()}: `{count}`\n"

    text = (
        f"📊 *إحصائيات {BOT_NAME}*\n\n"
        f"👥 إجمالي المستخدمين: `{stats['total_users']}`\n"
        f"📥 إجمالي التحميلات: `{stats['total_downloads']}`\n"
        f"📅 تحميلات اليوم: `{stats['today_downloads']}`\n"
        f"📢 القنوات: `{stats['total_channels']}`\n\n"
        f"*📈 التحميلات حسب المنصة:*\n{platform_text}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────────
#  معالج الأزرار
# ─────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data == "check_sub":
        subscribed, not_joined = await check_subscription(user.id, context)
        if subscribed:
            await query.message.edit_text(
                "✅ *تم التحقق بنجاح!*\n\nأرسل رابط الفيديو الآن 🎬",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.answer("❌ لم تشترك في جميع القنوات بعد!", show_alert=True)

    elif data == "about":
        text = (
            f"🤖 *{BOT_NAME}* v{BOT_VERSION}\n\n"
            "بوت تليكرام متخصص في تحميل الفيديوات\n"
            "من أشهر منصات السوشيال ميديا.\n\n"
            "✨ *المميزات:*\n"
            "• تيك توك بدون علامة مائية\n"
            "• انستقرام ريلز وبوستات\n"
            "• يوتيوب حتى 720p\n"
            "• سرعة عالية وجودة ممتازة\n\n"
            "🛡 *مصنوع بـ Python + yt-dlp*"
        )
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "my_stats":
        user_stats = db.get_user_stats(user.id)
        text = (
            f"📊 *إحصائياتك*\n\n"
            f"📥 تحميلاتك: `{user_stats.get('downloads', 0)}`\n"
            f"📅 انضممت: `{user_stats.get('joined_date', 'غير معروف')}`"
        )
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "help_download":
        text = (
            "📥 *كيف تحمل فيديو؟*\n\n"
            "1. انسخ رابط الفيديو\n"
            "2. ارسله مباشرة هنا\n"
            "3. انتظر ثواني وراح يوصلك الفيديو! ✅\n\n"
            "🎵 TikTok: `https://vm.tiktok.com/...`\n"
            "📸 Instagram: `https://www.instagram.com/reel/...`\n"
            "▶️ YouTube: `https://youtu.be/...`"
        )
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "admin_broadcast":
        if not is_admin(user.id):
            return
        await query.message.edit_text(
            "📢 *إرسال رسالة للكل*\n\n"
            "استخدم الأمر:\n`/broadcast رسالتك هنا`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "admin_stats":
        if not is_admin(user.id):
            return
        stats = db.get_stats()
        platform_stats = db.get_platform_stats()
        platform_text = "".join(
            f"{platform_emoji(p)} {p.upper()}: `{c}`\n"
            for p, c in platform_stats.items()
        )
        text = (
            f"📊 *إحصائيات البوت*\n\n"
            f"👥 المستخدمين: `{stats['total_users']}`\n"
            f"📥 التحميلات: `{stats['total_downloads']}`\n"
            f"📅 اليوم: `{stats['today_downloads']}`\n\n"
            f"*المنصات:*\n{platform_text}"
        )
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "admin_list_channels":
        if not is_admin(user.id):
            return
        channels = db.get_channels()
        if not channels:
            await query.message.edit_text("📭 ما في قنوات مضافة.")
            return
        text = f"📋 *القنوات ({len(channels)}):*\n\n"
        for ch in channels:
            text += f"• *{ch['name']}* — `{ch['channel_id']}`\n"
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data == "admin_users":
        if not is_admin(user.id):
            return
        stats = db.get_stats()
        await query.message.edit_text(
            f"👥 *المستخدمين*\n\n"
            f"الإجمالي: `{stats['total_users']}`\n\n"
            "لتصدير قائمة المستخدمين استخدم `/exportusers`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "admin_add_channel":
        if not is_admin(user.id):
            return
        await query.message.edit_text(
            "➕ *إضافة قناة جديدة*\n\n"
            "استخدم الأمر:\n"
            "`/addchannel @username اسم القناة`\n\n"
            "⚠️ تأكد إن البوت أدمن في القناة!",
            parse_mode=ParseMode.MARKDOWN
        )

    elif data == "admin_del_channel":
        if not is_admin(user.id):
            return
        channels = db.get_channels()
        if not channels:
            await query.message.edit_text("📭 ما في قنوات لحذفها.")
            return
        buttons = [
            [InlineKeyboardButton(f"🗑 {ch['name']}", callback_data=f"delch_{ch['channel_id']}")]
            for ch in channels
        ]
        await query.message.edit_text(
            "🗑 *اختر القناة للحذف:*",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )

    elif data.startswith("delch_"):
        if not is_admin(user.id):
            return
        channel_id = data[6:]
        db.remove_channel(channel_id)
        await query.message.edit_text(f"✅ تم حذف القناة `{channel_id}`", parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────────
#  تشغيل البوت
# ─────────────────────────────────────────────
def main():
    logger.info(f"🚀 تشغيل {BOT_NAME} v{BOT_VERSION}...")

    app = Application.builder().token(BOT_TOKEN).build()

    # أوامر المستخدم
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # أوامر الأدمن
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("addchannel", add_channel))
    app.add_handler(CommandHandler("removechannel", remove_channel))
    app.add_handler(CommandHandler("channels", list_channels))
    app.add_handler(CommandHandler("stats", stats_command))

    # معالج الأزرار
    app.add_handler(CallbackQueryHandler(callback_handler))

    # معالج الرسائل
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ البوت شغال وجاهز!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
