"""jarvis_worldnews.py — World News with geo-location engine"""
import json, time, re, xml.etree.ElementTree as ET
from datetime import datetime
import requests as _req
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_NEWS_CACHE = {}
_GEO_CACHE = {}
_CACHE_TTL = 600

FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/rss.xml", "lang": "en", "label": "BBC"},
    {"url": "https://www.tagesschau.de/xml/atom", "lang": "de", "label": "Tagesschau"},
    {"url": "https://www.ansa.it/sito/ansait_rss.xml", "lang": "it", "label": "ANSA"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "lang": "en", "label": "NYT"},
    {"url": "https://feeds.npr.org/1001/rss.xml", "lang": "en", "label": "NPR"},
]

LOCATIONS = {
    "ukraine": {"lat": 48.38, "lon": 31.17, "country": "Ukraine"},
    "kyiv": {"lat": 50.45, "lon": 30.52, "country": "Ukraine"},
    "kiev": {"lat": 50.45, "lon": 30.52, "country": "Ukraine"},
    "kharkiv": {"lat": 50.00, "lon": 36.23, "country": "Ukraine"},
    "odessa": {"lat": 46.49, "lon": 30.74, "country": "Ukraine"},
    "moscow": {"lat": 55.76, "lon": 37.62, "country": "Russia"},
    "russia": {"lat": 61.52, "lon": 105.32, "country": "Russia"},
    "moscow": {"lat": 55.76, "lon": 37.62, "country": "Russia"},
    "st petersburg": {"lat": 59.93, "lon": 30.36, "country": "Russia"},
    "beijing": {"lat": 39.91, "lon": 116.40, "country": "China"},
    "china": {"lat": 35.86, "lon": 104.19, "country": "China"},
    "shanghai": {"lat": 31.23, "lon": 121.47, "country": "China"},
    "taiwan": {"lat": 23.70, "lon": 121.00, "country": "Taiwan"},
    "tokyo": {"lat": 35.68, "lon": 139.69, "country": "Japan"},
    "japan": {"lat": 36.20, "lon": 138.25, "country": "Japan"},
    "seoul": {"lat": 37.57, "lon": 126.98, "country": "South Korea"},
    "berlin": {"lat": 52.52, "lon": 13.41, "country": "Germany"},
    "germany": {"lat": 51.17, "lon": 10.45, "country": "Germany"},
    "paris": {"lat": 48.86, "lon": 2.35, "country": "France"},
    "france": {"lat": 46.60, "lon": 1.89, "country": "France"},
    "london": {"lat": 51.51, "lon": -0.13, "country": "UK"},
    "uk": {"lat": 55.38, "lon": -3.44, "country": "UK"},
    "roma": {"lat": 41.90, "lon": 12.50, "country": "Italy"},
    "rome": {"lat": 41.90, "lon": 12.50, "country": "Italy"},
    "italy": {"lat": 41.87, "lon": 12.57, "country": "Italy"},
    "milano": {"lat": 45.46, "lon": 9.19, "country": "Italy"},
    "milan": {"lat": 45.46, "lon": 9.19, "country": "Italy"},
    "new york": {"lat": 40.71, "lon": -74.01, "country": "USA"},
    "washington": {"lat": 38.91, "lon": -77.04, "country": "USA"},
    "los angeles": {"lat": 34.05, "lon": -118.24, "country": "USA"},
    "san francisco": {"lat": 37.77, "lon": -122.42, "country": "USA"},
    "miami": {"lat": 25.76, "lon": -80.19, "country": "USA"},
    "chicago": {"lat": 41.88, "lon": -87.63, "country": "USA"},
    "usa": {"lat": 39.83, "lon": -98.58, "country": "USA"},
    "delhi": {"lat": 28.70, "lon": 77.10, "country": "India"},
    "india": {"lat": 20.59, "lon": 78.96, "country": "India"},
    "mumbai": {"lat": 19.08, "lon": 72.88, "country": "India"},
    "jerusalem": {"lat": 31.77, "lon": 35.22, "country": "Israel"},
    "tel aviv": {"lat": 32.09, "lon": 34.78, "country": "Israel"},
    "israel": {"lat": 31.05, "lon": 34.85, "country": "Israel"},
    "gaza": {"lat": 31.50, "lon": 34.47, "country": "Palestine"},
    "cairo": {"lat": 30.04, "lon": 31.24, "country": "Egypt"},
    "egypt": {"lat": 26.82, "lon": 30.80, "country": "Egypt"},
    "dubai": {"lat": 25.20, "lon": 55.27, "country": "UAE"},
    "uae": {"lat": 23.42, "lon": 53.85, "country": "UAE"},
    "istanbul": {"lat": 41.01, "lon": 28.98, "country": "Turkey"},
    "ankara": {"lat": 39.93, "lon": 32.86, "country": "Turkey"},
    "turkey": {"lat": 38.96, "lon": 35.24, "country": "Turkey"},
    "tehran": {"lat": 35.69, "lon": 51.39, "country": "Iran"},
    "iran": {"lat": 32.43, "lon": 53.69, "country": "Iran"},
    "riyadh": {"lat": 24.71, "lon": 46.68, "country": "Saudi Arabia"},
    "doha": {"lat": 25.29, "lon": 51.53, "country": "Qatar"},
    "islamabad": {"lat": 33.68, "lon": 73.05, "country": "Pakistan"},
    "pakistan": {"lat": 30.38, "lon": 69.35, "country": "Pakistan"},
    "kabul": {"lat": 34.56, "lon": 69.21, "country": "Afghanistan"},
    "baghdad": {"lat": 33.32, "lon": 44.36, "country": "Iraq"},
    "iraq": {"lat": 33.22, "lon": 43.68, "country": "Iraq"},
    "damascus": {"lat": 33.51, "lon": 36.29, "country": "Syria"},
    "beirut": {"lat": 33.89, "lon": 35.50, "country": "Lebanon"},
    "amman": {"lat": 31.95, "lon": 35.93, "country": "Jordan"},
    "cape town": {"lat": -33.92, "lon": 18.42, "country": "South Africa"},
    "johannesburg": {"lat": -26.20, "lon": 28.04, "country": "South Africa"},
    "nairobi": {"lat": -1.29, "lon": 36.82, "country": "Kenya"},
    "lagos": {"lat": 6.52, "lon": 3.38, "country": "Nigeria"},
    "addis ababa": {"lat": 9.03, "lon": 38.75, "country": "Ethiopia"},
    "rabat": {"lat": 34.02, "lon": -6.84, "country": "Morocco"},
    "sydney": {"lat": -33.87, "lon": 151.21, "country": "Australia"},
    "melbourne": {"lat": -37.81, "lon": 144.96, "country": "Australia"},
    "australia": {"lat": -25.27, "lon": 133.77, "country": "Australia"},
    "bangkok": {"lat": 13.76, "lon": 100.50, "country": "Thailand"},
    "singapore": {"lat": 1.35, "lon": 103.82, "country": "Singapore"},
    "hong kong": {"lat": 22.32, "lon": 114.17, "country": "China"},
    "kuala lumpur": {"lat": 3.14, "lon": 101.69, "country": "Malaysia"},
    "manila": {"lat": 14.60, "lon": 120.98, "country": "Philippines"},
    "jakarta": {"lat": -6.21, "lon": 106.85, "country": "Indonesia"},
    "hanoi": {"lat": 21.03, "lon": 105.85, "country": "Vietnam"},
    "mexico city": {"lat": 19.43, "lon": -99.13, "country": "Mexico"},
    "mexico": {"lat": 23.63, "lon": -102.55, "country": "Mexico"},
    "brasilia": {"lat": -15.79, "lon": -47.88, "country": "Brazil"},
    "brazil": {"lat": -14.24, "lon": -51.93, "country": "Brazil"},
    "buenos aires": {"lat": -34.60, "lon": -58.38, "country": "Argentina"},
    "santiago": {"lat": -33.45, "lon": -70.67, "country": "Chile"},
    "bogota": {"lat": 4.71, "lon": -74.07, "country": "Colombia"},
    "lima": {"lat": -12.05, "lon": -77.04, "country": "Peru"},
    "caracas": {"lat": 10.48, "lon": -66.90, "country": "Venezuela"},
    "stockholm": {"lat": 59.33, "lon": 18.07, "country": "Sweden"},
    "oslo": {"lat": 59.91, "lon": 10.75, "country": "Norway"},
    "copenhagen": {"lat": 55.68, "lon": 12.57, "country": "Denmark"},
    "helsinki": {"lat": 60.17, "lon": 24.94, "country": "Finland"},
    "warsaw": {"lat": 52.24, "lon": 21.01, "country": "Poland"},
    "prague": {"lat": 50.08, "lon": 14.42, "country": "Czech Republic"},
    "vienna": {"lat": 48.21, "lon": 16.37, "country": "Austria"},
    "budapest": {"lat": 47.50, "lon": 19.04, "country": "Hungary"},
    "madrid": {"lat": 40.42, "lon": -3.70, "country": "Spain"},
    "barcelona": {"lat": 41.39, "lon": 2.16, "country": "Spain"},
    "lisbon": {"lat": 38.72, "lon": -9.14, "country": "Portugal"},
    "brussels": {"lat": 50.85, "lon": 4.35, "country": "Belgium"},
    "amsterdam": {"lat": 52.37, "lon": 4.90, "country": "Netherlands"},
    "zurich": {"lat": 47.37, "lon": 8.54, "country": "Switzerland"},
    "geneva": {"lat": 46.20, "lon": 6.14, "country": "Switzerland"},
    "athens": {"lat": 37.98, "lon": 23.73, "country": "Greece"},
}

