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


# ============================================================
# إعدادات النظام
# ============================================================

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL = os.getenv("TELEGRAM_CHANNEL", "@MH999R").strip()

MAX_NEWS_PER_SOURCE = 8
MAX_POSTS_PER_RUN = 5
MAX_CANDIDATES = 35
MAX_AI_CALLS_PER_RUN = 8

# المقال يجب أن يكون حديثاً. إذا لم يرسل RSS تاريخاً، لا نرفضه تلقائياً.
MAX_AGE_HOURS = 12

SEEN_FILE = "seen_news.json"
MAX_SEEN_IDS = 6000
MAX_SEEN_EVENTS = 3000


# ============================================================
# الكلمات والموضوعات
# ============================================================

IRAN_US = [
    "إيران", "ايران", "الإيراني", "الايراني", "الإيرانية", "الايرانية",
    "طهران", "ترامب", "ترمب", "أمريكا", "امريكا", "الولايات المتحدة",
    "واشنطن", "البنتاغون", "البنتاجون", "البيت الأبيض", "البيت الابيض",
    "الحرس الثوري", "مضيق هرمز", "هرمز", "القوات الأمريكية",
    "القوات الامريكية", "القواعد الأمريكية", "القواعد الامريكية",
    "منشأة نووية", "منشاة نووية", "البرنامج النووي", "نووي",
]

IRAQ_WORDS = [
    "العراق", "العراقي", "العراقية", "بغداد", "كربلاء", "النجف",
    "البصرة", "نينوى", "الأنبار", "الانبار", "كركوك", "أربيل", "اربيل",
    "السليمانية", "البرلمان العراقي", "الحكومة العراقية",
    "رئيس الوزراء العراقي", "مجلس الوزراء", "الجيش العراقي",
    "الحشد الشعبي", "وزارة الداخلية العراقية", "وزارة الدفاع العراقية",
]

ARAB_WORDS = [
    "اليمن", "الحوثي", "الحوثيين", "السعودية", "لبنان", "سوريا", "سورية",
    "غزة", "فلسطين", "إسرائيل", "اسرائيل", "الأردن", "الاردن",
    "مصر", "قطر", "الإمارات", "الامارات", "تركيا", "ليبيا", "السودان",
]

WORLD_WORDS = [
    "روسيا", "أوكرانيا", "اوكرانيا", "الصين", "تايوان", "الناتو",
    "الأمم المتحدة", "الامم المتحدة", "مجلس الأمن", "مجلس الامن",
    "أوروبا", "اوروبا", "كوريا", "اليابان", "الهند", "باكستان",
]

IMPACT_WORDS = [
    "حرب", "هجوم", "ضربة", "قصف", "غارات", "استهداف", "صاروخ",
    "صواريخ", "مسيرة", "مسيّرة", "اعتراض", "اشتباك", "تصعيد",
    "انفجار", "مقتل", "اغتيال", "إصابة", "اصابة", "احتلال",
    "انسحاب", "إغلاق", "اغلاق", "حصار", "هدنة", "وقف إطلاق النار",
    "وقف اطلاق النار", "اتفاق", "اتفاقية", "عقوبات", "طوارئ",
    "حالة طوارئ", "تعبئة", "عملية عسكرية", "عملية عسكريه",
    "قاعدة عسكرية", "منشأة نووية", "منشاة نووية", "مضيق هرمز",
]

SENIOR_WORDS = [
    "ترامب", "ترمب", "خامنئي", "الرئيس الأمريكي", "الرئيس الامريكي",
    "رئيس الوزراء العراقي", "رئيس الجمهورية", "وزير الخارجية",
    "وزير الدفاع", "الحرس الثوري", "البنتاغون", "البيت الأبيض",
    "البيت الابيض", "مجلس الأمن", "مجلس الامن", "الأمم المتحدة",
]

