FROM python:3.12-slim

# تثبيت المتطلبات النظامية
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# مجلد العمل
WORKDIR /app

# نسخ ملفات المتطلبات
COPY requirements.txt .

# تثبيت مكتبات Python
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الكود
COPY . .

# إنشاء مجلد للبيانات
RUN mkdir -p /app/data

# تشغيل البوت
CMD ["python", "bot.py"]
