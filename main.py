import os
import re
import requests
import feedparser

from difflib import SequenceMatcher

from sources import SOURCES


# =========================================================
# الإعدادات
# =========================================================

OPENAI_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

CHANNEL = "@MH999R"

# أقصى عدد أخبار يتم جلبها من كل مصدر
MAX_NEWS_PER_SOURCE = 10

# أقصى عدد أخبار يتم نشرها في كل تشغيل
MAX_POSTS_PER_RUN = 5


# =========================================================
# جلب الأخبار من المصادر
# =========================================================

def fetch_news():

    all_news = []

    rss_sources = [
        source for source in SOURCES
        if source.get("feed")
    ]

    print(f"\n📚 عدد مصادر RSS الفعالة: {len(rss_sources)}")

    for source_info in rss_sources:

        source_name = source_info["name"]
        url = source_info["feed"]

        print(f"\n🔎 جلب أخبار من: {source_name}")

        try:

            feed = feedparser.parse(url)

            count = 0

            for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "").strip()

                if not title:
                    continue

                all_news.append({
                    "source": source_name,
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
# تنظيف النص
# =========================================================

def normalize_text(text):

    text = text.lower()

    text = re.sub(
        r"https?://\S+",
        "",
        text
    )

    text = re.sub(
        r"[^a-zA-Z0-9\u0600-\u06FF\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# مقارنة الأخبار
# =========================================================

def similarity(a, b):

    a = normalize_text(a)
    b = normalize_text(b)

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


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

        for j in range(
            i + 1,
            len(news)
        ):

            if j in used:
                continue

            other = news[j]

            score = similarity(
                article["title"],
                other["title"]
            )

            if score >= 0.55:

                if other["source"] != article["source"]:

                    group.append(other)

                    used.add(j)

        groups.append(group)

    print(
        f"🔗 مجموع مجموعات الأخبار: {len(groups)}"
    )

    return groups


# =========================================================
# التحقق من تعدد المصادر
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
# استخراج نص OpenAI
# =========================================================

def extract_openai_text(data):

    if data.get("output_text"):

        return data["output_text"].strip()

    texts = []

    for item in data.get(
        "output",
        []
    ):

        if item.get("type") != "message":
            continue

        for content in item.get(
            "content",
            []
        ):

            if content.get(
                "type"
            ) == "output_text":

                text = content.get(
                    "text",
                    ""
                )

                if text:
                    texts.append(text)

    if texts:

        return "\n".join(
            texts
        ).strip()

    return None


# =========================================================
# تحليل الخبر بواسطة OpenAI
# =========================================================

def analyze_news(group):

    sources = list(
        dict.fromkeys(
            article["source"]
            for article in group
        )
    )

    # استخدام الفاصلة العربية بين المصادر
    source_text = "، ".join(
        sources
    )

    news_text = ""

    for article in group:

        news_text += (
            f"\nاسم المصدر: {article['source']}\n"
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
- الحكومة العراقية.
- البرلمان.
- الانتخابات.
- الرئاسة.
- الوزراء والمسؤولين.
- الأحزاب والكتل السياسية.
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

10. إذا كانت هناك عدة مصادر، افصل بينها بالفاصلة العربية:
،

11. ممنوع تماماً كتابة كلمة:
المصدر

12. ممنوع كتابة أي رابط.

13. ممنوع إضافة هاشتاغات.

14. ممنوع إضافة مقدمة أو شرح خارج الخبر.

15. لا تستخدم كلمة "و" للفصل بين أسماء المصادر.

16. إذا أكدت عدة مصادر الخبر، اذكر أسماء المصادر معاً.

17. لا تنشر الخبر إذا كان مجرد خبر عادي أو غير مؤثر.

مثال صحيح:

🔴 السومرية، الجزيرة: أعلنت الحكومة قراراً جديداً بشأن...

مثال خاطئ:

🔴 المصدر: السومرية والجزيرة: أعلنت الحكومة قراراً جديداً بشأن...

مثال خاطئ:

🔴 السومرية والجزيرة: أعلنت الحكومة قراراً جديداً بشأن...

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

            print(
                response.text
            )

            return None

        data = response.json()

        text = extract_openai_text(
            data
        )

        if not text:

            print(
                "❌ لم يتم الحصول على نص من OpenAI"
            )

            return None

        print(
            "✅ تم استخراج رد OpenAI بنجاح"
        )

        text = text.strip()

        if text.upper() == "SKIP":

            print(
                "⏭️ الخبر غير مهم سياسياً"
            )

            return None

        # =================================================
        # حماية إضافية من كتابة "المصدر"
        # =================================================

        text = text.replace(
            "🔴 المصدر:",
            "🔴"
        )

        text = text.replace(
            "🔴المصدر:",
            "🔴"
        )

        text = text.replace(
            "المصدر:",
            ""
        )

        # =================================================
        # تنظيف الفواصل بين المصادر
        # =================================================

        text = text.replace(
            " والجزيرة:",
            "، الجزيرة:"
        )

        text = text.replace(
            " وBBC:",
            "، BBC:"
        )

        return text.strip()

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

        print(
            response.text
        )

        if response.status_code == 200:

            print(
                "✅ تم إرسال الخبر إلى تيليغرام بنجاح"
            )

            return True

        print(
            "❌ فشل إرسال الخبر إلى تيليغرام"
        )

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

    print("=" * 55)
    print("📰 نظام الأخبار السياسية")
    print("=" * 55)

    print(
        f"📢 الحد الأقصى للنشر في هذا التشغيل: "
        f"{MAX_POSTS_PER_RUN}"
    )

    # =====================================================
    # جلب الأخبار
    # =====================================================

    news = fetch_news()

    if not news:

        print(
            "❌ لم يتم العثور على أخبار"
        )

        return

    # =====================================================
    # تجميع الأخبار المتشابهة
    # =====================================================

    groups = group_news(
        news
    )

    # =====================================================
    # التحقق من الأخبار المؤكدة
    # =====================================================

    verified = verified_news(
        groups
    )

    if not verified:

        print(
            "❌ لا توجد أخبار مؤكدة من مصدرين."
        )

        return

    # =====================================================
    # تحليل ونشر الأخبار
    # =====================================================

    published = 0

    for group in verified:

        # التوقف بعد الوصول إلى الحد الأقصى
        if published >= MAX_POSTS_PER_RUN:

            print(
                f"\n🛑 تم الوصول إلى الحد الأقصى "
                f"({MAX_POSTS_PER_RUN} أخبار)"
            )

            break

        print(
            "\n" + "=" * 55
        )

        print(
            "📰 خبر مؤكد من عدة مصادر"
        )

        for article in group:

            print(
                f"• {article['source']}: "
                f"{article['title']}"
            )

        # =================================================
        # تحليل الخبر
        # =================================================

        result = analyze_news(
            group
        )

        if not result:

            continue

        print(
            "\n📢 الخبر النهائي:"
        )

        print(
            result
        )

        # =================================================
        # إرسال إلى Telegram
        # =================================================

        success = send_to_telegram(
            result
        )

        if success:

            published += 1

            print(
                f"✅ تم نشر الخبر رقم "
                f"{published} من أصل "
                f"{MAX_POSTS_PER_RUN}"
            )

    # =====================================================
    # النتيجة النهائية
    # =====================================================

    if published == 0:

        print(
            "\n⏭️ لم يتم نشر أي خبر سياسي مهم."
        )

    else:

        print(
            "\n" + "=" * 55
        )

        print(
            f"🎉 انتهى التشغيل."
        )

        print(
            f"📰 عدد الأخبار المنشورة: "
            f"{published}"
        )

        print(
            "=" * 55
        )


# =========================================================
# بدء البرنامج
# =========================================================

if __name__ == "__main__":
    main()