EVENT_KEYWORDS = {
    "conflict": ["war", "attack", "strike", "bomb", "missile", "military", "troop",
                 "offensive", "defense", "nato", "invasion", "ceasefire"],
    "disaster": ["earthquake", "flood", "hurricane", "wildfire", "tsunami", "storm",
                 "drought", "landslide", "eruption", "tornado"],
    "politics": ["election", "vote", "parliament", "president", "summit", "sanction",
                 "diplomat", "treaty", "referendum", "protest", "rally"],
    "economy": ["market", "stock", "trade", "tariff", "inflation", "recession",
                "gdp", "bank", "crypto", "oil", "sanction"],
    "climate": ["climate", "emission", "renewable", "carbon", "cop", "warming",
                "temperature", "co2"],
    "tech": ["ai", "robot", "space", "launch", "satellite", "chip", "quantum",
             "nasa", "spacex", "nuclear"],
}

def _geo_locate(text):
    """Estrae location dalla news text, restituisce (lat, lon, country, name) o None."""
    lower = text.lower()
    best = None
    best_len = 0
    for name, loc in LOCATIONS.items():
        # Use word boundary for short names (≤3 chars) to avoid false matches
        if len(name) <= 3:
            pattern = r'\b' + re.escape(name) + r'\b'
            if not re.search(pattern, lower):
                continue
        elif name not in lower:
            continue
        # Prefer the longest match to avoid "uk" matching inside "ukraine"
        if not best or len(name) > best_len:
            best = (loc["lat"], loc["lon"], loc["country"], name.title())
            best_len = len(name)
    return best

