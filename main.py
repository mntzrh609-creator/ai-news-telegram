import feedparser

# مصادر الأخبار
FEEDS = {
    "🇮🇶 أخبار العراق": "https://feeds.bbci.co.uk/news/topics/ce1qrvle14rt/rss.xml",
    "🌍 أخبار العالم": "https://feeds.bbci.co.uk/news/world/rss.xml",
}

print("================================")
print("🔎 بدء اختبار جلب الأخبار")
print("================================")

total = 0

for source_name, feed_url in FEEDS.items():

    print(f"\n{source_name}")
    print("-" * 40)

    try:
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            print("⚠️ توجد مشكلة في قراءة المصدر")

        entries = feed.entries[:5]

        if not entries:
            print("❌ لم يتم العثور على أخبار")
            continue

        for i, entry in enumerate(entries, 1):
            title = entry.get("title", "بدون عنوان")
            link = entry.get("link", "")

            print(f"{i}. {title}")
            print(f"   {link}")

            total += 1

    except Exception as e:
        print(f"❌ خطأ: {e}")

print("\n================================")
print(f"✅ مجموع الأخبار التي تم جلبها: {total}")
print("================================")
