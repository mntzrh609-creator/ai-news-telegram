import os
import re
import json
import hashlib
import calendar
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests
import feedparser

from sources import SOURCES


# =========================================================
# الإعدادات
# =========================================================

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL = "@MH999R"

# النظام يعمل طوال 24 ساعة عن طريق GitHub Actions.
MAX_NEWS_PER_SOURCE = 8

# عدد المنشورات الأقصى في كل تشغيل.
MAX_POSTS_PER_RUN = 5

# الأخبار الأحدث من 24 ساعة فقط.
MAX_AGE_HOURS = 24

# نأخذ أفضل الأخبار قبل مرحلة التحقق.
MAX_CANDIDATES = 60

# سجل الأخبار المنشورة.
SEEN_FILE = "seen_news.json"
MAX_SEEN_EVENTS = 2500

# حالة OpenAI.
OPENAI_STATE_FILE = "openai_state.json"

# لا نرسل طلب OpenAI في كل تشغيل.
OPENAI_COOLDOWN_MINUTES = 10


# =========================================================
# الكلمات
# =========================================================

IRAN_US = [
    "إيران",
    "الإيراني",
    "الإيرانية",
    "طهران",
    "أمريكا",
    "الولايات المتحدة",
    "واشنطن",
    "ترامب",
    "الحرس الثوري",
    "البنتاغون",
    "البيت الأبيض",
    "مضيق هرمز",
    "هرمز",
    "القوات الأمريكية",
    "القواعد الأمريكية",
    "قاعدة أمريكية",
    "إسرائيل",
    "منشأة نووية",
    "نووي",
    "مفاوضات",
    "هدنة",
    "عقوبات",
    "صاروخ",
    "صواريخ",
    "مسيرة",
    "مسيّرة",
    "ضربة",
    "هجوم",
    "قصف",
    "غارات",
]


IRAQ_WORDS = [
    "العراق",
    "العراقي",
    "العراقية",
    "بغداد",
    "النجف",
    "البصرة",
    "نينوى",
    "الأنبار",
    "كربلاء",
    "كركوك",
    "أربيل",
    "السليمانية",
    "دهوك",
    "البرلمان العراقي",
    "الحكومة العراقية",
    "رئيس الوزراء العراقي",
]


WORLD_WORDS = [
    "روسيا",
    "أوكرانيا",
    "الصين",
    "أمريكا",
    "إيران",
    "إسرائيل",
    "فلسطين",
    "غزة",
    "لبنان",
    "سوريا",
    "اليمن",
    "السعودية",
    "مصر",
    "تركيا",
    "الأردن",
    "أوروبا",
    "الناتو",
    "الأمم المتحدة",
    "مجلس الأمن",
]


POLITICAL_WORDS = [
    "حكومة",
    "رئيس",
    "رئاسة",
    "برلمان",
    "انتخابات",
    "وزير",
    "وزارة",
    "حزب",
    "كتلة",
    "سياسي",
    "سياسية",
    "مفاوضات",
    "اتفاق",
    "اتفاقية",
    "عقوبات",
    "أزمة",
    "حرب",
    "هجوم",
    "ضربة",
    "قصف",
    "صاروخ",
    "صواريخ",
    "مسيّرة",
    "مسيرة",
    "هدنة",
    "دبلوماسي",
    "أمم المتحدة",
    "مجلس الأمن",
]


BREAKING_WORDS = [
    "عاجل",
    "الآن",
    "هجوم",
    "ضربة",
    "قصف",
    "استهداف",
    "مقتل",
    "اغتيال",
    "انفجار",
    "صاروخ",
    "صواريخ",
    "مسيرة",
    "مسيّرة",
    "إطلاق نار",
    "اشتباك",
    "اعتراض",
    "سقوط",
    "تصعيد",
    "طوارئ",
    "يهدد",
    "تهديد",
    "تحذير",
]