BREAKING_WORDS = [
    "عاجل", "الآن", "الان", "قبل قليل", "هجوم", "ضربة", "قصف",
    "استهداف", "مقتل", "اغتيال", "انفجار", "صاروخ", "صواريخ",
    "مسيرة", "مسيّرة", "اشتباك", "اعتراض", "تصعيد", "طوارئ",
]

ROUTINE_WORDS = [
    "يبحث", "بحث", "يناقش", "ناقش", "استقبل", "يستقبل", "التقى",
    "يلتقي", "أعرب عن", "اعرب عن", "يؤكد أهمية", "تعزيز التعاون",
]

GENERIC_WORDS = {
    "خبر", "أخبار", "اخبار", "آخر", "اخر", "الجديد", "الجديدة",
    "تفاصيل", "تطورات", "تصريحات", "تصريح", "يعلن", "تعلن", "اعلن",
    "أعلن", "قال", "تقول", "بحسب", "مصدر", "مصادر", "صحيفة", "وكالة",
    "اليوم", "الان", "الآن", "عبر", "حول", "بشأن", "بعد", "قبل",
    "خلال", "نحو", "وسط", "ضمن", "لدى", "مع", "من", "في", "على",
    "الى", "إلى", "عن", "هذا", "هذه", "ذلك", "تلك",
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/2.0)"
})


# ============================================================
# أدوات النص
# ============================================================

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
    out = set()
    for w in norm(text).split():
        if len(w) <= 2 or w in GENERIC_WORDS:
            continue
        out.add(w)
    return out


def similarity(a, b):
    a = norm(a)
    b = norm(b)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    aw, bw = words(a), words(b)
    overlap = len(aw & bw) / len(aw | bw) if aw and bw else 0.0
    return seq * 0.45 + overlap * 0.55


def contains_any(text, items):
    t = norm(text)
    return any(norm(x) in t for x in items)


def count_hits(text, items):
    t = norm(text)
    return sum(1 for x in items if norm(x) in t)


# ============================================================
# المصادر والتصنيف
# ============================================================

def source_domain(source):
    website = (source.get("website") or "").strip()
    if not website:
        return ""
    try:
        host = urlparse(website).netloc.lower().removeprefix("www.")
    except Exception:
        host = website.lower()
    return host


def source_family(source):
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
        "cnn.com": "cnn",
        "rt.com": "rt",
        "arabic.rt.com": "rt",
        "france24.com": "france24",
        "dw.com": "dw",
        "euronews.com": "euronews",
        "apnews.com": "ap",
        "nytimes.com": "nytimes",
        "washingtonpost.com": "washingtonpost",
        "theguardian.com": "guardian",
        "al-monitor.com": "almonitor",
        "middleeasteye.net": "mee",
        "aawsat.com": "aawsat",
        "asharq.com": "asharq",
    }
    if domain in aliases:
        return aliases[domain]
    for key, value in aliases.items():
        if domain.endswith("." + key):
            return value
    return domain or norm(source.get("name", ""))


def source_tier(article):
    f = article.get("family", "")
    tier1 = {
        "reuters", "ap", "afp", "bbc", "cnn", "nytimes",
        "washingtonpost", "guardian", "ft", "wsj",
        "aljazeera", "un", "iaea", "whitehouse", "state",
        "defense", "pentagon",
    }
    tier2 = {
        "alarabiya", "skynewsarabia", "france24", "dw", "euronews",
        "alhurra", "rudaw", "shafaq", "alsumaria", "asharq", "aawsat",
        "rt", "almonitor", "mee",
    }
    if f in tier1:
        return 1
    if f in tier2:
        return 2
    return 3


def article_topic(article):
    text = norm(article.get("title", "") + " " + article.get("summary", ""))

    # مهم جداً: إيران-أمريكا فقط إذا ظهر سياق الطرفين أو سياق عسكري مباشر.
    iran = contains_any(text, ["إيران", "ايران", "طهران", "الحرس الثوري", "خامنئي"])
    us = contains_any(text, ["أمريكا", "امريكا", "الولايات المتحدة", "واشنطن", "ترامب", "البنتاغون"])
    if iran and us:
        return "Iran-US"

    if contains_any(text, IRAQ_WORDS):
        return "Iraq"
    if contains_any(text, ARAB_WORDS):
        return "Arab"
    if contains_any(text, WORLD_WORDS):
        return "World"

    # إذا كان الخبر عن إيران مع عمل عسكري/نووي، يبقى ضمن الملف الإيراني
    if iran and contains_any(text, IMPACT_WORDS):
        return "Iran-US"

    return "World"


