import os
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = "@MH999R"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

data = {
    "chat_id": CHANNEL,
    "text": "🔴 اختبار نظام الأخبار — إذا وصلت هذه الرسالة فالبوت يعمل بشكل صحيح."
}

response = requests.post(url, data=data, timeout=30)

print("Status:", response.status_code)
print("Response:", response.text)
