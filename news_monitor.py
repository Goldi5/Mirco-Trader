#!/usr/bin/env python3
"""
News-Monitor – holt stündlich Wirtschafts- und Aktien-Headlines.
"""
import json, os, time
from datetime import datetime
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
NEWS_CACHE = os.path.join(BASE, "news_cache.json")

# RSS-Feeds (kein API-Key nötig)
FEEDS = [
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "https://finance.yahoo.com/news/rssindex",
    "https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_headlines",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
]

KEYWORDS = {
    "interest rate": ["interest rate", "fed", "federal reserve", "rate hike", "rate cut", "zins"],
    "earnings": ["earnings", "quarterly results", "gewinn", "results"],
    "merger": ["merger", "acquisition", "übernahme", "buyout", "takeover"],
    "regulation": ["regulation", "sec", "regulatory", "regulierung", "klage", "lawsuit"],
    "recession": ["recession", "recession fears", "wirtschaftskrise", "recession warning"],
    "inflation": ["inflation", "cpi", "consumer price", "inflation data"],
    "tech": ["tech", "technology", "semiconductor", "ai", "chip", "künstliche intelligenz"],
    "energy": ["oil", "crude", "energy", "gas", "öl", "energie"],
    "market": ["market", "stock market", "dow", "s&p", "nasdaq", "index"],
    "geopolitics": ["war", "conflict", "trade war", "tariff", "zoll", "sanktion", "sanction"],
    "crypto": ["bitcoin", "crypto", "blockchain", "ethereum", "krypto"],
}

def fetch_rss(url, timeout=10):
    """Holt einen RSS-Feed und gibt Headlines zurück."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pubdate = item.findtext("pubDate", "")
            if title:
                items.append({"title": title.strip(), "link": link, "date": pubdate})
        return items
    except Exception as e:
        return []

def classify_headline(title):
    """Klassifiziert eine Headline nach relevanten Themen."""
    title_lower = title.lower()
    matches = []
    for category, kws in KEYWORDS.items():
        for kw in kws:
            if kw in title_lower:
                matches.append(category)
                break
    return matches

def update_news():
    """Holt aktuelle News und speichert sie."""
    alle = []
    for url in FEEDS:
        items = fetch_rss(url)
        if items:
            print(f"  ✅ {len(items)} von {url.split('/')[2]}")
        alle.extend(items[:15])  # max 15 pro Feed
        time.sleep(1)

    # Relevante Headlines
    relevant = []
    for item in alle:
        cats = classify_headline(item["title"])
        if cats:
            relevant.append({**item, "topics": cats})

    # Nach Aktien tickern suchen
    for item in relevant:
        tickers_found = []
        for ticker in ["AAPL","MSFT","TSLA","NVDA","AMD","META","AMZN","GOOGL",
                       "JPM","BAC","COIN","GME","PLTR","LCID","RIVN","F","GM",
                       "HOOD","SOFI","TQQQ","MARA"]:
            if ticker in item["title"] or f"${ticker}" in item["title"]:
                tickers_found.append(ticker)
        if tickers_found:
            item["tickers"] = tickers_found

    data = {
        "zeit": datetime.now().isoformat(),
        "total": len(alle),
        "relevant": len(relevant),
        "headlines": relevant[:30] if relevant else [{"title": "Keine relevanten News"}],
    }
    with open(NEWS_CACHE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n  📰 {len(alle)} Headlines gesammet, {len(relevant)} relevant")
    for h in relevant[:5]:
        print(f"    • {h['title'][:100]}")

if __name__ == "__main__":
    print("  📡 News-Monitor...")
    update_news()
