import os
import re
import json
import hashlib
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests
import feedparser

from sources import SOURCES


OPENAI_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = "@MH999R"

MAX_NEWS_PER_SOURCE = 8
MAX_POSTS_PER_RUN = 5
MAX_AGE_HOURS = 12

SEEN_FILE = "seen_news.json"
MAX_SEEN_EVENTS = 2500


IRAN_US = [
    "إيران", "الإيراني", "الإيرانية", "طهران",
    "أمريكا", "الولايات المتحدة", "واشنطن", "ترامب",
    "الحرس الثوري", "البنتاغون", "البيت الأبيض",
    "مضيق هرمز", "هرمز", "صاروخ", "صواريخ",
    "مسيرة", "مسيّرة", "ضربة", "هجوم", "قصف",
    "غارات", "مفاوضات", "هدنة", "عقوبات", "نووي",
    "منشأة نووية", "قاعدة أمريكية", "القواعد الأمريكية",
    "القوات الأمريكية", "إسرائيل"
]

POLITICAL = [
    "حكومة", "رئيس", "رئاسة", "برلمان", "انتخابات", "وزير",
    "وزارة", "حزب", "كتلة", "سياسي", "مفاوضات", "اتفاق",
    "عقوبات", "أزمة", "حرب", "هجوم", "ضربة", "قصف",
    "صاروخ", "مسيّرة", "هدنة", "دبلوماسي", "أمم المتحدة",
    "مجلس الأمن", "واشنطن", "إيران", "العراق", "السعودية",
    "اليمن", "سوريا", "لبنان", "غزة", "فلسطين", "روسيا",
    "أوكرانيا", "الصين"
]

BREAKING = [
    "عاجل", "الآن", "هجوم", "ضربة", "قصف", "استهداف",
    "مقتل", "اغتيال", "انفجار", "صاروخ", "صواريخ",
    "مسيرة", "مسيّرة", "إطلاق نار", "اشتباك", "اعتراض",
    "سقوط", "تطور", "تصعيد", "طوارئ"
]

ARABIC_STOP = {
    "من", "في", "على", "الى", "إلى", "عن", "مع", "هذا", "هذه",
    "ذلك", "تلك", "بعد", "قبل", "خلال", "بشأن", "حول", "ان",
    "إن", "تم", "قد", "وقال", "وقالت", "واكد", "وأكد", "مصادر",
    "مصدر", "اليوم", "غدا", "غداً", "الان", "الآن", "التي",
    "الذي", "الذين", "كما", "بين", "لدى", "لـ", "فيما", "أنه",
    "إنه", "كانت", "كان", "يكون", "يتم", "وسط", "نحو", "أمام",
    "ضمن", "عبر", "وفق", "بسبب", "أثناء", "أمس", "غدًا"
}

GENERIC_WORDS = {
    "خبر", "أخبار", "آخر", "اخر", "الجديد", "الجديدة", "تفاصيل",
    "تطورات", "تصريحات", "يعلن", "تعلن", "اعلن", "أعلن", "قال",
    "تقول", "بحسب", "مصدر", "مصادر", "صحيفة", "وكالة", "اليوم"
}


session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)"
})


def norm(text):
    text = (text or "").lower()

    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)

    text = (
        text.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ٱ", "ا")
            .replace("ة", "ه")
            .replace("ى", "ي")
    )

    text = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s]", " ", text)

    return re.sub(r"\s+", " ", text).strip()


def words(text):
    result = set()

    for word in norm(text).split():
        if len(word) <= 2:
            continue

        if word in ARABIC_STOP:
            continue

        if word in GENERIC_WORDS:
            continue

        result.add(word)

    return result


def similarity(a, b):
    a_norm = norm(a)
    b_norm = norm(b)

    if not a_norm or not b_norm:
        return 0.0

    seq = SequenceMatcher(None, a_norm, b_norm).ratio()

    aw = words(a_norm)
    bw = words(b_norm)

    if not aw or not bw:
        overlap = 0.0
    else:
        overlap = len(aw & bw) / len(aw | bw)

    return (seq * 0.45) + (overlap * 0.55)


def source_domain(source):
    website = (source.get("website") or "").strip()

    if not website:
        return ""

    try:
        host = urlparse(website).netloc.lower()
    except Exception:
        host = website.lower()

    return host.removeprefix("www.")


