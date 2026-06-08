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
    # ── Italiano ──
    {"url": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml", "lang": "it", "label": "ANSA"},
    {"url": "https://www.corriere.it/rss/homepage.xml", "lang": "it", "label": "Corriere"},
    {"url": "https://www.ansa.it/sito/ansait_rss.xml", "lang": "it", "label": "ANSA Italia"},
    {"url": "https://xml2.corriereobjects.it/rss/esteri.xml", "lang": "it", "label": "Corriere Esteri"},
    {"url": "https://www.repubblica.it/rss/esteri/rss2.0.xml", "lang": "it", "label": "Repubblica"},
    {"url": "https://www.ilsole24ore.com/rss/mondo.xml", "lang": "it", "label": "Sole 24 Ore"},
    # ── Internazionale (EN) ──
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "lang": "en", "label": "BBC"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "lang": "en", "label": "NYT"},
    {"url": "https://www.theguardian.com/world/rss", "lang": "en", "label": "Guardian"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "lang": "en", "label": "Al Jazeera"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml", "lang": "en", "label": "Sky News"},
    {"url": "https://www.cbsnews.com/latest/rss/world", "lang": "en", "label": "CBS"},
    # ── Europa (altre lingue) ──
    {"url": "https://www.tagesschau.de/index~rss2.xml", "lang": "de", "label": "Tagesschau"},
    {"url": "https://www.lemonde.fr/international/rss_full.xml", "lang": "fr", "label": "Le Monde"},
    {"url": "https://e00-elmundo.uecdn.es/elmundo/rss/internacional.xml", "lang": "es", "label": "El Mundo"},
]

# GDELT DOC 2.0 — keyless, immagini + paese + filtro lingua. Rate-limit 1 req / 5s.
GDELT_ENABLED = True
GDELT_QUERIES = [
    {"q": "sourcelang:italian", "lang": "it", "label": "GDELT-IT"},
    {"q": "sourcelang:english (war OR crisis OR election OR climate OR earthquake)", "lang": "en", "label": "GDELT-EN"},
]
_GDELT_LAST_CALL = [0.0]   # timestamp ultima chiamata per rate-limit
_GDELT_MIN_INTERVAL = 5.5

# ── SENTIMENT lexicon (per scoring veloce senza ML) ──
SENTIMENT_NEG = [
    "war", "guerra", "attack", "attacco", "bomb", "bomba", "kill", "morti", "dead",
    "death", "morte", "crisis", "crisi", "disaster", "disastro", "earthquake", "terremoto",
    "flood", "alluvione", "fire", "incendio", "victim", "vittime", "wound", "ferit",
    "violence", "violenza", "protest", "protesta", "strike", "sciopero", "collapse",
    "crollo", "recession", "recessione", "crash", "fear", "paura", "threat", "minaccia",
    "conflict", "conflitto", "missile", "invasion", "invasione", "terror", "terror",
    "fraud", "frode", "scandal", "scandalo", "arrest", "arrest", "emergency", "emergenza",
]
SENTIMENT_POS = [
    "peace", "pace", "deal", "accordo", "agreement", "intesa", "win", "vittoria",
    "growth", "crescita", "recovery", "ripresa", "success", "successo", "breakthrough",
    "svolta", "record", "rescue", "salvataggio", "hope", "speranza", "aid", "aiuto",
    "celebrate", "festa", "award", "premio", "boost", "rilancio", "innovation",
    "innovazione", "cure", "cura", "progress", "progresso", "historic", "storico",
]