HIGH_IMPACT_WORDS = [
    "حرب",
    "هجوم",
    "ضربة",
    "قصف",
    "صاروخ",
    "صواريخ",
    "مسيّرة",
    "مسيرة",
    "اغتيال",
    "مقتل",
    "انفجار",
    "اشتباك",
    "تصعيد",
    "هدنة",
    "وقف إطلاق النار",
    "اتفاق",
    "اتفاق تاريخي",
    "عقوبات",
    "فرض عقوبات",
    "انسحاب",
    "إغلاق",
    "مضيق هرمز",
    "منشأة نووية",
    "برنامج نووي",
    "تدخل عسكري",
    "عملية عسكرية",
    "حالة طوارئ",
    "إعلان الحرب",
]


SENIOR_ENTITIES = [
    "ترامب",
    "الرئيس الأمريكي",
    "رئيس الوزراء العراقي",
    "رئيس الجمهورية",
    "المرشد الإيراني",
    "خامنئي",
    "وزير الخارجية الأمريكي",
    "وزير الدفاع الأمريكي",
    "وزير الخارجية الإيراني",
    "الحرس الثوري",
    "البنتاغون",
    "البيت الأبيض",
    "مجلس الأمن",
    "الأمم المتحدة",
    "الناتو",
]


# كلمات تدل غالباً على خبر سياسي روتيني وليس خبراً يستحق النشر العاجل.
ROUTINE_WORDS = [
    "يبحث",
    "بحث",
    "يناقش",
    "ناقش",
    "استقبل",
    "يستقبل",
    "التقى",
    "يلتقي",
    "أعرب عن",
]


GENERIC_WORDS = {
    "خبر",
    "أخبار",
    "آخر",
    "اخر",
    "الجديد",
    "الجديدة",
    "تفاصيل",
    "تطورات",
    "تصريحات",
    "يعلن",
    "تعلن",
    "اعلن",
    "أعلن",
    "قال",
    "تقول",
    "بحسب",
    "مصدر",
    "مصادر",
    "صحيفة",
    "وكالة",
    "اليوم",
}


ARABIC_STOP = {
    "من",
    "في",
    "على",
    "الى",
    "إلى",
    "عن",
    "مع",
    "هذا",
    "هذه",
    "ذلك",
    "تلك",
    "بعد",
    "قبل",
    "خلال",
    "بشأن",
    "حول",
    "ان",
    "إن",
    "تم",
    "قد",
    "وقال",
    "وقالت",
    "واكد",
    "وأكد",
    "مصادر",
    "مصدر",
    "اليوم",
    "غدا",
    "غداً",
    "الان",
    "الآن",
    "التي",
    "الذي",
    "الذين",
    "كما",
    "بين",
    "لدى",
    "فيما",
    "أنه",
    "إنه",
    "كانت",
    "كان",
    "يكون",
    "يتم",
    "وسط",
    "نحو",
    "أمام",
    "ضمن",
    "عبر",
    "وفق",
    "بسبب",
    "أثناء",
    "أمس",
}


# =========================================================
# جلسة HTTP
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/2.0)"
})


# =========================================================
# أدوات النص
# =========================================================

def norm(text):
    text = (text or "").lower()

    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)

    # حذف التشكيل.
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)

    # توحيد الحروف العربية.
    text = (
        text
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ٱ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
    )

    text = re.sub(
        r"[^a-zA-Z0-9\u0600-\u06FF\s]",
        " ",
        text
    )

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

    seq = SequenceMatcher(
        None,
        a_norm,
        b_norm
    ).ratio()

    aw = words(a_norm)
    bw = words(b_norm)

    if not aw or not bw:
        overlap = 0.0
    else:
        overlap = len(aw & bw) / len(aw | bw)

    return (seq * 0.45) + (overlap * 0.55)


# =========================================================
# المصادر والعائلات
# =========================================================

def source_domain(source):
    website = (source.get("website") or "").strip()

    if not website:
        return ""

    try:
        host = urlparse(website).netloc.lower()
    except Exception:
        host = website.lower()

    host = host.removeprefix("www.")

    return host


