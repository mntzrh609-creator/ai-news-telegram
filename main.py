import os
import re
import requests
import feedparser

from difflib import SequenceMatcher


# =========================================================
# الإعدادات
# =========================================================

OPENAI_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHANNEL = "@MH999R"

# مصادر الأخبار
FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",

    "BBC Iraq": "https://feeds.bbci.co.uk/news/topics/ce1qrvle14rt/rss.xml",

    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",

    "Reuters": (
        "https://news.google.com/rss/search?"
        "q=site%3Areuters.com%2Fworld"
        "&hl=en-US&gl=US&ceid=US%3Aen"
    ),
}

MAX_NEWS_PER_SOURCE = 10


# =========================================================
# جلب الأخبار
# =========================================================

def fetch_news():

    all_news = []

    for source, url in FEEDS.items():

        print(f"\n🔎 جلب أخبار من: {source}")

        try:

            feed = feedparser.parse(url)

            count = 0

            for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()

                if not title:
                    continue

                all_news.append({
                    "source": source,
                    "title": title,
                    "summary": summary,
                })

                count += 1

            print(f"   ✅ تم جلب {count} خبر")

        except Exception as e:

            print(f"   ❌ خطأ في المصدر: {e}")

    print(f"\n📊 مجموع الأخبار: {len(all_news)}")

    return all_news


# =========================================================
# تنظيف العناوين
# =========================================================

def normalize_text(text):

    text = text.lower()

    text = re.sub(r"https?://\S+", "", text)

    text = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================================================
# مقارنة الأخبار
# =========================================================

def similarity(a, b):

    a = normalize_text(a)
    b = normalize_text(b)

    return SequenceMatcher(None, a, b).ratio()


# =========================================================
# تجميع الأخبار المتشابهة
# =========================================================

def group_news(news):

    groups = []

    used = set()

    for i, article in enumerate(news):

        if i in used:
            continue

        group = [article]

        used.add(i)

        for j in range(i + 1, len(news)):

            if j in used:
                continue

            other = news[j]

            score = similarity(
                article["title"],
                other["title"]
            )

            # تشابه العناوين
            if score >= 0.55:

                # يجب أن تكون المصادر مختلفة
                if other["source"] != article["source"]:

                    group.append(other)
                    used.add(j)

        groups.append(group)

    print(f"🔗 مجموع مجموعات الأخبار: {len(groups)}")

    return groups


# =========================================================
# استخراج الأخبار التي لديها أكثر من مصدر
# =========================================================

def verified_news(groups):

    verified = []

    for group in groups:

        sources = set(
            article["source"]
            for article in group
        )

        if len(sources) >= 2:

            verified.append(group)

    print(
        f"✅ الأخبار التي لديها مصدران أو أكثر: "
        f"{len(verified)}"
    )

    return verified


# =========================================================
# استخراج نص رد OpenAI
# =========================================================

def extract_openai_text(data):

    if data.get("output_text"):

        return data["output_text"].strip()

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


# =========================================================
# تحليل الأخبار السياسية بواسطة OpenAI
# =========================================================

