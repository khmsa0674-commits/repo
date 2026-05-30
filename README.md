# 🤖 VidBot Pro — بوت تحميل الفيديوات

بوت تليكرام متكامل لتحميل الفيديوات من TikTok وInstagram وYouTube وTwitter وFacebook.

---

## ✨ المميزات

| الميزة | التفاصيل |
|--------|----------|
| 🎵 TikTok | تحميل بدون علامة مائية |
| 📸 Instagram | ريلز، بوستات، ستوريز |
| ▶️ YouTube | حتى 720p |
| 🐦 Twitter/X | فيديوات وGIF |
| 📘 Facebook | فيديوات عامة |
| 📢 اشتراك إجباري | إدارة القنوات من البوت مباشرة |
| 📣 البث للكل | إرسال رسالة لجميع المستخدمين |
| 📊 إحصائيات | متابعة المستخدمين والتحميلات |
| 🛡 لوحة أدمن | تحكم كامل |

---

## 🚀 التشغيل المحلي

### 1. المتطلبات
- Python 3.11+
- ffmpeg مثبت على النظام

### 2. تثبيت المكتبات
```bash
pip install -r requirements.txt
```

### 3. إعداد المتغيرات
```bash
cp .env.example .env
# عدّل الملف .env
```

**اضبط:**
- `BOT_TOKEN` — من [@BotFather](https://t.me/BotFather)
- `ADMIN_IDS` — معرفك الرقمي (من [@userinfobot](https://t.me/userinfobot))

### 4. تشغيل البوت
```bash
python bot.py
```

---

## 🚂 النشر على Railway

### الطريقة الأولى: من GitHub

1. **ارفع الكود على GitHub:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

2. **أنشئ مشروع على Railway:**
   - اذهب إلى [railway.app](https://railway.app)
   - اضغط **New Project**
   - اختر **Deploy from GitHub repo**
   - اختر المستودع

3. **أضف المتغيرات:**
   - اذهب لـ **Variables** في Railway
   - أضف:
     - `BOT_TOKEN`
     - `ADMIN_IDS`
     - `BOT_NAME` (اختياري)

4. **انتظر** — Railway سيبني وينشر البوت تلقائياً!

### الطريقة الثانية: من Docker

```bash
docker build -t vidbot .
docker run -d \
  -e BOT_TOKEN=your_token \
  -e ADMIN_IDS=your_id \
  --name vidbot \
  vidbot
```

---

## 🛠 أوامر البوت

### للمستخدمين
| الأمر | الوصف |
|-------|-------|
| `/start` | بدء البوت |
| `/help` | المساعدة |
| أرسل رابط | تحميل الفيديو مباشرة |

### للأدمن
| الأمر | الوصف |
|-------|-------|
| `/admin` | لوحة التحكم |
| `/broadcast رسالة` | إرسال للكل |
| `/addchannel @ch اسم` | إضافة قناة |
| `/removechannel @ch` | حذف قناة |
| `/channels` | قائمة القنوات |
| `/stats` | الإحصائيات |

---

## 📋 إضافة قنوات الاشتراك الإجباري

1. اجعل البوت **أدمن** في القناة
2. استخدم الأمر:
```
/addchannel @channel_username اسم القناة
```
3. أو باستخدام المعرف الرقمي:
```
/addchannel -100123456789 اسم القناة
```

---

## ❓ حل المشاكل الشائعة

### البوت لا يحمل من Instagram
- Instagram يحتاج كوكيز أحياناً
- ضع ملف `instagram_cookies.txt` بجانب `bot.py`
- لاستخراج الكوكيز استخدم إضافة [Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)

### خطأ ffmpeg
```bash
# Ubuntu/Debian
apt install ffmpeg

# Mac
brew install ffmpeg

# Windows
# حمّل من ffmpeg.org وأضفه لـ PATH
```

### تجاوز حجم 50MB
- Telegram لا يسمح بإرسال ملفات أكبر من 50MB للبوتات
- الفيديوات الكبيرة ستُرفض تلقائياً

---

## 📄 الترخيص

MIT License — استخدم الكود بحرية!
