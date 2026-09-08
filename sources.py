# sources.py
# ==========================================
# مصادر نظام الأخبار السياسية
# عراقية + عربية + عالمية
# ==========================================

SOURCES = [

    # ==================================================
    # 🇮🇶 المصادر العراقية
    # ==================================================

    {
        "name": "وكالة الأنباء العراقية المستقلة",
        "country": "Iraq",
        "type": "agency",
        "feed": "https://www.ina-iraq.com/news/important/rss",
    },

    {
        "name": "شفق نيوز",
        "country": "Iraq",
        "type": "agency",
        "feed": "https://www.shafaq.com/ar/rss",
    },

    {
        "name": "السومرية",
        "country": "Iraq",
        "type": "channel",
        "feed": "https://www.alsumaria.tv/Rss/News/ar/1/سياسة",
    },

    {
        "name": "السومرية - دوليات",
        "country": "Iraq",
        "type": "channel",
        "feed": "https://www.alsumaria.tv/Rss/News/ar/49/دوليات",
    },

    {
        "name": "السومرية - آخر الأخبار",
        "country": "Iraq",
        "type": "channel",
        "feed": "https://www.alsumaria.tv/Rss/iraq-latest-news/ar",
    },

    {
        "name": "الشرقية",
        "country": "Iraq",
        "type": "channel",
        "feed": None,
        "website": "https://www.alsharqiya.com/",
    },

    {
        "name": "دجلة",
        "country": "Iraq",
        "type": "channel",
        "feed": None,
        "website": "https://dijlah.tv/",
    },

    {
        "name": "شبكة الإعلام العراقي",
        "country": "Iraq",
        "type": "network",
        "feed": None,
        "website": "https://imn.gov.iq/",
    },

    {
        "name": "وكالة الأنباء العراقية",
        "country": "Iraq",
        "type": "agency",
        "feed": None,
        "website": "https://ina.iq/",
    },

    {
        "name": "الصباح",
        "country": "Iraq",
        "type": "newspaper",
        "feed": None,
        "website": "https://alsabaah.iq/",
    },

    {
        "name": "المدى",
        "country": "Iraq",
        "type": "newspaper",
        "feed": None,
        "website": "https://almadapaper.net/",
    },

    {
        "name": "الزمان",
        "country": "Iraq",
        "type": "newspaper",
        "feed": None,
        "website": "https://www.azzaman.com/",
    },

    {
        "name": "كتابات",
        "country": "Iraq",
        "type": "news",
        "feed": "https://kitabat.com/feed/",
    },

    {
        "name": "صوت العراق",
        "country": "Iraq",
        "type": "news",
        "feed": "https://www.sotaliraq.com/feed/",
    },

    {
        "name": "شبكة أخبار العراق",
        "country": "Iraq",
        "type": "news",
        "feed": None,
        "website": "https://aliraqnews.com/",
    },

    {
        "name": "بغداد اليوم",
        "country": "Iraq",
        "type": "news",
        "feed": None,
        "website": "https://baghdadtoday.news/",
    },

    {
        "name": "ناس",
        "country": "Iraq",
        "type": "news",
        "feed": None,
        "website": "https://www.nasnews.com/",
    },

    {
        "name": "المسلة",
        "country": "Iraq",
        "type": "news",
        "feed": None,
        "website": "https://almasalah.com/",
    },

    {
        "name": "باسنيوز",
        "country": "Iraq",
        "type": "news",
        "feed": None,
        "website": "https://www.basnews.com/",
    },


    # ==================================================
    # 🌍 مصادر عربية
    # ==================================================

    {
        "name": "الجزيرة",
        "country": "Arab",
        "type": "channel",
        "feed": "https://www.aljazeera.com/xml/rss/all.xml",
    },

    {
        "name": "الحدث",
        "country": "Arab",
        "type": "channel",
        "feed": "https://www.alhadath.net/tools/mrss",
    },

    {
        "name": "الجديد",
        "country": "Arab",
        "type": "channel",
        "feed": "https://www.aljadeed.tv/rss/ar",
    },

    {
        "name": "LBCI",
        "country": "Arab",
        "type": "channel",
        "feed": "https://www.lbcgroup.tv/rss/ar",
    },

    {
        "name": "العربية",
        "country": "Arab",
        "type": "channel",
        "feed": None,
        "website": "https://www.alarabiya.net/",
    },

    {
        "name": "الشرق",
        "country": "Arab",
        "type": "channel",
        "feed": None,
        "website": "https://asharq.com/",
    },

    {
        "name": "العربي الجديد",
        "country": "Arab",
        "type": "newspaper",
        "feed": None,
        "website": "https://www.alaraby.co.uk/",
    },

    {
        "name": "الشرق الأوسط",
        "country": "Arab",
        "type": "newspaper",
        "feed": None,
        "website": "https://aawsat.com/",
    },

    {
        "name": "الحرة",
        "country": "Arab",
        "type": "channel",
        "feed": None,
        "website": "https://www.alhurra.com/",
    },

    {
        "name": "سكاي نيوز عربية",
        "country": "Arab",
        "type": "channel",
        "feed": None,
        "website": "https://www.skynewsarabia.com/",
    },


    # ==================================================
    # 🌎 المصادر العالمية
    # ==================================================

    {
        "name": "BBC World",
        "country": "World",
        "type": "channel",
        "feed": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },

    {
        "name": "BBC Politics",
        "country": "World",
        "type": "channel",
        "feed": None,
        "website": "https://www.bbc.com/news/politics",
    },

    {
        "name": "Reuters",
        "country": "World",
        "type": "agency",
        "feed": (
            "https://news.google.com/rss/search?"
            "q=site%3Areuters.com"
            "&hl=en-US&gl=US&ceid=US%3Aen"
        ),
    },

    {
        "name": "Associated Press",
        "country": "World",
        "type": "agency",
        "feed": "https://apnews.com/rss/apf-world",
    },

    {
        "name": "CNN World",
        "country": "World",
        "type": "channel",
        "feed": "https://rss.cnn.com/rss/edition_world.rss",
    },

    {
        "name": "France 24",
        "country": "World",
        "type": "channel",
        "feed": "https://www.france24.com/en/rss",
    },

    {
        "name": "The Guardian",
        "country": "World",
        "type": "newspaper",
        "feed": "https://www.theguardian.com/world/rss",
    },

    {
        "name": "NBC News",
        "country": "World",
        "type": "channel",
        "feed": "https://feeds.nbcnews.com/feeds/worldnews",
    },

    {
        "name": "Sky News",
        "country": "World",
        "type": "channel",
        "feed": "https://news.sky.com/info/rss",
    },

    {
        "name": "Al Jazeera English",
        "country": "World",
        "type": "channel",
        "feed": "https://www.aljazeera.com/xml/rss/all.xml",
    },

]


# ==================================================
# دوال مساعدة
# ==================================================

def get_rss_sources():
    """إرجاع المصادر التي لديها RSS فعلي."""
    return [
        source for source in SOURCES
        if source.get("feed")
    ]


def get_web_sources():
    """إرجاع المصادر التي لا تملك RSS وتحتاج جلباً من الموقع."""
    return [
        source for source in SOURCES
        if not source.get("feed") and source.get("website")
    ]


def get_sources_by_country(country):
    """إرجاع المصادر حسب المنطقة."""
    return [
        source for source in SOURCES
        if source.get("country") == country
    ]


def get_source_count():
    """عدد المصادر."""
    return len(SOURCES)
