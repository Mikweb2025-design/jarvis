"""jarvis_trends.py — Trend monitoring module for Jarvis"""
import json, time
from datetime import datetime

_TRENDS_CACHE = {}
_CACHE_TTL = 300  # 5 minuti

def _cached(key, ttl=_CACHE_TTL):
    def deco(fn):
        def wrapper(*a, **kw):
            now = time.time()
            if key in _TRENDS_CACHE and (now - _TRENDS_CACHE[key]["time"]) < ttl:
                return _TRENDS_CACHE[key]["data"]
            result = fn(*a, **kw)
            _TRENDS_CACHE[key] = {"data": result, "time": now}
            return result
        return wrapper
    return deco

CATEGORY_MAP = {
    "technology": "tecnologia tendenze 2026",
    "ai": "intelligenza artificiale novita 2026",
    "german": "deutschland technologietrends 2026",
    "italian": "italia tecnologia trend 2026",
    "startup": "startup innovazione 2026",
    "opensource": "open source progetti nuovi 2026",
    "social": "tendenze social media 2026",
    "coding": "programmazione linguaggi framework 2026",
}

REGION_MAP = {
    "it": "it-IT",
    "de": "de-DE",
    "us": "en-US",
    "gb": "en-GB",
    "fr": "fr-FR",
    "es": "es-ES",
    "wt": "wt-wt",
}

def trends_search(category="technology", region="wt-wt", max_results=10):
    """Cerca trend utilizzando DuckDuckGo."""
    query = CATEGORY_MAP.get(category, category)
    region_code = REGION_MAP.get(region, region)
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region=region_code, max_results=max_results))
        if not results:
            return {"status": "ok", "query": query, "results": [], "count": 0}
        items = []
        for r in results:
            items.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
        return {"status": "ok", "query": query, "region": region_code, "results": items, "count": len(items)}
    except ImportError:
        return {"status": "error", "message": "duckduckgo_search non installato. pip install duckduckgo_search"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def trending_now(region="it"):
    """Trend del momento — shortcut veloce."""
    categories = ["technology", "ai", "social"]
    combined = []
    for cat in categories:
        result = trends_search(category=cat, region=region, max_results=5)
        if result["status"] == "ok":
            combined.extend(result["results"])
    seen = set()
    unique = []
    for item in combined:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return {"status": "ok", "region": region, "results": unique[:15], "count": min(len(unique), 15)}

def format_trends_for_prompt(results, max_items=5):
    """Formatta trend per injection nel prompt LLM."""
    items = results.get("results", [])[:max_items]
    if not items:
        return ""
    lines = ["📊 TREND ATTUALI:"]
    for i, r in enumerate(items, 1):
        lines.append(f"{i}. {r['title']} — {r['snippet'][:100]}")
    return "\n".join(lines)