def article_id(article):
    raw = "|".join([
        article.get("family", ""),
        article.get("title", ""),
        article.get("link", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def published_time(entry):
    parsed = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
        or entry.get("created_parsed")
    )
    if parsed:
        try:
            import calendar
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        except Exception:
            pass
    return None


# ============================================================
# الأهمية
# ============================================================

def importance(article):
    text = norm(article.get("title", "") + " " + article.get("summary", ""))
    score = 0

    tier = source_tier(article)
    score += {1: 28, 2: 18, 3: 8}.get(tier, 0)

    topic = article.get("topic", article_topic(article))
    if topic == "Iran-US":
        score += 22
    elif topic == "Iraq":
        score += 16
    elif topic == "Arab":
        score += 12
    else:
        score += 7

    impact = count_hits(text, IMPACT_WORDS)
    breaking = count_hits(text, BREAKING_WORDS)
    senior = count_hits(text, SENIOR_WORDS)

    score += min(impact * 5, 25)
    score += min(breaking * 4, 16)
    score += min(senior * 4, 16)

    if contains_any(text, ROUTINE_WORDS):
        score -= 8

    if article.get("published_at"):
        age = max(
            0,
            (datetime.now(timezone.utc) - article["published_at"]).total_seconds() / 3600
        )
        if age <= 1:
            score += 15
        elif age <= 3:
            score += 11
        elif age <= 6:
            score += 7
        elif age <= 12:
            score += 3

    return max(0, min(100, score))


# ============================================================
# فلترة الأخبار
# ============================================================

def is_relevant(article):
    text = norm(article.get("title", "") + " " + article.get("summary", ""))

    political = (
        contains_any(text, IRAN_US)
        or contains_any(text, IRAQ_WORDS)
        or contains_any(text, ARAB_WORDS)
        or contains_any(text, WORLD_WORDS)
        or contains_any(text, IMPACT_WORDS)
    )
    if not political:
        return False

    # نستبعد أخبار العلاقات العامة الروتينية إذا لم تحمل أثراً واضحاً.
    routine_only = (
        contains_any(text, ROUTINE_WORDS)
        and not contains_any(text, IMPACT_WORDS)
        and not contains_any(text, BREAKING_WORDS)
    )
    if routine_only:
        return False

    return True


def fetch_news():
    result = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)

    rss_sources = [s for s in SOURCES if s.get("feed")]
    print(f"📚 إجمالي المصادر: {len(rss_sources)}")

    for source in rss_sources:
        count = 0
        try:
            feed = feedparser.parse(source["feed"])

            for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue

                published_at = published_time(entry)
                if published_at and published_at < cutoff:
                    continue

                article = {
                    "source": source.get("name", "مصدر"),
                    "family": source_family(source),
                    "tier": None,
                    "country": source.get("country", ""),
                    "type": source.get("type", "news"),
                    "website": source.get("website", ""),
                    "title": title,
                    "summary": re.sub(r"<[^>]+>", " ", (entry.get("summary") or "")).strip(),
                    "link": (entry.get("link") or "").strip(),
                    "published_at": published_at,
                }

                if not is_relevant(article):
                    continue

                article["topic"] = article_topic(article)
                article["tier"] = source_tier(article)
                article["importance"] = importance(article)
                article["_id"] = article_id(article)
                result.append(article)
                count += 1

            print(f"🔎 {source.get('name','مصدر')}: {count} خبر سياسي حديث")

        except Exception as exc:
            print(f"❌ {source.get('name','مصدر')}: {exc}")

    return result


# ============================================================
# الذاكرة ومنع التكرار
# ============================================================

def load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"ids": set(), "events": []}

    if isinstance(data, list):
        return {"ids": set(data), "events": []}

    if not isinstance(data, dict):
        return {"ids": set(), "events": []}

    ids = set(data.get("ids", []))
    events = data.get("events", [])
    if not isinstance(events, list):
        events = []

    return {
        "ids": ids,
        "events": [x for x in events if isinstance(x, dict) and x.get("text")]
    }