def family(source):
    domain = source_domain(source)

    aliases = {
        "alhurra.com": "alhurra",
        "alhurra-iraq.com": "alhurra",

        "alarabiya.net": "alarabiya",
        "alhadath.net": "alarabiya",

        "aljazeera.net": "aljazeera",

        "reuters.com": "reuters",

        "bbc.com": "bbc",
        "bbc.co.uk": "bbc",

        "skynewsarabia.com": "skynewsarabia",
    }

    if domain in aliases:
        return aliases[domain]

    for key, value in aliases.items():
        if domain.endswith("." + key):
            return value

    return domain or norm(source.get("name", ""))


def article_id(article):
    raw = "|".join([
        article.get("family", ""),
        article.get("title", ""),
        article.get("link", "")
    ])

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def event_text(article):
    return (
        article.get("title", "") +
        " " +
        article.get("summary", "")
    ).strip()


def event_hash(text):
    normalized = " ".join(
        sorted(words(text))
    )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def load_seen():

    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            data = json.load(f)

    except Exception:
        return {
            "ids": set(),
            "events": []
        }

    if isinstance(data, list):
        return {
            "ids": set(data),
            "events": []
        }

    if not isinstance(data, dict):
        return {
            "ids": set(),
            "events": []
        }

    ids = set(data.get("ids", []))
    events = data.get("events", [])

    if not isinstance(events, list):
        events = []

    clean_events = []

    for item in events:
        if isinstance(item, dict) and item.get("title"):
            clean_events.append(item)

    return {
        "ids": ids,
        "events": clean_events
    }


def save_seen(seen):

    data = {
        "version": 2,
        "ids": list(seen["ids"])[-5000:],
        "events": seen["events"][-MAX_SEEN_EVENTS:]
    }

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def already_seen(article, seen):

    aid = article_id(article)

    if aid in seen["ids"]:
        return True

    candidate = event_text(article)

    for old in seen["events"]:

        old_title = old.get("title", "")
        old_text = old.get("text", old_title)

        score_title = similarity(
            article.get("title", ""),
            old_title
        )

        score_full = similarity(
            candidate,
            old_text
        )

        if score_title >= 0.84:
            return True

        if score_full >= 0.82:
            return True

        common = words(candidate) & words(old_text)

        if len(common) >= 4 and score_full >= 0.68:
            return True

    return False


def remember_group(group, final_text, seen):

    for article in group:
        seen["ids"].add(
            article_id(article)
        )

    clean_final = re.sub(
        r"^🔴\s*",
        "",
        final_text
    ).strip()

    seen["events"].append({
        "hash": event_hash(clean_final),
        "title": clean_final,
        "text": clean_final,
        "time": datetime.now(
            timezone.utc
        ).isoformat()
    })

    seen["ids"] = set(
        list(seen["ids"])[-5000:]
    )

    seen["events"] = seen["events"][
        -MAX_SEEN_EVENTS:
    ]


def published_time(entry):

    parsed = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
        or entry.get("created_parsed")
    )

    if parsed:

        try:
            import calendar

            return datetime.fromtimestamp(
                calendar.timegm(parsed),
                tz=timezone.utc
            )

        except Exception:
            pass

    return None


def priority(article):

    text = norm(
        event_text(article)
    )

    score = 0

    for key in IRAN_US:
        if norm(key) in text:
            score += 8

    for key in POLITICAL:
        if norm(key) in text:
            score += 2

    for key in BREAKING:
        if norm(key) in text:
            score += 5

    if article.get("published_at"):

        age_minutes = max(
            0,
            (
                datetime.now(timezone.utc)
                - article["published_at"]
            ).total_seconds() / 60
        )

        score += max(
            0,
            20 - int(age_minutes / 10)
        )

    return score


def is_political(article):

    text = norm(
        event_text(article)
    )

    political_hits = sum(
        1
        for key in POLITICAL
        if norm(key) in text
    )

    iran_us_hits = sum(
        1
        for key in IRAN_US
        if norm(key) in text
    )

    return (
        political_hits >= 1
        or iran_us_hits >= 1
    )


