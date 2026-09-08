import os
import requests
import feedparser
import json
import re
from difflib import SequenceMatcher

OPENAI_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHANNEL = "@MH999R"

# =========================
# مصادر الأخبار
# =========================

FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Iraq": "https://feeds.bbci.co.uk/news/topics/ce1qrvle14rt/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Reuters": "https://news.google.com/rss/search?q=site%3Areuters.com%2Fworld&hl=en-US&gl=US&ceid=US%3Aen",
}

MAX_NEWS_PER_SOURCE = 10


# =========================
# تنظيف النص
# =========================

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================
# جلب الأخبار
# =========================

def get_news():

    news = []

    for source, feed_url in FEEDS.items():

        print(f"\n🔎 جلب أخبار من: {source}")

        try:
            feed = feedparser.parse(feed_url)

            count = 0

            for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()
                link = entry.get("link", "").strip()

                if not title:
                    continue

                news.append({
                    "source": source,
                    "title": title,
                    "summary": summary,
                    "link": link
                })

                count += 1

            print(f"   ✅ تم جلب {count} خبر")

        except Exception as e:
            print(f"   ❌ خطأ في المصدر: {e}")

    return news


# =========================
# مقارنة الأخبار
# =========================

def similarity(text1, text2):

    return SequenceMatcher(
        None,
        normalize_text(text1),
        normalize_text(text2)
    ).ratio()


# =========================
# تجميع الأخبار المتشابهة
# =========================

def group_news(news):

    groups = []

    for article in news:

        added = False

        for group in groups:

            main_article = group[0]

            score = similarity(
                article["title"],
                main_article["title"]
            )

            if score >= 0.55:

                group.append(article)
                added = True
                break

        if not added:
            groups.append([article])

    return groups


# =========================
# التحقق من تعدد المصادر
# =========================

def verified_groups(groups):

    verified = []

    for group in groups:

        sources = set(
            article["source"]
            for article in group
        )

        if len(sources) >= 2:

            verified.append({
                "articles": group,
                "sources": list(sources)
            })

    return verified


# =========================
# استخراج نص OpenAI
# =========================

def extract_openai_text(data):

    # الطريقة الأولى
    if data.get("output_text"):
        return data["output_text"].strip()

    # الطريقة الثانية
    texts = []

    for item in data.get("output", []):

        if item.get("type") != "message":
            continue

        for content in item.get("content", []):

            if content.get("type") == "output_text":

                text = content.get("text", "")

                if text:
                    texts.append(text)

    if texts:
        return "\n".join(texts).strip()

    return None


# =========================
# تحليل الذكاء الاصطناعي
# =========================

def analyze_news(verified):

    stories = []

    for item in verified:

        articles_text = []

        for article in item["articles"]:

            articles_text.append({
                "source": article["source"],
                "title": article["title"],
                "summary": article["summary"]
            })

        stories.append({
            "sources": item["sources"],
            "articles": articles_text
        })

    news_text = json.dumps(
        stories,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
أنت محرر أخبار محترف ومسؤول عن قناة إخبارية.

حلل الأخبار التي تم التحقق منها من أكثر من مصدر.

القواعد الصارمة:

1. العراق + العالم فقط.
2. اختر الأخبار المهمة فقط.
3. الأولوية للأخبار السياسية والأمنية والاقتصادية والإنسانية والدولية.
4. تجاهل الأخبار الخفيفة والترفيهية والرياضية.
5. لا تكرر نفس الحدث.
6. لا تخترع أي معلومة.
7. لا تضف أي رقم غير موجود في المصادر.
8. حافظ على الأرقام والمعلومات المهمة.
9. استخدم المعلومات التي تؤكدها المصادر فقط.
10. إذا كان هناك اختلاف بين المصادر، لا تحسم المعلومة من عندك.
11. لا تنشر خبراً غير واضح.
12. لا تضع روابط.
13. يجب أن يبدأ كل خبر بـ 🔴.
14. اذكر المصدر في بداية الخبر.
15. اجعل الخبر مختصراً وواضحاً.
16. لا تذكر أنه تم التحقق من الخبر.
17. لا تكتب مقدمة أو شرحاً خارج الأخبار.

صيغة النشر:

🔴 المصدر: نص الخبر المختصر والواضح.

أعد فقط الأخبار التي تستحق النشر.

الأخبار المتحقق منها:

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

    print("\n🤖 OpenAI Status:", response.status_code)

    if response.status_code != 200:

        print("❌ فشل OpenAI")
        print(response.text)

        return None

    data = response.json()

    # استخراج النص بالطريقة الصحيحة
    output_text = extract_openai_text(data)

    if not output_text:

        print("❌ لم يتم العثور على النص داخل رد OpenAI")

        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            )
        )

        return None

    print("✅ تم استخراج رد OpenAI بنجاح")

    return output_text


# =========================
# إرسال إلى تيليغرام
# =========================

def send_to_telegram(message):

    telegram_url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHANNEL,
        "text": message
    }

    response = requests.post(
        telegram_url,
        data=data,
        timeout=30
    )

    print("\n📨 Telegram Status:", response.status_code)
    print(response.text)

    if response.status_code == 200:

        print("✅ تم إرسال الخبر إلى تيليغرام بنجاح")

        return True

    print("❌ فشل إرسال الخبر إلى تيليغرام")

    return False


# =========================
# تشغيل النظام
# =========================

print("====================================")
print("📰 نظام الأخبار - اختبار النشر")
print("====================================")

news = get_news()

print(f"\n📊 مجموع الأخبار: {len(news)}")

if not news:

    print("❌ لم يتم العثور على أخبار")
    raise SystemExit


# تجميع الأخبار

groups = group_news(news)

print(
    f"🔗 مجموع مجموعات الأخبار: {len(groups)}"
)


# التحقق

verified = verified_groups(groups)

print(
    f"✅ الأخبار التي لديها مصدران أو أكثر: {len(verified)}"
)


if not verified:

    print("⚠️ لا توجد أخبار مؤكدة من أكثر من مصدر.")
    print("⚠️ لن يتم النشر.")

    raise SystemExit


# تحليل OpenAI

result = analyze_news(verified)


if not result:

    print("❌ لم ينتج الذكاء الاصطناعي أي خبر.")

    raise SystemExit


print("\n====================================")
print("🤖 الأخبار المختارة")
print("====================================")

print(result)


# =========================
# النشر في تيليغرام
# =========================

print("\n====================================")
print("📨 محاولة النشر في تيليغرام")
print("====================================")

send_to_telegram(result)


print("\n====================================")
print("✅ انتهى الاختبار")
print("====================================")
