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

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL = "@MH999R"

MAX_NEWS_PER_SOURCE = 8
MAX_POSTS_PER_RUN = 5
MAX_AGE_HOURS = 24
MAX_SEEN_EVENTS = 2500
SEEN_FILE = "seen_news.json"
OPENAI_STATE_FILE = "openai_state.json"
OPENAI_COOLDOWN_MINUTES = 10

IRAN_US = ["إيران","ايران","طهران","ترامب","ترمب","خامنئي","أمريكا","امريكا","الولايات المتحدة","واشنطن","البنتاغون","البيت الأبيض","الحرس الثوري","إسرائيل","اسرائيل","مضيق هرمز","هرمز","البرنامج النووي","منشأة نووية"]
IRAQ = ["العراق","بغداد","كربلاء","النجف","البصرة","نينوى","الأنبار","الانبار","كركوك","أربيل","اربيل","السليمانية","البرلمان العراقي","الحكومة العراقية","رئيس الوزراء العراقي","مجلس الوزراء","الجيش العراقي","الحشد الشعبي"]
WORLD = ["روسيا","أوكرانيا","الصين","تايوان","إسرائيل","اسرائيل","غزة","فلسطين","لبنان","سوريا","اليمن","السعودية","تركيا","الأردن","مصر","الناتو","الأمم المتحدة","مجلس الأمن"]
POLITICAL = ["حكومة","رئيس","رئاسة","برلمان","انتخابات","وزير","وزارة","حزب","كتلة","سياسي","سياسية","مفاوضات","اتفاق","عقوبات","أزمة","حرب","هجوم","ضربة","قصف","صاروخ","مسيّرة","مسيرة","هدنة","دبلوماسي","مجلس الأمن"]
BREAKING = ["عاجل","الآن","قبل قليل","هجوم","ضربة","قصف","استهداف","مقتل","اغتيال","انفجار","صاروخ","صواريخ","مسيرة","مسيّرة","اشتباك","اعتراض","تصعيد","طوارئ","تهديد","تحذير"]
IMPACT = ["حرب","هجوم","ضربة","قصف","صاروخ","صواريخ","مسيّرة","مسيرة","اغتيال","مقتل","انفجار","اشتباك","تصعيد","هدنة","وقف إطلاق النار","اتفاق","عقوبات","انسحاب","إغلاق","مضيق هرمز","منشأة نووية","عملية عسكرية","حالة طوارئ","إعلان الحرب"]
SENIOR = ["ترامب","خامنئي","الرئيس الأمريكي","رئيس الوزراء العراقي","رئيس الجمهورية","وزير الخارجية","وزير الدفاع","الحرس الثوري","البنتاغون","البيت الأبيض","مجلس الأمن","الأمم المتحدة"]
ROUTINE = ["يبحث","بحث","يناقش","ناقش","استقبل","يستقبل","التقى","يلتقي","أعرب عن"]

STOP = {"من","في","على","الى","إلى","عن","مع","هذا","هذه","ذلك","تلك","بعد","قبل","خلال","حول","ان","إن","تم","قد","وقال","وقالت","وأكد","مصدر","مصادر","اليوم","الان","الآن","التي","الذي","كما","بين","لدى","فيما","أنه","إنه","كانت","كان","يكون","يتم","وسط","نحو","أمام","ضمن","عبر","وفق","بسبب","أثناء","أمس"}
GENERIC = {"خبر","أخبار","آخر","اخر","الجديد","الجديدة","تفاصيل","تطورات","تصريحات","يعلن","تعلن","اعلن","أعلن","قال","تقول","بحسب","صحيفة","وكالة","اليوم"}

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/3.0)"})

def norm(text):
    text = (text or "").lower()
    text = re.sub(r"https?://\S+|<[^>]+>", " ", text)
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = text.replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ٱ","ا").replace("ة","ه").replace("ى","ي")
    text = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def words(text):
    return {w for w in norm(text).split() if len(w) > 2 and w not in STOP and w not in GENERIC}

def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    aw, bw = words(a), words(b)
    overlap = len(aw & bw) / len(aw | bw) if aw and bw else 0.0
    return seq * 0.45 + overlap * 0.55

def domain(source):
    value = source.get("website", "") or source.get("feed", "")
    try:
        return urlparse(value).netloc.lower().removeprefix("www.")
    except Exception:
        return value.lower()

