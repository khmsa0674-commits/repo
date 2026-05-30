import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  إعدادات البوت الأساسية
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# معرفات الأدمن (أرقام)
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()]

# ─────────────────────────────────────────────
#  معلومات البوت
# ─────────────────────────────────────────────
BOT_NAME = os.getenv("BOT_NAME", "VidBot Pro")
BOT_VERSION = "2.0.0"

WELCOME_MESSAGE = (
    "👋 *أهلاً {name}!*\n\n"
    "🤖 *{bot_name}* v{version}\n\n"
    "أنا بوت متخصص في تحميل الفيديوات من:\n"
    "🎵 TikTok • 📸 Instagram • ▶️ YouTube\n"
    "🐦 Twitter • 📘 Facebook\n\n"
    "📎 *فقط أرسل الرابط وأنا أتكفل بالباقي!*"
)

# ─────────────────────────────────────────────
#  إعدادات التحميل
# ─────────────────────────────────────────────
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "49"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))

# ─────────────────────────────────────────────
#  قنوات الاشتراك الإجباري (تُدار من قاعدة البيانات)
# ─────────────────────────────────────────────
REQUIRED_CHANNELS = os.getenv("REQUIRED_CHANNELS", "").split(",") if os.getenv("REQUIRED_CHANNELS") else []

# ─────────────────────────────────────────────
#  قاعدة البيانات
# ─────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")