def fetch_news():

    result = []

    rss_sources = [
        s for s in SOURCES
        if s.get("feed")
    ]

    print(
        f"📚 إجمالي المصادر التي سيحاول النظام قراءتها: "
        f"{len(rss_sources)}"
    )

    now = datetime.now(timezone.utc)

    cutoff = (
        now -
        timedelta(hours=MAX_AGE_HOURS)
    )

    for source in rss_sources:

        try:

            feed = feedparser.parse(
                source["feed"]
            )

            if getattr(
                feed,
                "bozo",
                False
            ):
                print(
                    f"⚠️ RSS غير مستقر: "
                    f"{source['name']}"
                )

            count = 0

            for entry in feed.entries[
                :MAX_NEWS_PER_SOURCE
            ]:

                title = (
                    entry.get("title") or ""
                ).strip()

                if not title:
                    continue

                published_at = published_time(
                    entry
                )

                if (
                    published_at
                    and published_at < cutoff
                ):
                    continue

                article = {
                    "source": source["name"],
                    "family": family(source),
                    "country": source.get(
                        "country",
                        ""
                    ),
                    "type": source.get(
                        "type",
                        "news"
                    ),
                    "website": source.get(
                        "website",
                        ""
                    ),
                    "title": title,
                    "summary": (
                        entry.get(
                            "summary"
                        ) or ""
                    ).strip(),
                    "link": (
                        entry.get(
                            "link"
                        ) or ""
                    ).strip(),
                    "published_at":
                        published_at
                }

                if not is_political(
                    article
                ):
                    continue

                article["_id"] = article_id(
                    article
                )

                result.append(article)

                count += 1

            print(
                f"🔎 {source['name']}: "
                f"{count} خبر سياسي حديث"
            )

        except Exception as exc:

            print(
                f"❌ {source.get('name', 'مصدر')}: "
                f"{exc}"
            )

    return result


def same_event(a, b):

    if a["family"] == b["family"]:
        return False

    title_score = similarity(
        a["title"],
        b["title"]
    )

    full_score = similarity(
        event_text(a),
        event_text(b)
    )

    common = (
        words(event_text(a))
        &
        words(event_text(b))
    )

    if (
        title_score >= 0.84
        or
        full_score >= 0.84
    ):
        return True

    event_words = {
        "ايران", "ايراني",
        "امريكا", "امريكي",
        "واشنطن", "طهران",
        "ترامب", "اسرائيل",
        "اليمن", "الحوثيين",
        "غزه", "لبنان",
        "العراق", "السعوديه",
        "هجوم", "ضربه", "قصف",
        "صاروخ", "صواريخ",
        "مسييره", "مفاوضات",
        "هدنه", "عقوبات",
        "نووي", "هرمز",
        "حرس", "ثوري",
        "قاعدة", "قوات",
        "اسرائيلي"
    }

    shared_event = (
        common &
        event_words
    )

    if (
        full_score >= 0.70
        and
        len(shared_event) >= 3
    ):
        return True

    if (
        title_score >= 0.72
        and
        len(common) >= 3
    ):
        return True

    return False


def group_news(news):

    ordered = sorted(
        news,
        key=priority,
        reverse=True
    )

    groups = []
    used = set()

    for i, article in enumerate(
        ordered
    ):

        if i in used:
            continue

        group = [article]

        used.add(i)

        for j in range(
            i + 1,
            len(ordered)
        ):

            if j in used:
                continue

            other = ordered[j]

            if same_event(
                article,
                other
            ):

                group.append(other)
                used.add(j)

        groups.append(group)

    return groups


def group_priority(group):

    return max(
        priority(article)
        for article in group
    )


def group_countries(group):

    return {
        a.get("country", "")
        for a in group
        if a.get("country")
    }


def diversify_groups(groups):

    remaining = list(groups)

    selected = []

    used_families = set()

    country_counts = {
        "Iraq": 0,
        "Arab": 0,
        "World": 0
    }

    while (
        remaining
        and
        len(selected) < MAX_POSTS_PER_RUN
    ):

        best_index = None
        best_score = None

        for idx, group in enumerate(
            remaining
        ):

            families = {
                a["family"]
                for a in group
            }

            if len(families) < 2:
                continue

            if families & used_families:
                continue

            countries = group_countries(
                group
            )

            score = float(
                group_priority(group)
            )

            for country in countries:

                if country in country_counts:

                    if country_counts[
                        country
                    ] == 0:

                        score += 7

                    elif country_counts[
                        country
                    ] >= 2:

                        score -= 8

            joined = norm(
                " ".join(
                    a["title"]
                    for a in group
                )
            )

            if any(
                norm(k) in joined
                for k in IRAN_US
            ):
                score += 12

            if (
                best_score is None
                or
                score > best_score
            ):

                best_score = score
                best_index = idx

        if best_index is None:
            break

        group = remaining.pop(
            best_index
        )

        selected.append(group)

        for article in group:
            used_families.add(
                article["family"]
            )

        for country in group_countries(
            group
        ):

            if country in country_counts:
                country_counts[
                    country
                ] += 1

    return selected