def family(source):
    domain = source_domain(source)

    aliases = {
        "reuters.com": "reuters",
        "apnews.com": "ap",
        "afp.com": "afp",
        "bbc.com": "bbc",
        "bbc.co.uk": "bbc",
        "cnn.com": "cnn",
        "aljazeera.net": "aljazeera",
        "alarabiya.net": "alarabiya",
        "alhadath.net": "alarabiya",
        "skynewsarabia.com": "skynewsarabia",
        "france24.com": "france24",
        "dw.com": "dw",
        "euronews.com": "euronews",
        "alhurra.com": "alhurra",
        "alhurra-iraq.com": "alhurra",
        "nytimes.com": "nytimes",
        "washingtonpost.com": "washingtonpost",
        "theguardian.com": "guardian",
        "ft.com": "ft",
        "wsj.com": "wsj",
        "state.gov": "state",
        "whitehouse.gov": "whitehouse",
        "defense.gov": "defense",
        "un.org": "un",
        "iaea.org": "iaea",
    }

    if domain in aliases:
        return aliases[domain]

    for key, value in aliases.items():
        if domain.endswith("." + key):
            return value

    return domain or norm(source.get("name", ""))


def source_tier(article):
    """
    1 = مصدر قوي جداً
    2 = مصدر قوي/إقليمي
    3 = مصدر محلي أو أقل قوة
    """

    domain = source_domain(article)

    tier1 = [
        "reuters.com",
        "apnews.com",
        "afp.com",
        "bbc.com",
        "bbc.co.uk",
        "cnn.com",
        "nytimes.com",
        "washingtonpost.com",
        "theguardian.com",
        "ft.com",
        "wsj.com",
        "aljazeera.net",
        "un.org",
        "iaea.org",
        "whitehouse.gov",
        "state.gov",
        "defense.gov",
    ]

    tier2 = [
        "alarabiya.net",
        "alhadath.net",
        "skynewsarabia.com",
        "france24.com",
        "dw.com",
        "euronews.com",
        "alhurra.com",
        "rudaw.net",
        "shafaq.com",
        "alsumaria.tv",
    ]

    for item in tier1:
        if domain == item or domain.endswith("." + item):
            return 1

    for item in tier2:
        if domain == item or domain.endswith("." + item):
            return 2

    return 3


# =========================================================
# المعرّفات والسجل
# =========================================================

def article_id(article):
    raw = "|".join([
        article.get("family", ""),
        article.get("title", ""),
        article.get("link", ""),
    ])

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def event_text(article):
    return (
        article.get("title", "")
        + " "
        + article.get("summary", "")
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
        with open(
            SEEN_FILE,
            encoding="utf-8"
        ) as f:
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

    ids = set(
        data.get("ids", [])
    )

    events = data.get(
        "events",
        []
    )

    if not isinstance(events, list):
        events = []

    clean_events = []

    for item in events:
        if (
            isinstance(item, dict)
            and item.get("title")
        ):
            clean_events.append(item)

    return {
        "ids": ids,
        "events": clean_events
    }


def save_seen(seen):
    data = {
        "version": 3,
        "ids": list(seen["ids"])[-5000:],
        "events": seen["events"][-MAX_SEEN_EVENTS:],
    }

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as f:
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

        old_title = old.get(
            "title",
            ""
        )

        old_text = old.get(
            "text",
            old_title
        )

        score_title = similarity(
            article.get("title", ""),
            old_title
        )

        score_full = similarity(
            candidate,
            old_text
        )

        if score_title >= 0.86:
            return True

        if score_full >= 0.83:
            return True

        common = (
            words(candidate)
            & words(old_text)
        )

        if (
            len(common) >= 4
            and score_full >= 0.70
        ):
            return True

    return False


def remember_group(
    group,
    final_text,
    seen
):
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
        ).isoformat(),
    })

    seen["ids"] = set(
        list(seen["ids"])[-5000:]
    )

    seen["events"] = (
        seen["events"][-MAX_SEEN_EVENTS:]
    )