def source_family(source):
    d = domain(source)
    aliases = {
        "bbc.com":"bbc","bbc.co.uk":"bbc","reuters.com":"reuters","apnews.com":"ap",
        "afp.com":"afp","aljazeera.net":"aljazeera","alarabiya.net":"alarabiya",
        "alhadath.net":"alarabiya","skynewsarabia.com":"skynews",
        "france24.com":"france24","dw.com":"dw","euronews.com":"euronews",
        "alhurra.com":"alhurra","rudaw.net":"rudaw","shafaq.com":"shafaq",
        "alsumaria.tv":"alsumaria","un.org":"un","iaea.org":"iaea",
        "whitehouse.gov":"whitehouse","state.gov":"state","defense.gov":"defense"
    }
    if d in aliases:
        return aliases[d]
    for key, value in aliases.items():
        if d.endswith("." + key):
            return value
    return d

def source_tier(source):
    d = domain(source)
    t1 = ["reuters.com","apnews.com","afp.com","bbc.com","bbc.co.uk","cnn.com","nytimes.com","washingtonpost.com","theguardian.com","ft.com","wsj.com","aljazeera.net","un.org","iaea.org","whitehouse.gov","state.gov","defense.gov"]
    t2 = ["alarabiya.net","alhadath.net","skynewsarabia.com","france24.com","dw.com","euronews.com","alhurra.com","rudaw.net","shafaq.com","alsumaria.tv"]
    if any(d == x or d.endswith("." + x) for x in t1):
        return 1
    if any(d == x or d.endswith("." + x) for x in t2):
        return 2
    return 3