def openai_text(data):

    if data.get("output_text"):
        return data[
            "output_text"
        ].strip()

    output = []

    for item in data.get(
        "output",
        []
    ):

        if item.get(
            "type"
        ) != "message":
            continue

        for content in item.get(
            "content",
            []
        ):

            if content.get(
                "type"
            ) == "output_text":

                text = content.get(
                    "text"
                )

                if text:
                    output.append(text)

    return (
        "\n".join(output).strip()
        if output
        else None
    )


def openai_call(
    prompt,
    max_tokens=300
):

    try:

        response = session.post(
            "https://api.openai.com/v1/responses",

            headers={
                "Authorization":
                    f"Bearer {OPENAI_KEY}",
                "Content-Type":
                    "application/json"
            },

            json={
                "model": "gpt-5.6-luna",
                "input": prompt,
                "max_output_tokens":
                    max_tokens
            },

            timeout=60
        )

        print(
            "🤖 OpenAI Status:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                response.text
            )

            return None

        return openai_text(
            response.json()
        )

    except Exception as exc:

        print(
            "❌ OpenAI:",
            exc
        )

        return None


def verify_event(group):

    families = {
        a["family"]
        for a in group
    }

    if len(families) < 2:
        return False

    text = "\n\n".join(
        f"المؤسسة: {a['source']}\n"
        f"الدولة/الفئة: {a['country']}\n"
        f"العنوان: {a['title']}\n"
        f"التفاصيل: {a['summary']}"
        for a in group
    )

    prompt = f"""
أنت مدقق أخبار سياسية.

تحقق بدقة هل المصادر التالية تؤكد "الواقعة نفسها" أم أنها تتحدث عن وقائع مختلفة داخل الموضوع نفسه.

{text}

القواعد الصارمة:
- لا تدمج خبرين مختلفين لمجرد أنهما عن إيران أو أمريكا أو العراق أو اليمن أو السعودية.
- يجب أن تكون الواقعة الأساسية نفسها: نفس الحدث أو الضربة أو القرار أو التصريح أو الاعتقال أو المفاوضات ونحو ذلك.
- إذا كان هناك اختلاف جوهري في الحدث، أجب NO.
- إذا كانت المصادر تؤكد الواقعة نفسها فعلاً، أجب YES.
- لا تعتبر تكرار المؤسسة نفسها مصدراً مستقلاً.
- أجب فقط YES أو NO.
""".strip()

    # مهم: الحد الأدنى الحالي للـ API هو 16.
    answer = openai_call(
        prompt,
        max_tokens=16
    )

    print(
        "🔍 تحقق الحدث:",
        answer
    )

    if not answer:
        return False

    return (
        answer.strip()
        .upper()
        == "YES"
    )


def clean_final(text):

    text = (
        text or ""
    ).strip()

    text = re.sub(
        r"^```.*?\n",
        "",
        text,
        flags=re.S
    )

    text = re.sub(
        r"\n```$",
        "",
        text,
        flags=re.S
    )

    text = re.sub(
        r"^🔴\s*المصدر\s*:\s*",
        "🔴 ",
        text,
        flags=re.I
    )

    text = text.replace(
        "\n\n",
        "\n"
    ).strip()

    return text


def analyze(group):

    if not verify_event(group):
        return None

    source_names = list(
        dict.fromkeys(
            a["source"]
            for a in group
        )
    )

    source_text = "، ".join(
        source_names
    )

    news_text = "\n\n".join(
        f"المصدر: {a['source']}\n"
        f"العنوان: {a['title']}\n"
        f"التفاصيل: {a['summary']}"
        for a in group
    )

    prompt = f"""
أنت محرر أخبار سياسية عاجلة.

اكتب منشوراً واحداً فقط عن "الواقعة نفسها" التي تؤكدها المصادر أدناه.

المصادر المستقلة:
{source_text}

المعلومات:
{news_text}

التعليمات الإلزامية:
- انشر فقط إذا كان الخبر مهماً سياسياً أو عاجلاً.
- أولوية قصوى لأي تطور حقيقي وجديد بين إيران والولايات المتحدة.
- لا تدمج أحداثاً مختلفة في منشور واحد.
- لا تضف أي معلومة غير موجودة في المصادر.
- حافظ على الأسماء والأرقام والتواريخ.
- لا تستخدم كلمة "المصدر".
- لا تضع روابط.
- لا تضع هاشتاغات.
- ابدأ دائماً بـ 🔴.
- بعد 🔴 اكتب أسماء المؤسسات التي تؤكد نفس الواقعة مباشرة.
- إذا تعددت المؤسسات، افصل بينها بالفاصلة العربية "،" وليس "و".
- لا تضف مقدمة أو تعليقاً أو تفسيراً.

الصيغة الوحيدة:
🔴 اسم المصدر، اسم المصدر: نص الخبر

إذا لم يكن الخبر مهماً:
SKIP
""".strip()

    result = openai_call(
        prompt,
        max_tokens=300
    )

    if not result:
        return None

    result = clean_final(
        result
    )

    if result.upper() == "SKIP":
        return None

    if not result.startswith("🔴"):
        result = "🔴 " + result

    return result