# =========================================================
# التاريخ
# =========================================================

def published_time(entry):
    parsed = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
        or entry.get("created_parsed")
    )

    if parsed:
        try:
            return datetime.fromtimestamp(
                calendar.timegm(parsed),
                tz=timezone.utc
            )
        except Exception:
            pass

    return None


# =========================================================
# تصنيف البلد/الموضوع
# =========================================================

def topic_type(article):
    text = norm(event_text(article))

    iraq_hits = sum(
        1
        for key in IRAQ_WORDS
        if norm(key) in text
    )

    iran_us_hits = sum(
        1
        for key in IRAN_US
        if norm(key) in text
    )

    world_hits = sum(
        1
        for key in WORLD_WORDS
        if norm(key) in text
    )

    if iran_us_hits >= 1:
        return "Iran-US"

    if iraq_hits >= 1:
        return "Iraq"

    if world_hits >= 1:
        return "World"

    return "Other"


# =========================================================
# أهمية الخبر من 100
# =========================================================

def importance_score(article):
    text = norm(event_text(article))

    score = 0

    tier = source_tier(article)

    # جودة المصدر.
    if tier == 1:
        score += 25
    elif tier == 2:
        score += 18
    else:
        score += 10

    # إيران/أمريكا لها أولوية قصوى.
    iran_us_hits = sum(
        1
        for key in IRAN_US
        if norm(key) in text
    )

    score += min(
        iran_us_hits * 5,
        25
    )

    # العراق.
    iraq_hits = sum(
        1
        for key in IRAQ_WORDS
        if norm(key) in text
    )

    score += min(
        iraq_hits * 3,
        12
    )

    # أحداث عالية التأثير.
    impact_hits = sum(
        1
        for key in HIGH_IMPACT_WORDS
        if norm(key) in text
    )

    score += min(
        impact_hits * 5,
        25
    )

    # عاجل/تصعيد.
    breaking_hits = sum(
        1
        for key in BREAKING_WORDS
        if norm(key) in text
    )

    score += min(
        breaking_hits * 3,
        15
    )

    # شخصيات/جهات كبيرة.
    senior_hits = sum(
        1
        for key in SENIOR_ENTITIES
        if norm(key) in text
    )

    score += min(
        senior_hits * 3,
        12
    )

    # حداثة الخبر.
    published_at = article.get(
        "published_at"
    )

    if published_at:
        age_minutes = max(
            0,
            (
                datetime.now(timezone.utc)
                - published_at
            ).total_seconds() / 60
        )

        freshness = max(
            0,
            12 - int(age_minutes / 30)
        )

        score += freshness

    # الأخبار الروتينية تُخفض.
    routine_hits = sum(
        1
        for key in ROUTINE_WORDS
        if norm(key) in text
    )

    score -= min(
        routine_hits * 8,
        20
    )

    # منع الأخبار السياسية العامة جداً.
    if (
        not impact_hits
        and not breaking_hits
        and iran_us_hits == 0
        and iraq_hits == 0
    ):
        score -= 15

    return max(
        0,
        min(score, 100)
    )


# =========================================================
# هل الخبر سياسي؟
# =========================================================

def is_political(article):
    text = norm(event_text(article))

    political_hits = sum(
        1
        for key in POLITICAL_WORDS
        if norm(key) in text
    )

    iran_us_hits = sum(
        1
        for key in IRAN_US
        if norm(key) in text
    )

    iraq_hits = sum(
        1
        for key in IRAQ_WORDS
        if norm(key) in text
    )

    return (
        political_hits >= 1
        or iran_us_hits >= 1
        or iraq_hits >= 1
    )