def analyze_news(group):

    sources = list(
        dict.fromkeys(
            article["source"]
            for article in group
        )
    )

    source_text = " و".join(sources)

    news_text = ""

    for article in group:

        news_text += (
            f"\nالمصدر: {article['source']}\n"
            f"العنوان: {article['title']}\n"
            f"التفاصيل: {article['summary']}\n"
        )

    prompt = f"""
أنت محرر أخبار سياسية محترف.

مهمتك اختيار الخبر السياسي المهم فقط من المعلومات التالية.

المصادر التي أكدت الخبر:
{source_text}

الأخبار:
{news_text}

الشروط الإلزامية:

1. انشر الخبر فقط إذا كان سياسياً ومهماً وله تأثير واضح.

2. الأخبار المقبولة تشمل:
- السياسة العراقية.
- قرارات الحكومة.
- البرلمان.
- الانتخابات.
- الرئاسة.
- الوزراء والمسؤولين.
- العلاقات بين الدول.
- المفاوضات.
- الاتفاقيات السياسية.
- العقوبات.
- الأزمات السياسية.
- الحروب والتطورات السياسية المرتبطة بها.
- القرارات الدولية المهمة.
- التصريحات السياسية المهمة جداً.

3. لا تنشر:
- الأخبار الفنية.
- الرياضية.
- الاقتصادية البسيطة.
- الحوادث العادية.
- الأخبار الاجتماعية.
- أخبار المشاهير.
- الأخبار السياسية الثانوية أو غير المؤثرة.

4. يجب أن يكون الخبر مؤكداً من مصدرين مختلفين على الأقل.

5. لا تضف أي معلومة غير موجودة في المصادر.

6. حافظ على الأرقام والأسماء والتواريخ المهمة.

7. اختصر الخبر بوضوح ومن دون مبالغة.

8. يجب أن يبدأ الخبر دائماً بالرمز:
🔴

9. بعد 🔴 اذكر اسم المصدر أو المصادر مباشرة.

10. ممنوع تماماً كتابة كلمة:
"المصدر"

11. ممنوع كتابة رابط.

12. ممنوع إضافة هاشتاغات.

13. ممنوع إضافة مقدمة أو شرح خارج الخبر.

14. إذا كانت عدة مصادر تؤكد الخبر، اذكر أسماءها معاً.

مثال صحيح:

🔴 BBC World والجزيرة: أعلنت الحكومة قراراً جديداً بشأن...

مثال خاطئ:

🔴 المصدر: BBC World والجزيرة: ...

إذا لم يكن الخبر السياسي مهماً، أجب فقط:
SKIP

إذا كان مهماً، أعد الخبر فقط.
"""

    url = "https://api.openai.com/v1/responses"

    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-5.6-luna",
        "input": prompt,
        "max_output_tokens": 300,
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60,
        )

        print(
            "\n🤖 OpenAI Status:",
            response.status_code
        )

        if response.status_code != 200:

            print(response.text)

            return None

        data = response.json()

        text = extract_openai_text(data)

        if not text:

            print("❌ لم يتم الحصول على نص من OpenAI")

            return None

        print("✅ تم استخراج رد OpenAI بنجاح")

        text = text.strip()

        if text.upper() == "SKIP":

            print("⏭️ الخبر غير مهم سياسياً")

            return None

        # حماية إضافية من كلمة المصدر
        text = text.replace(
            "🔴 المصدر:",
            "🔴"
        )

        return text

    except Exception as e:

        print(
            f"❌ خطأ أثناء الاتصال بـ OpenAI: {e}"
        )

        return None


# =========================================================
# إرسال الخبر إلى Telegram
# =========================================================

def send_to_telegram(message):

    telegram_url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_TOKEN}/sendMessage"
    )

    data = {
        "chat_id": CHANNEL,
        "text": message,
    }

    try:

        response = requests.post(
            telegram_url,
            data=data,
            timeout=30,
        )

        print(
            "\n📨 Telegram Status:",
            response.status_code
        )

        print(response.text)

        if response.status_code == 200:

            print(
                "✅ تم إرسال الخبر إلى تيليغرام بنجاح"
            )

            return True

        print("❌ فشل إرسال الخبر إلى تيليغرام")

        return False

    except Exception as e:

        print(
            f"❌ خطأ في Telegram: {e}"
        )

        return False


# =========================================================
# التشغيل الرئيسي
# =========================================================

def main():

    print("=" * 45)
    print("📰 نظام الأخبار السياسية")
    print("=" * 45)

    # جلب الأخبار
    news = fetch_news()

    if not news:

        print("❌ لم يتم العثور على أخبار")

        return

    # تجميع الأخبار المتشابهة
    groups = group_news(news)

    # التحقق من وجود مصدرين أو أكثر
    verified = verified_news(groups)

    if not verified:

        print(
            "❌ لا توجد أخبار سياسية مؤكدة من مصدرين."
        )

        return

    # تجربة الأخبار المؤكدة
    for group in verified:

        print("\n" + "=" * 45)

        print("📰 خبر مؤكد")

        for article in group:

            print(
                f"• {article['source']}: "
                f"{article['title']}"
            )

        result = analyze_news(group)

        if not result:

            continue

        print("\n📢 الخبر النهائي:")
        print(result)

        # الإرسال إلى Telegram
        send_to_telegram(result)

        # حالياً نرسل خبراً واحداً فقط في كل تشغيل
        break


# =========================================================
# بدء البرنامج
# =========================================================

if __name__ == "__main__":
    main()