def send(message):

    try:

        response = session.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",

            data={
                "chat_id": CHANNEL,
                "text": message,
                "disable_web_page_preview":
                    True
            },

            timeout=30
        )

        print(
            "📨 Telegram Status:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                response.text
            )

        return (
            response.status_code
            == 200
        )

    except Exception as exc:

        print(
            "❌ Telegram:",
            exc
        )

        return False


def main():

    print("=" * 70)

    print(
        "📰 نظام الأخبار السياسية العاجلة - الإصدار الجديد"
    )

    print(
        "⚡ أولوية قصوى: إيران 🇮🇷 ↔ أمريكا 🇺🇸"
    )

    print(
        "🌍 العراق + العالم العربي + العالم"
    )

    print(
        f"📢 الحد الأقصى للنشر في التشغيل: "
        f"{MAX_POSTS_PER_RUN}"
    )

    print(
        f"⏱️ الأخبار الحديثة ضمن آخر: "
        f"{MAX_AGE_HOURS} ساعة"
    )

    print("=" * 70)

    seen = load_seen()

    all_news = fetch_news()

    print(
        f"\n📰 مجموع الأخبار السياسية الحديثة المقروءة: "
        f"{len(all_news)}"
    )

    fresh = [
        article
        for article in all_news
        if not already_seen(
            article,
            seen
        )
    ]

    print(
        f"🆕 بعد منع التكرار: "
        f"{len(fresh)}"
    )

    if not fresh:

        print(
            "ℹ️ لا توجد أخبار جديدة قابلة للنشر."
        )

        save_seen(seen)

        return

    groups = group_news(
        fresh
    )

    print(
        f"🧩 عدد مجموعات الأحداث: "
        f"{len(groups)}"
    )

    groups = diversify_groups(
        groups
    )

    print(
        f"🎯 المجموعات المختارة للنشر/التحقق: "
        f"{len(groups)}"
    )

    published = 0

    published_fingerprints = []

    for index, group in enumerate(
        groups,
        start=1
    ):

        if published >= MAX_POSTS_PER_RUN:
            break

        print("\n" + "=" * 70)

        print(
            f"🔎 المجموعة {index}"
        )

        for article in group:

            print(
                f"• [{article['country']}] "
                f"{article['source']} | "
                f"{article['title']}"
            )

        result = analyze(
            group
        )

        if not result:

            print(
                "⏭️ تم تجاهل المجموعة: "
                "غير مؤكدة أو غير مهمة."
            )

            continue

        result_body = re.sub(
            r"^🔴\s*",
            "",
            result
        ).strip()

        duplicate_in_run = any(
            similarity(
                result_body,
                old
            ) >= 0.78
            for old in published_fingerprints
        )

        if duplicate_in_run:

            print(
                "⛔ تكرار داخل التشغيل نفسه — لن يُنشر."
            )

            continue

        print(
            "\n📢 الخبر النهائي:"
        )

        print(
            result
        )

        if send(result):

            published += 1

            published_fingerprints.append(
                result_body
            )

            remember_group(
                group,
                result,
                seen
            )

            save_seen(
                seen
            )

            print(
                f"✅ تم نشر الخبر "
                f"{published} "
                f"من أصل "
                f"{MAX_POSTS_PER_RUN}"
            )

        else:

            print(
                "❌ فشل الإرسال — "
                "لم نضع الخبر في سجل المنشور."
            )

    save_seen(
        seen
    )

    print("\n" + "=" * 70)

    print(
        f"🎉 انتهى التشغيل. "
        f"عدد المنشورات الناجحة: "
        f"{published}"
    )

    print(
        "💾 سجل التكرار محفوظ."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