def _categorize(text):
    """Categorizza la news in base alle keyword."""
    lower = text.lower()
    for cat, keywords in EVENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return cat
    return "general"

def _fetch_feed(feed):
    """Fetch e parse singolo feed RSS/Atom."""
    try:
        r = _req.get(feed["url"], headers={"User-Agent": "Jarvis/1.0"}, timeout=15, verify=False)
        raw = r.content
        root = ET.fromstring(raw)
    except:
        return []

    items = []
    # Try RSS 2.0
    for entry in root.iter("item"):
        title = entry.findtext("title", "")
        desc = entry.findtext("description", "")
        link = entry.findtext("link", "")
        pub = entry.findtext("pubDate", "")
        text = f"{title} {desc}"
        items.append({"title": title, "snippet": desc[:200], "url": link,
                       "source": feed["label"], "lang": feed["lang"],
                       "published": pub, "text": text})
    # Try Atom
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.iter("atom:entry"):
            title = entry.findtext("atom:title", "", ns)
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            pub = entry.findtext("atom:published", "", ns)
            content = entry.findtext("atom:summary", "", ns) or entry.findtext("atom:content", "", ns)
            text = f"{title} {content}"
            items.append({"title": title, "snippet": (content or "")[:200],
                           "url": link, "source": feed["label"],
                           "lang": feed["lang"], "published": pub, "text": text})
    return items

def fetch_world_news(max_items=50):
    """Fetch news da tutti i feed, geo-localizza e categorizza."""
    now = time.time()
    if "all_geo" in _NEWS_CACHE and (now - _NEWS_CACHE["all_geo"]["time"]) < _CACHE_TTL:
        geo_news = _NEWS_CACHE["all_geo"]["data"]
        return {"news": geo_news[:max_items], "total": len(geo_news),
                "timestamp": datetime.now().isoformat()}

    all_news = []
    for feed in FEEDS:
        all_news.extend(_fetch_feed(feed))

    seen = set()
    geo_news = []
    for item in all_news:
        dedup = item["title"][:60]
        if dedup in seen:
            continue
        seen.add(dedup)

        geo = _geo_locate(item["text"])
        cat = _categorize(item["text"])
        entry = {
            "title": item["title"],
            "snippet": item["snippet"],
            "url": item["url"],
            "source": item["source"],
            "lang": item["lang"],
            "category": cat,
            "published": item["published"],
        }
        if geo:
            entry["lat"] = geo[0]
            entry["lon"] = geo[1]
            entry["country"] = geo[2]
            entry["location"] = geo[3]
        geo_news.append(entry)

    _NEWS_CACHE["all_geo"] = {"data": geo_news, "time": now}
    return {"news": geo_news[:max_items], "total": len(geo_news),
            "timestamp": datetime.now().isoformat()}

def format_for_prompt(news_data, max_items=5):
    """Formatta news per injection nel prompt LLM."""
    items = news_data.get("news", [])[:max_items]
    if not items:
        return ""
    lines = ["🌍 NOTIZIE DAL MONDO (geo-localizzate):"]
    for i, n in enumerate(items, 1):
        loc = n.get("location", n.get("country", "Sconosciuto"))
        cat = n["category"]
        icon = {"conflict": "⚔", "disaster": "🌊", "politics": "🏛",
                "economy": "💰", "climate": "🌿", "tech": "🔬"}.get(cat, "📰")
        lines.append(f"{i}. {icon} [{loc}] {n['title']} ({n['source']})")
    return "\n".join(lines)

if __name__ == "__main__":
    data = fetch_world_news(10)
    print(json.dumps(data, indent=2, ensure_ascii=False))