def save_seen(seen):
    data = {
        "version": 3,
        "ids": list(seen["ids"])[-MAX_SEEN_IDS:],
        "events": seen["events"][-MAX_SEEN_EVENTS:],
    }
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def already_seen(article, seen):
    if article.get("_id") in seen["ids"]:
        return True

    current = article.get("title", "") + " " + article.get("summary", "")

    for old in seen["events"]:
        old_text = old.get("text", "")
        if similarity(article.get("title", ""), old.get("title", "")) >= 0.90:
            return True
        if similarity(current, old_text) >= 0.88:
            return True

    return False


def remember_group(group, final_text, seen):
    for article in group:
        seen["ids"].add(article.get("_id"))

    clean = re.sub(r"^🔴\s*", "", final_text).strip()
    seen["events"].append({
        "title": clean[:500],
        "text": clean[:1200],
        "time": datetime.now(timezone.utc).isoformat(),
    })

    seen["ids"] = set(list(seen["ids"])[-MAX_SEEN_IDS:])
    seen["events"] = seen["events"][-MAX_SEEN_EVENTS:]


# ============================================================
# تجميع الأحداث
# ============================================================

EVENT_WORDS = {
    "ايران", "ايراني", "طهران", "امريكا", "امريكي", "واشنطن",
    "ترامب", "خامنئي", "اسرائيل", "غزه", "لبنان", "اليمن",
    "الحوثيين", "العراق", "بغداد", "السعوديه", "سوريا",
    "روسيا", "اوكرانيا", "الصين", "تايوان", "هجوم", "ضربه",
    "قصف", "صاروخ", "صواريخ", "مسييره", "اعتراض", "اشتباك",
    "مفاوضات", "هدنه", "عقوبات", "نووي", "هرمز", "حرس", "ثوري",
    "قاعدة", "قوات", "اسرائيلي", "برلمان", "حكومه", "انتخابات",
}


def same_event(a, b):
    # لا ندمج مؤسستين من نفس العائلة كأنهما مصدران مستقلان.
    if a["family"] == b["family"]:
        return False

    # يجب أن يكون الموضوع العام نفسه.
    if a.get("topic") != b.get("topic"):
        return False

    title_score = similarity(a["title"], b["title"])
    full_score = similarity(
        a["title"] + " " + a["summary"],
        b["title"] + " " + b["summary"],
    )

    common = words(a["title"] + " " + a["summary"]) & words(
        b["title"] + " " + b["summary"]
    )
    shared_event = common & EVENT_WORDS

    if title_score >= 0.82:
        return True
    if full_score >= 0.82:
        return True
    if full_score >= 0.67 and len(shared_event) >= 3:
        return True

    return False


def group_news(news):
    ordered = sorted(news, key=lambda x: x["importance"], reverse=True)
    groups = []
    used = set()

    for i, article in enumerate(ordered):
        if i in used:
            continue

        group = [article]
        used.add(i)

        for j in range(i + 1, len(ordered)):
            if j in used:
                continue
            if same_event(article, ordered[j]):
                group.append(ordered[j])
                used.add(j)

        groups.append(group)

    return groups


def group_score(group):
    families = {a["family"] for a in group}
    best = max(a["importance"] for a in group)

    # التحقق المستقل يرفع الثقة.
    corroboration = min(18, max(0, len(families) - 1) * 9)

    # مصدر Tier 1 داخل المجموعة.
    if any(a["tier"] == 1 for a in group):
        corroboration += 6

    return min(100, best + corroboration)


