import os
import requests

OPENAI_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHANNEL = "@MH999R"

# اختبار أن مفتاح OpenAI موجود
headers = {
    "Authorization": f"Bearer {OPENAI_KEY}"
}

response = requests.get(
    "https://api.openai.com/v1/models",
    headers=headers,
    timeout=30
)

print("OpenAI Status:", response.status_code)

if response.status_code == 200:
    message = "🔴 تم اختبار الاتصال بنجاح — نظام الذكاء الاصطناعي جاهز للعمل."
else:
    message = f"❌ فشل اختبار OpenAI. Status: {response.status_code}"

# إرسال النتيجة إلى تيليغرام
telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

data = {
    "chat_id": CHANNEL,
    "text": message
}

telegram_response = requests.post(
    telegram_url,
    data=data,
    timeout=30
)

print("Telegram Status:", telegram_response.status_code)
print(telegram_response.text)