# =========================================================
# جلب الأخبار
# =========================================================

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

    now = datetime.now(
        timezone.utc
    )

    cutoff = (
        now
        - timedelta(
            hours=MAX_AGE_HOURS
        )
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
                    entry.get("title")
                    or ""
                ).strip()

                if not title:
                    continue

                published_at = (
                    published_time(entry)
                )

                # إذا كان التاريخ معروفاً وقديماً.
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
                            "summary",
                            ""
                        )
                        or ""
                    ).strip(),
                    "link": (
                        entry.get(
                            "link",
                            ""
                        )
                        or ""
                    ).strip(),
                    "published_at":
                        published_at,
                }

                if not is_political(
                    article
                ):
                    continue

                article["importance"] = (
                    importance_score(
                        article
                    )
                )

                article["_id"] = (
                    article_id(article)
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


# =========================================================
# هل الخبران نفس الحدث؟
# =========================================================

def same_event(a, b):

    # نفس المؤسسة ليست مصدراً مستقلاً.
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
        & words(event_text(b))
    )

    event_words = {
        "ايران",
        "ايراني",
        "امريكا",
        "امريكي",
        "واشنطن",
        "طهران",
        "ترامب",
        "اسرائيل",
        "اليمن",
        "الحوثيين",
        "غزه",
        "لبنان",
        "العراق",
        "السعوديه",
        "هجوم",
        "ضربه",
        "قصف",
        "صاروخ",
        "صواريخ",
        "مسييره",
        "مفاوضات",
        "هدنه",
        "عقوبات",
        "نووي",
        "هرمز",
        "قاعده",
        "قوات",
        "اسرائيلي",
    }

    shared_event = (
        common & event_words
    )

    if title_score >= 0.86:
        return True

    if full_score >= 0.86:
        return True

    if (
        full_score >= 0.72
        and len(shared_event) >= 3
    ):
        return True

    if (
        title_score >= 0.75
        and len(common) >= 4
    ):
        return True

    return False


# =========================================================
# تجميع الأخبار
# =========================================================