def _score_sentiment(text):
    """Sentiment veloce keyword-based. Ritorna float in [-1, 1]."""
    lower = text.lower()
    neg = sum(1 for w in SENTIMENT_NEG if w in lower)
    pos = sum(1 for w in SENTIMENT_POS if w in lower)
    if neg == 0 and pos == 0:
        return 0.0
    raw = (pos - neg) / (pos + neg)
    # comprimi leggermente verso 0
    return round(max(-1.0, min(1.0, raw)), 3)

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
    "colombia": {"lat": 4.57, "lon": -74.30, "country": "Colombia"},
    "lima": {"lat": -12.05, "lon": -77.04, "country": "Peru"},
    "peru": {"lat": -9.19, "lon": -75.02, "country": "Peru"},
    "perù": {"lat": -9.19, "lon": -75.02, "country": "Peru"},
    "caracas": {"lat": 10.48, "lon": -66.90, "country": "Venezuela"},
    "venezuela": {"lat": 6.42, "lon": -66.59, "country": "Venezuela"},
    "argentina": {"lat": -38.42, "lon": -63.62, "country": "Argentina"},
    "ecuador": {"lat": -1.83, "lon": -78.18, "country": "Ecuador"},
    "bolivia": {"lat": -16.29, "lon": -63.59, "country": "Bolivia"},
    "chile": {"lat": -35.68, "lon": -71.54, "country": "Chile"},
    "cuba": {"lat": 21.52, "lon": -77.78, "country": "Cuba"},
    "honduras": {"lat": 15.20, "lon": -86.24, "country": "Honduras"},
    "nicaragua": {"lat": 12.87, "lon": -85.21, "country": "Nicaragua"},
    "paraguay": {"lat": -23.44, "lon": -58.44, "country": "Paraguay"},
    "uruguay": {"lat": -32.52, "lon": -55.77, "country": "Uruguay"},
    "guatemala": {"lat": 15.78, "lon": -90.23, "country": "Guatemala"},
    "panama": {"lat": 8.54, "lon": -80.78, "country": "Panama"},
    "costa rica": {"lat": 9.75, "lon": -83.75, "country": "Costa Rica"},
    "puerto rico": {"lat": 18.22, "lon": -66.59, "country": "Puerto Rico"},
    "repubblica dominicana": {"lat": 18.74, "lon": -70.16, "country": "Dominican Republic"},
    "haiti": {"lat": 18.97, "lon": -72.29, "country": "Haiti"},
    "algeria": {"lat": 28.03, "lon": 1.66, "country": "Algeria"},
    "marocco": {"lat": 31.95, "lon": -6.81, "country": "Morocco"},
    "tunisia": {"lat": 33.89, "lon": 9.54, "country": "Tunisia"},
    "libia": {"lat": 26.34, "lon": 17.23, "country": "Libya"},
    "sudan": {"lat": 12.86, "lon": 30.22, "country": "Sudan"},
    "etiopia": {"lat": 9.15, "lon": 40.49, "country": "Ethiopia"},
    "kenya": {"lat": -0.02, "lon": 37.91, "country": "Kenya"},
    "tanzania": {"lat": -6.37, "lon": 34.89, "country": "Tanzania"},
    "angola": {"lat": -11.20, "lon": 17.87, "country": "Angola"},
    "mozambico": {"lat": -18.67, "lon": 35.53, "country": "Mozambique"},
    "ghana": {"lat": 7.95, "lon": -1.02, "country": "Ghana"},
    "senegal": {"lat": 14.50, "lon": -14.45, "country": "Senegal"},
    "congo": {"lat": -0.23, "lon": 15.83, "country": "Congo"},
    "ucraina": {"lat": 48.38, "lon": 31.17, "country": "Ukraine"},
    "libano": {"lat": 33.85, "lon": 35.86, "country": "Lebanon"},
    "giordania": {"lat": 31.24, "lon": 36.51, "country": "Jordan"},
    "egitto": {"lat": 26.82, "lon": 30.80, "country": "Egypt"},
    "turchia": {"lat": 38.96, "lon": 35.24, "country": "Turkey"},
    "grecia": {"lat": 39.07, "lon": 21.82, "country": "Greece"},
    "serbia": {"lat": 44.02, "lon": 21.01, "country": "Serbia"},
    "croazia": {"lat": 45.10, "lon": 15.20, "country": "Croatia"},
    "romania": {"lat": 45.94, "lon": 24.97, "country": "Romania"},
    "bulgaria": {"lat": 42.73, "lon": 25.49, "country": "Bulgaria"},
    "polonia": {"lat": 51.92, "lon": 19.15, "country": "Poland"},
    "svezia": {"lat": 60.13, "lon": 18.64, "country": "Sweden"},
    "norvegia": {"lat": 60.47, "lon": 8.47, "country": "Norway"},
    "danimarca": {"lat": 56.26, "lon": 9.50, "country": "Denmark"},
    "finlandia": {"lat": 61.92, "lon": 25.75, "country": "Finland"},
    "olanda": {"lat": 52.13, "lon": 5.29, "country": "Netherlands"},
    "belgio": {"lat": 50.50, "lon": 4.47, "country": "Belgium"},
    "svizzera": {"lat": 46.82, "lon": 8.23, "country": "Switzerland"},
    "austria": {"lat": 47.52, "lon": 14.55, "country": "Austria"},
    "portogallo": {"lat": 39.40, "lon": -8.22, "country": "Portugal"},
    "irlanda": {"lat": 53.41, "lon": -8.24, "country": "Ireland"},
    "scozia": {"lat": 56.49, "lon": -4.20, "country": "UK"},
    "galles": {"lat": 52.13, "lon": -3.78, "country": "UK"},
    "inghilterra": {"lat": 52.36, "lon": -1.17, "country": "UK"},
    "germania": {"lat": 51.17, "lon": 10.45, "country": "Germany"},
    "giappone": {"lat": 36.20, "lon": 138.25, "country": "Japan"},
    "corea": {"lat": 35.91, "lon": 127.77, "country": "South Korea"},
    "vietnam": {"lat": 14.06, "lon": 108.28, "country": "Vietnam"},
    "tailandia": {"lat": 15.87, "lon": 100.99, "country": "Thailand"},
    "indonesia": {"lat": -0.79, "lon": 113.92, "country": "Indonesia"},
    "filippine": {"lat": 12.88, "lon": 121.77, "country": "Philippines"},
    "nuova zelanda": {"lat": -40.90, "lon": 174.89, "country": "New Zealand"},
    "sudafrica": {"lat": -30.56, "lon": 22.94, "country": "South Africa"},
    "arabia saudita": {"lat": 23.89, "lon": 45.08, "country": "Saudi Arabia"},
    "emirati arabi": {"lat": 23.42, "lon": 53.85, "country": "UAE"},
    "qatar": {"lat": 25.35, "lon": 51.18, "country": "Qatar"},
    "kuwait": {"lat": 29.31, "lon": 47.48, "country": "Kuwait"},
    "oman": {"lat": 21.47, "lon": 55.98, "country": "Oman"},
    "yemen": {"lat": 15.55, "lon": 48.52, "country": "Yemen"},
    "siria": {"lat": 34.80, "lon": 39.00, "country": "Syria"},
    "afghanistan": {"lat": 33.94, "lon": 67.71, "country": "Afghanistan"},
    "mongolia": {"lat": 46.86, "lon": 103.85, "country": "Mongolia"},
    "nepal": {"lat": 28.39, "lon": 84.12, "country": "Nepal"},
    "bangladesh": {"lat": 23.68, "lon": 90.36, "country": "Bangladesh"},
    "myanmar": {"lat": 21.92, "lon": 95.96, "country": "Myanmar"},
    "cambogia": {"lat": 12.57, "lon": 104.99, "country": "Cambodia"},
    "messico": {"lat": 19.43, "lon": -99.13, "country": "Mexico"},
    "cina": {"lat": 35.86, "lon": 104.19, "country": "China"},
    "russia": {"lat": 61.52, "lon": 105.32, "country": "Russia"},
    "francia": {"lat": 46.60, "lon": 1.89, "country": "France"},
    "spagna": {"lat": 40.42, "lon": -3.70, "country": "Spain"},
    "regno unito": {"lat": 55.38, "lon": -3.44, "country": "UK"},
    "stati uniti": {"lat": 39.83, "lon": -98.58, "country": "USA"},
    "usa": {"lat": 39.83, "lon": -98.58, "country": "USA"},
}

