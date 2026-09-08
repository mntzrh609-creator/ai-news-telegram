import os
import requests
import feedparser
import json

OPENAI_KEY = os.environ["OPENAI_API_KEY"]

# مصادر الأخبار
FEEDS = {
    "العراق": "https://feeds.bbci.co.uk/news/topics/ce1qrvle14rt/rss.xml",
    "العالم": "https://feeds.bbci.co.uk/news/world/rss.xml",
}

# عدد الأخبار التي نأخذها من كل مصدر
MAX_NEWS_PER_SOURCE = 5


def get_news():
    news = []

    for category, feed_url in FEEDS.items():
        print(f"\n🔎 جلب أخبار {category}...")

        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "").strip()

            if title:
                news.append({
                    "category": category,
                    "title": title,
                    "summary": summary,
                    "link": link
                })

    return news


def analyze_news(news):
    news_text = json.dumps(news, ensure_ascii=False, indent=2)

    prompt = f"""
أنت محرر أخبار محترف.

مهمتك تحليل الأخبار التالية واختيار الأخبار المهمة فقط.

القواعد:

1. العراق + العالم فقط.
2. اختر الأخبار المهمة ذات التأثير السياسي أو الأمني أو الاقتصادي أو الإنساني أو الدولي.
3. تجاهل الأخبار الخفيفة والترفيهية والرياضية والأخبار غير المهمة.
4. لا تكرر نفس الحدث.
5. لا تخترع أي معلومة.
6. لا تضف أرقامًا غير موجودة في المصادر.
7. يجب الحفاظ على الأرقام والمعلومات المهمة.
8. يجب التأكد من أن الخبر واضح ومسنود بالمصدر المتاح.
9. إذا كان الخبر غير واضح أو لا يمكن الاعتماد عليه، استبعده.
10. لا تضع رابطًا في النص النهائي.

صيغة النشر المطلوبة:

🔴 المصدر: نص الخبر المختصر والواضح.

يجب أن يبدأ كل خبر بـ 🔴.

اذكر اسم المصدر في بداية الخبر.

أعد فقط الأخبار التي تستحق النشر.

الأخبار:
{news_text}
"""

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-5.6-luna",
            "input": prompt
        },
        timeout=120
    )

    print("\nOpenAI Status:", response.status_code)

    if response.status_code != 200:
        print("❌ فشل OpenAI")
        print(response.text)
        return None

    data = response.json()

    # استخراج النص من Responses API
    output_text = data.get("output_text")

    if not output_text:
        print("❌ لم يتم الحصول على نص من OpenAI")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return None

    return output_text.strip()


# =========================
# تشغيل النظام
# =========================

print("====================================")
print("📰 نظام الأخبار - مرحلة التحليل")
print("====================================")

news = get_news()

print(f"\n✅ تم جلب {len(news)} خبرًا")

if not news:
    print("❌ لم يتم العثور على أخبار")
    raise SystemExit

result = analyze_news(news)

if result:
    print("\n====================================")
    print("🤖 الأخبار التي اختارها الذكاء الاصطناعي")
    print("====================================")
    print(result)

print("\n====================================")
print("✅ انتهى الاختبار")
print("⚠️ لم يتم النشر في تيليغرام")
print("====================================")