def published_time(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("created_parsed")
    if parsed:
        try:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
        except Exception:
            pass
    return None

def article_text(a):
    return (a.get("title","") + " " + a.get("summary","")).strip()

def is_political(a):
    text = norm(article_text(a))
    return any(norm(k) in text for k in POLITICAL + IRAN_US + IRAQ)

def topic(a):
    text = norm(article_text(a))
    if any(norm(k) in text for k in IRAN_US): return "Iran-US"
    if any(norm(k) in text for k in IRAQ): return "Iraq"
    if any(norm(k) in text for k in WORLD): return "World"
    return "Other"

def importance(a):
    text = norm(article_text(a))
    score = {1:25,2:18,3:10}[a["tier"]]
    score += min(sum(norm(k) in text for k in IRAN_US)*5,25)
    score += min(sum(norm(k) in text for k in IRAQ)*3,12)
    score += min(sum(norm(k) in text for k in IMPACT)*5,25)
    score += min(sum(norm(k) in text for k in BREAKING)*3,15)
    score += min(sum(norm(k) in text for k in SENIOR)*3,12)
    if a.get("published_at"):
        age = max(0,(datetime.now(timezone.utc)-a["published_at"]).total_seconds()/60)
        score += max(0,12-int(age/30))
    score -= min(sum(norm(k) in text for k in ROUTINE)*8,20)
    return max(0,min(score,100))

def article_id(a):
    raw = "|".join([a.get("family",""),a.get("title",""),a.get("link","")])
    return hashlib.sha256(raw.encode()).hexdigest()

def load_seen():
    try:
        with open(SEEN_FILE,encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data,dict):
            return {"ids":set(data.get("ids",[])),"events":data.get("events",[])}
        return {"ids":set(data if isinstance(data,list) else []),"events":[]}
    except Exception:
        return {"ids":set(),"events":[]}

def save_seen(seen):
    with open(SEEN_FILE,"w",encoding="utf-8") as f:
        json.dump({"version":4,"ids":list(seen["ids"])[-5000:],"events":seen["events"][-MAX_SEEN_EVENTS:]},f,ensure_ascii=False,indent=2)

def already_seen(a,seen):
    if article_id(a) in seen["ids"]:
        return True
    for old in seen["events"]:
        if similarity(a.get("title",""),old.get("title","")) >= 0.86:
            return True
        if similarity(article_text(a),old.get("text",old.get("title",""))) >= 0.83:
            return True
    return False

def fetch_news():
    result=[]
    cutoff=datetime.now(timezone.utc)-timedelta(hours=MAX_AGE_HOURS)
    sources=[s for s in SOURCES if s.get("feed")]
    print(f"📚 إجمالي المصادر: {len(sources)}")
    for source in sources:
        try:
            feed=feedparser.parse(source["feed"])
            count=0
            for entry in feed.entries[:MAX_NEWS_PER_SOURCE]:
                title=(entry.get("title") or "").strip()
                if not title: continue
                published_at=published_time(entry)
                if published_at and published_at < cutoff: continue
                a={
                    "source":source.get("name",domain(source)),
                    "family":source_family(source),
                    "country":source.get("country",""),
                    "website":source.get("website",""),
                    "title":title,
                    "summary":(entry.get("summary") or "").strip(),
                    "link":(entry.get("link") or "").strip(),
                    "published_at":published_at,
                    "tier":source_tier(source)
                }
                if not is_political(a): continue
                a["importance"]=importance(a)
                a["_id"]=article_id(a)
                result.append(a); count+=1
            print(f"🔎 {source.get('name','مصدر')}: {count} خبر سياسي حديث")
        except Exception as exc:
            print(f"❌ {source.get('name','مصدر')}: {exc}")
    return result

def same_event(a,b):
    if a["family"] == b["family"]: return False
    title_score=similarity(a["title"],b["title"])
    full_score=similarity(article_text(a),article_text(b))
    common=words(article_text(a)) & words(article_text(b))
    if title_score >= .86 or full_score >= .86: return True
    event_words={norm(x) for x in IRAN_US+IRAQ+WORLD+IMPACT}
    return full_score >= .72 and len(common & event_words) >= 3

def group_news(news):
    ordered=sorted(news,key=lambda x:x["importance"],reverse=True)
    groups=[]; used=set()
    for i,a in enumerate(ordered):
        if i in used: continue
        group=[a]; used.add(i)
        for j in range(i+1,len(ordered)):
            if j not in used and same_event(a,ordered[j]):
                group.append(ordered[j]); used.add(j)
        groups.append(group)
    return groups

def select_groups(groups):
    candidates=[]
    for group in groups:
        score=max(a["importance"] for a in group)
        families={a["family"] for a in group}
        score=min(100,score+min(max(0,len(families)-1)*8,24))
        text=norm(" ".join(a["title"] for a in group))
        breaking=any(norm(k) in text for k in BREAKING)
        impact=any(norm(k) in text for k in IMPACT)
        t1=any(a["tier"]==1 for a in group)
        t2=any(a["tier"]==2 for a in group)
        verified=len(families)>=2 and score>=55
        single_t1=len(families)==1 and t1 and score>=72 and (breaking or impact)
        single_t2=len(families)==1 and t2 and score>=82 and breaking and impact
        if verified or single_t1 or single_t2:
            candidates.append((score,topic(group[0]),group))
    return sorted(candidates,key=lambda x:x[0],reverse=True)

def diversify(items):
    selected=[]; used=set()
    counts={"Iran-US":0,"Iraq":0,"World":0,"Other":0}
    remaining=list(items)
    while remaining and len(selected)<MAX_POSTS_PER_RUN:
        best_i=None; best_v=None
        for i,(score,tp,group) in enumerate(remaining):
            fams={a["family"] for a in group}
            value=score+(8 if counts[tp]==0 else 0)-(10 if counts[tp]>=2 else 0)+(12 if tp=="Iran-US" else 0)-(20 if fams & used else 0)
            if best_v is None or value>best_v:
                best_i,best_v=i,value
        item=remaining.pop(best_i); selected.append(item)
        counts[item[1]]+=1; used.update(a["family"] for a in item[2])
    return selected

def openai_allowed():
    if not OPENAI_KEY: return False
    try:
        with open(OPENAI_STATE_FILE,encoding="utf-8") as f: last=json.load(f).get("last_attempt")
        if last and (datetime.now(timezone.utc)-datetime.fromisoformat(last)).total_seconds()/60 < OPENAI_COOLDOWN_MINUTES:
            return False
    except Exception: pass
    return True

def openai_call(prompt):
    if not openai_allowed(): return None
    try:
        with open(OPENAI_STATE_FILE,"w",encoding="utf-8") as f:
            json.dump({"last_attempt":datetime.now(timezone.utc).isoformat()},f)
        r=session.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json={"model":OPENAI_MODEL,"input":prompt,"max_output_tokens":300},timeout=60)
        print("🤖 OpenAI Status:",r.status_code)
        if r.status_code != 200:
            print(r.text); return None
        data=r.json()
        if data.get("output_text"): return data["output_text"].strip()
        out=[]
        for item in data.get("output",[]):
            for c in item.get("content",[]):
                if c.get("type")=="output_text" and c.get("text"): out.append(c["text"])
        return "\n".join(out).strip() or None
    except Exception as exc:
        print("❌ OpenAI:",exc); return None