def is_publishable_candidate(group):
    score = group_score(group)
    families = {a["family"] for a in group}
    has_t1 = any(a["tier"] == 1 for a in group)
    has_t2 = any(a["tier"] == 2 for a in group)
    text = " ".join(a["title"] + " " + a["summary"] for a in group)

    impact = contains_any(text, IMPACT_WORDS)
    breaking = contains_any(text, BREAKING_WORDS)
    topic = group[0].get("topic")

    # خبر مؤكد من مؤسستين مستقلتين.
    if len(families) >= 2 and score >= 52 and (impact or breaking or topic in {"Iran-US", "Iraq"}):
        return True

    # خبر عاجل/عالي الأثر من Tier 1 واحد.
    if len(families) == 1 and has_t1 and score >= 55 and (impact or breaking):
        return True

    # Tier 2 وحده يحتاج حدثاً شديد الأثر.
    if len(families) == 1 and has_t2 and score >= 72 and impact and breaking:
        return True

    return False


def rank_groups(groups):
    candidates = [g for g in groups if is_publishable_candidate(g)]
    candidates.sort(key=group_score, reverse=True)

    # لا نمنع المرشح من الوصول للتحقق فقط لأن له نفس العائلة
    # الموجودة في مرشح آخر؛ التنويع يتم بعد التأكد من الخبر.
    return candidates[:MAX_CANDIDATES]


# ============================================================
# OpenAI: مكالمة واحدة للتحقق + التحرير
# ============================================================

def openai_text(data):
    if data.get("output_text"):
        return data["output_text"].strip()

    chunks = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunks).strip() if chunks else None


def openai_call(prompt, max_tokens=350):
    if not OPENAI_KEY:
        print("⚠️ OPENAI_API_KEY غير موجود — سيُستخدم التحقق المحلي.")
        return None

    try:
        response = session.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "input": prompt,
                "max_output_tokens": max_tokens,
            },
            timeout=60,
        )

        print("🤖 OpenAI Status:", response.status_code)

        if response.status_code != 200:
            print(response.text[:1000])
            return None

        return openai_text(response.json())

    except Exception as exc:
        print("❌ OpenAI:", exc)
        return None


def build_ai_prompt(group):
    rows = []
    for a in sorted(group, key=lambda x: x["importance"], reverse=True):
        age = ""
        if a.get("published_at"):
            age = a["published_at"].isoformat()
        rows.append(
            f"المؤسسة: {a['source']}\n"
            f"العائلة: {a['family']}\n"
            f"التصنيف: {a['topic']}\n"
            f"الدرجة: {a['importance']}\n"
            f"وقت المقال: {age}\n"
            f"العنوان: {a['title']}\n"
            f"التفاصيل: {a['summary'][:1200]}"
        )

    return f"""
أنت محرر ومدقق أخبار سياسية محترف.

المهمة:
حلل المصادر التالية عن حدث واحد محتمل.

أولاً:
- قرر هل تتحدث المصادر فعلاً عن الواقعة نفسها، وليس مجرد الموضوع نفسه.
- إذا كانت الوقائع مختلفة، أجب SKIP.
- إذا كانت هناك روايتان متعارضتان للواقعة نفسها، لا تحذف التعارض؛ انسب كل ادعاء إلى صاحبه.
- ميّز بين "قال/أعلن/ادعى" وبين الواقعة المؤكدة.
- لا تعتبر مؤسستين من العائلة نفسها مصدرين مستقلين.
- لا تخترع أي معلومة.
- لا تستخدم معلومة غير موجودة في النص المقدم.

ثانياً:
لا تنشر إذا كان الخبر:
- روتينياً أو بروتوكولياً بلا أثر سياسي واضح.
- قديماً ولا يحتوي على تطور جديد واضح.
- غير متعلق بحدث سياسي مهم.
- مجرد رأي أو تعليق بلا تطور مهم.

إذا كان صالحاً للنشر:
اكتب منشوراً عربياً مختصراً جداً، صحفياً، دقيقاً، من سطر واحد أو سطرين كحد أقصى.

الصيغة:
🔴 اسم المصدر، اسم المصدر: نص الخبر

قواعد الصياغة:
- ابدأ دائماً بـ 🔴.
- اذكر المصادر المستقلة التي تؤكد الواقعة.
- إذا كانت المعلومة ادعاءً، استخدم "بحسب" أو "أعلنت" أو "قالت" أو "ادعت" بحسب النص.
- إذا كان هناك رد أو نفي من الطرف الآخر، ضمه باختصار.
- لا تضع روابط.
- لا هاشتاغات.
- لا تقل "المصدر:".
- لا تضف مقدمة أو رأياً.
- حافظ على الأرقام والأسماء.
- لا تخلط حدثين مختلفين.
- لا تعيد صياغة ادعاء على أنه حقيقة.

أجب فقط:
SKIP
أو المنشور النهائي.

المصادر:
{chr(10).join(rows)}
""".strip()