EVENT_KEYWORDS = {
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

# ── nomi paese → coordinate (per geo-fallback da GDELT sourcecountry) ──
_COUNTRY_TO_COORD = {}
for _name, _loc in LOCATIONS.items():
    _cn = _loc["country"].lower()
    if _cn not in _COUNTRY_TO_COORD:
        _COUNTRY_TO_COORD[_cn] = _loc

def _fetch_gdelt():
    """Fetch da GDELT DOC 2.0 (immagini, paese, lingua). Rate-limited."""
    if not GDELT_ENABLED:
        return []
    items = []
    for gq in GDELT_QUERIES:
        # rate-limit globale 1 req / 5.5s
        wait = _GDELT_MIN_INTERVAL - (time.time() - _GDELT_LAST_CALL[0])
        if wait > 0:
            time.sleep(min(wait, 6))
        try:
            from urllib.parse import quote
            url = ("https://api.gdeltproject.org/api/v2/doc/doc?query=" + quote(gq["q"]) +
                   "&mode=artlist&maxrecords=30&format=json&timespan=1d&sort=DateDesc")
            r = _req.get(url, headers={"User-Agent": "Jarvis/2.0"}, timeout=20, verify=False)
            _GDELT_LAST_CALL[0] = time.time()
            ct = r.headers.get("content-type", "")
            if "json" not in ct and not r.text.strip().startswith("{"):
                continue
            data = r.json()
            for a in data.get("articles", []):
                title = a.get("title", "")
                if not title:
                    continue
                items.append({
                    "title": title,
                    "snippet": "",
                    "url": a.get("url", ""),
                    "source": (a.get("domain", "") or gq["label"]).replace("www.", "")[:24],
                    "lang": gq["lang"],
                    "published": a.get("seendate", ""),
                    "text": title,
                    "image": a.get("socialimage", ""),
                    "sourcecountry": a.get("sourcecountry", ""),
                })
        except Exception:
            _GDELT_LAST_CALL[0] = time.time()
            continue
    return items

# parole comuni da escludere dal trending
_STOP = set("the a an of to in on and or for with from by at as is are was were be been "
            "il lo la i gli le un uno una di a da in con su per tra fra e o ma se che "
            "del della dei delle al alla ai alle dal dalla nel nella sul sulla con non "
            "più che chi cosa come dove quando dopo prima oggi news new video dell della "
            "after world over into this that they them will would could about have has had "
            "their there been more most some what when where which while says said also "
            "anche essere stato sono erano fino solo molto cosa così senza dopo ancora "
            "contro verso ogni quella quello questi queste tutto tutti года year years".split())

def _compute_trending(news, top=12):
    """Estrae le keyword più frequenti dai titoli (escludendo stopword)."""
    from collections import Counter
    cnt = Counter()
    for n in news:
        words = re.findall(r"[A-Za-zÀ-ÿ]{4,}", (n.get("title") or "").lower())
        for w in words:
            if w in _STOP:
                continue
            cnt[w] += 1
    return [{"word": w, "count": c} for w, c in cnt.most_common(top) if c >= 2]

def _compute_stats(news):
    """Statistiche aggregate per categoria, paese, sentiment."""
    from collections import Counter
    by_cat = Counter(n.get("category", "general") for n in news)
    by_country = Counter(n.get("country") for n in news if n.get("country"))
    sents = [n.get("sentiment", 0) for n in news]
    avg_sent = round(sum(sents) / len(sents), 3) if sents else 0
    neg = sum(1 for s in sents if s < -0.1)
    pos = sum(1 for s in sents if s > 0.1)
    return {
        "by_category": dict(by_cat.most_common()),
        "by_country": dict(by_country.most_common(8)),
        "sentiment_avg": avg_sent,
        "sentiment_neg": neg,
        "sentiment_pos": pos,
        "geo_count": sum(1 for n in news if n.get("lat") is not None),
    }

def fetch_world_news(max_items=50):
    """Fetch news da RSS + GDELT, geo-localizza, categorizza, sentiment, trending, stats."""
    now = time.time()
    if "all_geo" in _NEWS_CACHE and (now - _NEWS_CACHE["all_geo"]["time"]) < _CACHE_TTL:
        c = _NEWS_CACHE["all_geo"]
        return {"news": c["data"][:max_items], "total": len(c["data"]),
                "trending": c.get("trending", []), "stats": c.get("stats", {}),
                "timestamp": datetime.now().isoformat()}

    all_news = []
    for feed in FEEDS:
        all_news.extend(_fetch_feed(feed))
    # GDELT (best-effort, non blocca se fallisce)
    try:
        all_news.extend(_fetch_gdelt())
    except Exception:
        pass

    seen = set()
    geo_news = []
    for item in all_news:
        dedup = item["title"][:60].lower().strip()
        if not dedup or dedup in seen:
            continue
        seen.add(dedup)

        text = item.get("text") or item["title"]
        geo = _geo_locate(text)
        cat = _categorize(text)
        sentiment = _score_sentiment(text)
        entry = {
            "title": item["title"],
            "snippet": item.get("snippet", ""),
            "url": item["url"],
            "source": item["source"],
            "lang": item["lang"],
            "category": cat,
            "sentiment": sentiment,
            "published": item.get("published", ""),
        }
        if item.get("image"):
            entry["image"] = item["image"]
        if geo:
            entry["lat"] = geo[0]; entry["lon"] = geo[1]
            entry["country"] = geo[2]; entry["location"] = geo[3]
        elif item.get("sourcecountry"):
            # fallback: usa il paese della fonte GDELT
            coord = _COUNTRY_TO_COORD.get(item["sourcecountry"].lower())
            if coord:
                entry["lat"] = coord["lat"]; entry["lon"] = coord["lon"]
                entry["country"] = coord["country"]; entry["location"] = coord["country"]
        geo_news.append(entry)

    # ordina: geo-localizzate prima, poi per |sentiment| (notizie forti in cima)
    geo_news.sort(key=lambda n: (n.get("lat") is None, -abs(n.get("sentiment", 0))))

    trending = _compute_trending(geo_news)
    stats = _compute_stats(geo_news)
    _NEWS_CACHE["all_geo"] = {"data": geo_news, "time": now,
                             "trending": trending, "stats": stats}
    return {"news": geo_news[:max_items], "total": len(geo_news),
            "trending": trending, "stats": stats,
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