def verify_event(group):
    families={a["family"] for a in group}
    if len(families)<2:
        a=group[0]; text=norm(article_text(a))
        return len(group)==1 and a["tier"]==1 and a["importance"]>=72 and any(norm(k) in text for k in BREAKING+IMPACT)
    text="\n\n".join(f"المؤسسة: {a['source']}\nالعنوان: {a['title']}\nالتفاصيل: {a['summary']}" for a in group)
    answer=openai_call(f"""أنت مدقق أخبار سياسية. هل المصادر التالية تؤكد الواقعة نفسها فعلاً؟ لا تدمج أحداثاً مختلفة. أجب فقط YES أو NO.\n\n{text}""")
    if answer is None:
        return True
    return bool(re.search(r"\bYES\b",answer.upper()))

def make_post(group):
    lead=max(group,key=lambda a:a["importance"])
    sources=", ".join(dict.fromkeys(a["source"] for a in group[:4]))
    result=openai_call(f"""اكتب خبراً سياسياً عربياً قصيراً للنشر في تيليغرام. لا تضف أي معلومة غير موجودة. ابدأ بـ 🔴، واذكر المصدر. سطر أو سطران فقط.\nالمصادر: {sources}\nالعنوان: {lead['title']}\nالتفاصيل: {lead['summary']}""")
    if result and result.startswith("🔴"):
        return result[:1000]
    detail=re.sub(r"\s+"," ",lead["summary"]).strip()
    text=f"🔴 {lead['source']}: {lead['title']}"
    return text + (f"؛ {detail[:450]}" if detail else "")

def send(message):
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN غير موجود"); return False
    try:
        r=session.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",json={"chat_id":CHANNEL,"text":message,"disable_web_page_preview":False},timeout=30)
        print("📨 Telegram Status:",r.status_code)
        if r.status_code != 200: print(r.text); return False
        return bool(r.json().get("ok"))
    except Exception as exc:
        print("❌ Telegram:",exc); return False

def remember_group(group,text,seen):
    seen["ids"].update(article_id(a) for a in group)
    clean=re.sub(r"^🔴\s*","",text).strip()
    seen["events"].append({"title":clean,"text":clean,"time":datetime.now(timezone.utc).isoformat()})
    save_seen(seen)

def main():
    print("="*70)
    print("🚀 بدء تشغيل Telegram News Bot")
    seen=load_seen()
    all_news=fetch_news()
    print(f"📰 مجموع الأخبار السياسية الحديثة: {len(all_news)}")
    fresh=[a for a in all_news if not already_seen(a,seen)]
    print(f"🆕 بعد منع التكرار: {len(fresh)}")
    if not fresh:
        save_seen(seen); print("ℹ️ لا توجد أخبار جديدة."); return
    groups=group_news(fresh)
    print(f"🧩 عدد مجموعات الأحداث: {len(groups)}")
    candidates=select_groups(groups)
    print(f"🎯 بعد الفلترة: {len(candidates)}")
    selected=diversify(candidates)
    print(f"📌 المجموعات المختارة: {len(selected)}")
    published=0; fingerprints=[]
    for index,(_,tp,group) in enumerate(selected,1):
        print(f"\n🔎 المجموعة {index} | {tp}")
        for a in group: print(f"• {a['source']} | {a['title']} | أهمية {a['importance']}")
        if not verify_event(group): continue
        result=make_post(group)
        body=re.sub(r"^🔴\s*","",result).strip()
        if any(similarity(body,old)>=.78 for old in fingerprints): continue
        if send(result):
            published+=1; fingerprints.append(body); remember_group(group,result,seen)
            print(f"✅ تم نشر الخبر {published}/{MAX_POSTS_PER_RUN}")
        if published>=MAX_POSTS_PER_RUN: break
    save_seen(seen)
    print(f"🎉 انتهى التشغيل. عدد المنشورات الناجحة: {published}")

if __name__ == "__main__":
    main()