def clean_final(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:text)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    text = text.replace("\n\n", "\n").strip()

    if text.upper() == "SKIP":
        return None

    if not text.startswith("🔴"):
        text = "🔴 " + text

    # Telegram حد الرسالة 4096، ونبقي المنشور قصيراً.
    return text[:3800].strip()


# ============================================================
# التحقق المحلي عند تعذر OpenAI
# ============================================================

def local_post(group):
    families = {}
    for a in sorted(group, key=lambda x: x["importance"], reverse=True):
        families.setdefault(a["family"], a)

    if len(families) >= 2:
        selected = sorted(families.values(), key=lambda x: x["importance"], reverse=True)
        names = [a["source"] for a in selected[:3]]
        title = clean_title(selected[0]["title"])
        if title:
            return "🔴 " + "، ".join(names) + ": " + title

    # Tier 1 single-source breaking event.
    best = max(group, key=lambda x: x["importance"])
    text = best["title"] + " " + best["summary"]
    if best["tier"] == 1 and best["importance"] >= 55 and (
        contains_any(text, IMPACT_WORDS) or contains_any(text, BREAKING_WORDS)
    ):
        return "🔴 " + best["source"] + ": " + clean_title(best["title"])

    return None


def clean_title(title):
    text = (title or "").strip()
    text = re.sub(r"\s+[-–—]\s+[^-–—]{2,70}$", "", text).strip()
    text = re.sub(r"^(عاجل\s*[:：-]\s*)+", "", text, flags=re.I).strip()
    return text


def analyze_group(group, use_ai=True):
    if use_ai:
        result = openai_call(build_ai_prompt(group), max_tokens=350)
        result = clean_final(result)
        if result:
            return result

    return local_post(group)


# ============================================================
# Telegram
# ============================================================

def send(message):
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN غير موجود.")
        return False

    try:
        response = session.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": CHANNEL,
                "text": message,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )

        print("📨 Telegram Status:", response.status_code)

        if response.status_code != 200:
            print(response.text[:1000])

        return response.status_code == 200

    except Exception as exc:
        print("❌ Telegram:", exc)
        return False


# ============================================================
# التشغيل
# ============================================================