def group_news(news):

    ordered = sorted(
        news,
        key=lambda x: x.get(
            "importance",
            0
        ),
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


# =========================================================
# تقييم المجموعة
# =========================================================

def group_score(group):

    scores = [
        a.get(
            "importance",
            0
        )
        for a in group
    ]

    base = max(scores) if scores else 0

    families = {
        a["family"]
        for a in group
    }

    # كل مصدر مستقل إضافي يزيد الثقة.
    verification_bonus = min(
        max(0, len(families) - 1) * 8,
        24
    )

    topic = topic_type(
        group[0]
    )

    topic_bonus = (
        10
        if topic == "Iran-US"
        else 4
        if topic == "Iraq"
        else 0
    )

    return min(
        100,
        base
        + verification_bonus
        + topic_bonus
    )


# =========================================================
# اختيار أفضل الأحداث
# =========================================================

def select_best_groups(groups):

    candidates = []

    for group in groups:

        score = group_score(
            group
        )

        families = {
            a["family"]
            for a in group
        }

        tier1 = any(
            source_tier(a) == 1
            for a in group
        )

        tier2 = any(
            source_tier(a) == 2
            for a in group
        )

        text = norm(
            " ".join(
                a["title"]
                for a in group
            )
        )

        breaking = any(
            norm(k) in text
            for k in BREAKING_WORDS
        )

        high_impact = any(
            norm(k) in text
            for k in HIGH_IMPACT_WORDS
        )

        topic = topic_type(
            group[0]
        )

        # القاعدة الأساسية:
        # مصدران مستقلان + أهمية جيدة.
        verified = (
            len(families) >= 2
            and score >= 55
        )

        # مصدر Tier 1 واحد يسمح بالنشر
        # إذا كان الخبر قوياً وعاجلاً.
        strong_single = (
            len(families) == 1
            and tier1
            and score >= 72
            and (
                breaking
                or high_impact
            )
        )

        # Tier 2 يحتاج عتبة أعلى.
        tier2_single = (
            len(families) == 1
            and tier2
            and score >= 82
            and breaking
            and high_impact
        )

        # المصادر الأضعف لا تنشر وحدها.
        if not (
            verified
            or strong_single
            or tier2_single
        ):
            continue

        candidates.append(
            (
                score,
                topic,
                group
            )
        )

    candidates.sort(
        key=lambda x: x[0],
        reverse=True
    )

    # نأخذ أفضل 60 مجموعة كحد أقصى.
    return candidates[:MAX_CANDIDATES]


# =========================================================
# تنويع المنشورات
# =========================================================

def diversify_groups(groups):

    selected = []

    used_families = set()

    topic_counts = {
        "Iran-US": 0,
        "Iraq": 0,
        "World": 0,
        "Other": 0,
    }

    remaining = list(groups)

    while (
        remaining
        and len(selected)
        < MAX_POSTS_PER_RUN
    ):

        best_index = None
        best_value = None

        for idx, item in enumerate(
            remaining
        ):

            score, topic, group = item

            families = {
                a["family"]
                for a in group
            }

            # لا نريد نفس المؤسسة
            # في منشورين متتالين.
            family_penalty = (
                20
                if families & used_families
                else 0
            )

            value = score

            # تنويع الموضوعات.
            if topic_counts[topic] == 0:
                value += 8

            if topic_counts[topic] >= 2:
                value -= 10

            # إيران/أمريكا لها أولوية خاصة.
            if topic == "Iran-US":
                value += 12

            value -= family_penalty

            if (
                best_value is None
                or value > best_value
            ):
                best_value = value
                best_index = idx

        if best_index is None:
            break

        item = remaining.pop(
            best_index
        )

        score, topic, group = item

        selected.append(
            item
        )

        topic_counts[topic] += 1

        for article in group:
            used_families.add(
                article["family"]
            )

    return selected


# =========================================================
# OpenAI
# =========================================================

def openai_text(data):

    if data.get(
        "output_text"
    ):
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
                    output.append(
                        text
                    )

    return (
        "\n".join(output).strip()
        if output
        else None
    )


def load_openai_state():

    try:
        with open(
            OPENAI_STATE_FILE,
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(
            data,
            dict
        ):
            return data

    except Exception:
        pass

    return {
        "last_attempt": None
    }


def save_openai_state(state):

    with open(
        OPENAI_STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2
        )


def openai_allowed():

    if not OPENAI_KEY:
        return False

    state = load_openai_state()

    last = state.get(
        "last_attempt"
    )

    if not last:
        return True

    try:
        elapsed = (
            datetime.now(
                timezone.utc
            )
            - datetime.fromisoformat(
                last
            )
        ).total_seconds() / 60

        if (
            elapsed
            < OPENAI_COOLDOWN_MINUTES
        ):
            print(
                "⏳ OpenAI في فترة الانتظار — "
                "سيتم استخدام النشر المحلي."
            )

            return False

    except Exception:
        return True

    return True


def openai_call(
    prompt,
    max_tokens=300
):

    if not openai_allowed():
        return None

    state = load_openai_state()

    state["last_attempt"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    save_openai_state(
        state
    )

    try:

        response = session.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization":
                    f"Bearer {OPENAI_KEY}",
                "Content-Type":
                    "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "input": prompt,
                "max_output_tokens":
                    max_tokens,
            },
            timeout=60,
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


# =========================================================
# التحقق من الحدث
# =========================================================

def verify_event(group):

    families = {
        a["family"]
        for a in group
    }

    # إذا مصدر واحد، لا نحتاج تحقق
    # إلا إذا كان Tier 1 قوي جداً.
    if len(families) < 2:

        return (
            len(group) == 1
            and source_tier(
                group[0]
            ) == 1
            and group[0].get(
                "importance",
                0
            ) >= 72
        )

    text = "\n\n".join(
        f"المؤسسة: {a['source']}\n"
        f"العنوان: {a['title']}\n"
        f"التفاصيل: {a['summary']}"
        for a in group
    )

    prompt = f"""
أنت مدقق أخبار سياسية محترف.

تحقق هل المصادر التالية تؤكد الواقعة نفسها فعلاً.

لا تدمج أحداثاً مختلفة لمجرد أنها تتعلق بالدولة أو الشخص نفسه.

المطلوب:
- نفس الحدث
