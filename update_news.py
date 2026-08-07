#!/usr/bin/env python3
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import html
import sys

RSS_SOURCES = [
    {"name": "中新网即时", "url": "https://www.chinanews.com.cn/rss/scroll-news.xml", "category": "综合", "priority": 1},
    {"name": "人民网时政", "url": "http://www.people.com.cn/rss/politics.xml", "category": "时政", "priority": 2},
    {"name": "中国日报-中国", "url": "http://www.chinadaily.com.cn/rss/china_rss.xml", "category": "综合", "priority": 3},
    {"name": "中国日报-财经", "url": "http://www.chinadaily.com.cn/rss/bizchina_rss.xml", "category": "经济", "priority": 3},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ChinaDailyNewsBot/1.0)", "Accept": "application/rss+xml, application/xml, text/xml, */*"}
OUTPUT_FILE = Path(__file__).parent / "index.html"
MAX_ITEMS_PER_SOURCE = 12
TOTAL_DISPLAY = 40

def fetch_rss(source):
    items = []
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
            title = clean_text(entry.get("title", ""))
            link = entry.get("link", "")
            summary = clean_text(entry.get("summary", entry.get("description", "")))
            summary = re.sub(r"<[^>]+>", "", summary)[:120]
            published = parse_date(entry)
            if title and link:
                items.append({"title": title, "link": link, "summary": summary, "source": source["name"], "category": source["category"], "published": published, "priority": source["priority"]})
    except Exception as e:
        print(f"[警告] 无法获取 {source['name']}: {e}")
    return items

def clean_text(text):
    if not text: return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def parse_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        if hasattr(entry, key) and getattr(entry, key):
            try: return datetime(*getattr(entry, key)[:6], tzinfo=timezone.utc)
            except: pass
    return datetime.now(timezone.utc)

def categorize(item):
    text = (item["title"] + item["summary"]).lower()
    if any(k in text for k in ["习近平", "中共中央", "政治局", "总书记", "国务院", "人大", "政协"]): return "时政"
    if any(k in text for k in ["经济", "外贸", "进出口", "gdp", "股市", "金融", "投资", "消费", "产业"]): return "经济"
    if any(k in text for k in ["台风", "暴雨", "地震", "高温", "气象", "防汛", "灾害", "预警"]): return "气象防灾"
    if any(k in text for k in ["科技", "航天", "卫星", "人工智能", "ai", "芯片", "创新", "研发"]): return "科技"
    if any(k in text for k in ["教育", "学校", "医疗", "健康", "民生", "就业", "社保"]): return "社会民生"
    return item.get("category", "综合")

def generate_html(all_items):
    now = datetime.now(timezone(timedelta(hours=8)))
    date_str = now.strftime("%Y年%m月%d日")
    weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    update_time = now.strftime("%H:%M")
    seen = set()
    unique = []
    for item in sorted(all_items, key=lambda x: (x["priority"], -x["published"].timestamp())):
        t = item["title"][:40]
        if t not in seen:
            seen.add(t)
            item["category"] = categorize(item)
            unique.append(item)
        if len(unique) >= TOTAL_DISPLAY: break
    groups = {"时政": [], "经济": [], "科技": [], "社会民生": [], "气象防灾": [], "综合": []}
    for item in unique:
        cat = item["category"]
        groups[cat if cat in groups else "综合"].append(item)
    top = unique[:5]

    def card(item, large=False):
        title = html.escape(item["title"])
        summary = html.escape(item["summary"] or "")
        source = html.escape(item["source"])
        link = html.escape(item["link"])
        cat = html.escape(item["category"])
        pub = item["published"].astimezone(timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
        if large:
            return f'<a href="{link}" target="_blank" rel="noopener" class="card large"><span class="tag">{cat}</span><h3>{title}</h3><p>{summary}</p><div class="meta"><span>{source}</span><span>{pub}</span></div></a>'
        return f'<a href="{link}" target="_blank" rel="noopener" class="card"><span class="tag">{cat}</span><h3>{title}</h3><div class="meta"><span>{source}</span><span>{pub}</span></div></a>'

    def lst(items, limit=8):
        parts = []
        for i, item in enumerate(items[:limit], 1):
            title = html.escape(item["title"])
            link = html.escape(item["link"])
            source = html.escape(item["source"])
            pub = item["published"].astimezone(timezone(timedelta(hours=8))).strftime("%m-%d")
            parts.append(f'<a href="{link}" target="_blank" rel="noopener" class="list-item"><span class="num">{i}</span><div class="info"><h4>{title}</h4><span class="meta">{source} · {pub}</span></div></a>')
        return "\n".join(parts)

    top_html = "\n".join(card(item, large=(i==0)) for i, item in enumerate(top))
    sections = ""
    for name, items in groups.items():
        if not items: continue
        sections += f'<section class="section"><div class="section-header"><h2>{name}</h2><span class="count">{len(items)} 条</span></div><div class="list">{lst(items)}</div></section>'

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中国每日新闻 · {date_str}</title>
<style>
:root{{--primary:#c41e3a;--bg:#f4f4f6;--card:#fff;--text:#1a1a1a;--muted:#666;--border:#e8e8ed;--radius:10px;--shadow:0 2px 12px rgba(0,0,0,.06)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.55}}
a{{text-decoration:none;color:inherit}}
header{{background:linear-gradient(135deg,#c41e3a,#8b1538);color:#fff;padding:18px 20px;position:sticky;top:0;z-index:50;box-shadow:0 2px 10px rgba(196,30,58,.25)}}
.header-inner{{max-width:1100px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
.logo{{display:flex;align-items:center;gap:12px}}
.logo-icon{{width:38px;height:38px;background:#fff;color:var(--primary);border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px}}
.logo h1{{font-size:20px;font-weight:700}}
.logo small{{display:block;font-size:12px;opacity:.85;font-weight:400}}
.update-badge{{background:rgba(255,255,255,.15);padding:6px 14px;border-radius:20px;font-size:13px}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 50px}}
.hero{{display:grid;grid-template-columns:1.4fr 1fr;gap:16px;margin-bottom:32px}}
@media(max-width:800px){{.hero{{grid-template-columns:1fr}}}}
.card{{background:var(--card);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);transition:transform .15s,box-shadow .15s;display:block}}
.card:hover{{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,.1)}}
.card.large{{grid-row:span 2}}
.card .tag{{display:inline-block;background:#fef2f2;color:var(--primary);font-size:11px;font-weight:600;padding:2px 8px;border-radius:4px;margin-bottom:8px}}
.card h3{{font-size:16px;font-weight:600;line-height:1.4;margin-bottom:8px}}
.card.large h3{{font-size:20px}}
.card p{{font-size:13px;color:var(--muted);margin-bottom:10px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.meta{{font-size:12px;color:#999;display:flex;justify-content:space-between}}
.section{{margin-bottom:28px}}
.section-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid var(--primary)}}
.section-header h2{{font-size:18px;font-weight:700;display:flex;align-items:center;gap:8px}}
.section-header h2::before{{content:"";width:4px;height:18px;background:var(--primary);border-radius:2px}}
.count{{font-size:12px;color:var(--muted)}}
.list{{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}}
.list-item{{display:flex;gap:14px;padding:14px 18px;border-bottom:1px solid var(--border);transition:background .12s;align-items:flex-start}}
.list-item:last-child{{border-bottom:none}}
.list-item:hover{{background:#fafafa}}
.num{{width:24px;height:24px;background:var(--primary);color:#fff;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0}}
.list-item:nth-child(n+4) .num{{background:#e5e5ea;color:#555}}
.info h4{{font-size:14.5px;font-weight:600;line-height:1.4;margin-bottom:3px}}
.info .meta{{font-size:12px;color:var(--muted)}}
footer{{text-align:center;padding:28px 16px;font-size:12px;background:#1a1a1a;color:rgba(255,255,255,.6)}}
.auto-note{{background:#eef7ff;border:1px solid #b6d4fe;border-radius:8px;padding:12px 16px;margin-bottom:24px;font-size:13px;color:#084298}}
</style>
</head>
<body>
<header>
<div class="header-inner">
<div class="logo"><div class="logo-icon">中</div><div><h1>中国每日新闻</h1><small>自动聚合 · 每日更新</small></div></div>
<div class="update-badge">{date_str} {weekday} · 更新于 {update_time}</div>
</div>
</header>
<main>
<div class="auto-note">📡 本页面由脚本自动从公开 RSS 源抓取生成，每日可定时更新。</div>
<div class="hero" style="display:contents">{top_html}</div>
{sections}
</main>
<footer>
<p>中国每日新闻聚合 · 数据来自公开 RSS · 非官方媒体</p>
<p style="margin-top:6px;opacity:.7">上次生成时间：{now.strftime("%Y-%m-%d %H:%M:%S")} (北京时间)</p>
</footer>
</body>
</html>'''

def main():
    print("开始抓取新闻源...")
    all_items = []
    for source in RSS_SOURCES:
        print(f"  → {source['name']} ...", end=" ")
        items = fetch_rss(source)
        print(f"获取 {len(items)} 条")
        all_items.extend(items)
    print(f"\\n共获取 {len(all_items)} 条原始新闻")
    html_content = generate_html(all_items)
    OUTPUT_FILE.write_text(html_content, encoding="utf-8")
    print(f"✅ 已生成：{OUTPUT_FILE}")

if __name__ == "__main__":
    main()