def main():
    print("=" * 72)
    print("🚀 Telegram News Bot — Event Intelligence v3")
    print("🇮🇷🇺🇸 أولوية إيران ↔ أمريكا")
    print("🇮🇶 العراق + 🌍 العرب + 🌎 العالم")
    print(f"📢 سقف النشر: {MAX_POSTS_PER_RUN}")
    print(f"🎯 سقف المرشحين: {MAX_CANDIDATES}")
    print(f"🤖 سقف مكالمات AI: {MAX_AI_CALLS_PER_RUN}")
    print(f"⏱️ حد حداثة المقال: {MAX_AGE_HOURS} ساعة")
    print("=" * 72)

    seen = load_seen()

    all_news = fetch_news()
    print(f"\n📰 الأخبار السياسية الحديثة: {len(all_news)}")

    fresh = [a for a in all_news if not already_seen(a, seen)]
    print(f"🆕 بعد منع التكرار: {len(fresh)}")

    if not fresh:
        save_seen(seen)
        print("ℹ️ لا توجد أخبار جديدة.")
        return

    groups = group_news(fresh)
    print(f"🧩 مجموعات الأحداث: {len(groups)}")

    candidates = rank_groups(groups)
    print(f"🎯 المرشحون بعد الأهمية: {len(candidates)}")

    # ترتيب صارم مع محاولة إعطاء أولوية للأحداث المدعومة بمصادر متعددة.
    candidates.sort(
        key=lambda g: (
            len({a["family"] for a in g}) >= 2,
            group_score(g),
            max(a["importance"] for a in g),
        ),
        reverse=True,
    )

    published = 0
    ai_calls = 0
    published_fingerprints = []
    used_topics = set()
    stats = {
        "checked": 0,
        "ai": 0,
        "local": 0,
        "rejected": 0,
        "telegram_failed": 0,
    }

    for index, group in enumerate(candidates, start=1):
        if published >= MAX_POSTS_PER_RUN:
            break

        stats["checked"] += 1

        print("\n" + "=" * 72)
        print(
            f"🔎 مرشح {index}/{len(candidates)} | "
            f"الموضوع: {group[0]['topic']} | "
            f"الدرجة: {group_score(group)} | "
            f"المصادر المستقلة: {len({a['family'] for a in group})}"
        )

        for a in sorted(group, key=lambda x: x["importance"], reverse=True):
            print(
                f"• {a['source']} | {a['topic']} | "
                f"{a['importance']} | {a['title']}"
            )

        # تنويع خفيف فقط؛ لا نسقط خبراً إيرانياً مهماً لمجرد وجود خبر سابق من نفس الفئة.
        topic = group[0]["topic"]
        if topic in used_topics and published < 3:
            # لا نرفض الخبر؛ فقط نؤجله قليلاً إذا توجد خيارات أخرى.
            print("ℹ️ الموضوع مستخدم سابقاً، لكن سيُفحص لأن الجودة أهم من التنويع.")

        use_ai = ai_calls < MAX_AI_CALLS_PER_RUN and bool(OPENAI_KEY)
        if use_ai:
            ai_calls += 1
            stats["ai"] += 1
        else:
            stats["local"] += 1

        try:
            result = analyze_group(group, use_ai=use_ai)
        except Exception as exc:
            print("❌ خطأ في تحليل المجموعة:", exc)
            result = local_post(group)

        if not result:
            stats["rejected"] += 1
            print("⏭️ مرفوض: غير مؤكد/غير مهم/حدث مختلف.")
            continue

        body = re.sub(r"^🔴\s*", "", result).strip()
        if any(similarity(body, old) >= 0.80 for old in published_fingerprints):
            print("⛔ مكرر داخل التشغيل.")
            stats["rejected"] += 1
            continue

        print("\n📢 الخبر النهائي:")
        print(result)

        if send(result):
            published += 1
            published_fingerprints.append(body)
            used_topics.add(topic)
            remember_group(group, result, seen)
            save_seen(seen)
            print(f"✅ نُشر: {published}/{MAX_POSTS_PER_RUN}")
        else:
            stats["telegram_failed"] += 1
            print("❌ فشل Telegram — ننتقل للمرشح التالي.")

    save_seen(seen)

    print("\n" + "=" * 72)
    print("📊 إحصائيات التشغيل")
    print(f"🔎 فُحص: {stats['checked']}")
    print(f"🤖 AI: {stats['ai']}")
    print(f"🧩 محلي: {stats['local']}")
    print(f"⏭️ مرفوض: {stats['rejected']}")
    print(f"❌ فشل Telegram: {stats['telegram_failed']}")
    print(f"📨 نُشر بنجاح: {published}/{MAX_POSTS_PER_RUN}")
    print("🎉 انتهى التشغيل.")
    print("=" * 72)


if __name__ == "__main__":
    main()
