#!/usr/bin/env python3
"""jarvis_plugins.py — Plugin Store, Marketplace & Auto-Scaling v2.0
Inspirato da OpenClaw ClawHub.
Features:
  - Marketplace GitHub-index con categorie
  - Auto-update con version checking
  - Community ratings (locali)
  - Dipendenze automatiche
  - Plugin discovery e search
"""
import json, os, sys, importlib, subprocess, requests, tempfile, zipfile, shutil, time, hashlib, re
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent / "data"
PLUGINS_DIR = Path(__file__).parent / "plugins"
MARKETPLACE_CACHE = DATA_DIR / "marketplace_cache.json"
MARKETPLACE_INDEX_URL = "https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/index.json"
DB_PATH = DATA_DIR / "plugins.db"

PLUGINS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

LOCAL_PLUGIN_INDEX = [
    {"name":"smart_reply","version":"1.0.0","description":"Risposte email smart con AI (tono professionale, amichevole o conciso)","author":"JARVIS","category":"productivity","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/smart_reply.py","dependencies":["requests"],"homepage":"","license":"MIT"},
    {"name":"summarize_article","version":"1.0.0","description":"Riassume articoli web o testi lunghi con AI, estrae contenuto da URL","author":"JARVIS","category":"productivity","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/summarize_article.py","dependencies":["requests"],"homepage":"","license":"MIT"},
    {"name":"web_scraper","version":"1.0.0","description":"Advanced web scraping with CSS selectors, pagination, and export","author":"JARVIS","category":"web","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/web_scraper.py","dependencies":["beautifulsoup4","lxml"],"homepage":"","license":"MIT"},
    {"name":"data_viz","version":"1.0.0","description":"Generate charts and visualizations from data (bar, line, scatter, pie)","author":"JARVIS","category":"data","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/data_viz.py","dependencies":["matplotlib","pandas"],"homepage":"","license":"MIT"},
    {"name":"pdf_tools","version":"1.0.0","description":"PDF manipulation: merge, split, extract text, convert to images","author":"JARVIS","category":"documents","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/pdf_tools.py","dependencies":["PyMuPDF"],"homepage":"","license":"MIT"},
    {"name":"social_poster","version":"1.0.0","description":"Post to social media platforms (Twitter, LinkedIn, Instagram)","author":"JARVIS","category":"social","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/social_poster.py","dependencies":["tweepy","requests"],"homepage":"","license":"MIT"},
    {"name":"image_gen","version":"1.0.0","description":"AI image generation with local Stable Diffusion or API","author":"JARVIS","category":"media","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/image_gen.py","dependencies":["torch","diffusers"],"homepage":"","license":"MIT"},
    {"name":"crypto_tracker","version":"1.0.0","description":"Track cryptocurrency prices, portfolios, and alerts","author":"JARVIS","category":"finance","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/crypto_tracker.py","dependencies":["requests"],"homepage":"","license":"MIT"},
    {"name":"weather_pro","version":"1.0.0","description":"Advanced weather with maps, radar, and severe weather alerts","author":"JARVIS","category":"utilities","url":"https://raw.githubusercontent.com/anomalyco/jarvis-plugins/main/weather_pro.py","dependencies":["requests"],"homepage":"","license":"MIT"},
]

CATEGORIES = {
    "web": "🌐 Web & Browser",
    "data": "📊 Data & Analytics",
    "documents": "📄 Document Processing",
    "social": "📱 Social Media",
    "media": "🎬 Media & Image",
    "finance": "💰 Finance & Crypto",
    "utilities": "🔧 Utilities & Tools",
    "development": "💻 Development",
    "ai": "🤖 AI & Machine Learning",
    "automation": "⚡ Automation",
    "games": "🎮 Gaming",
    "music": "🎵 Music & Audio",
    "productivity": "📋 Productivity",
}


class PluginManager:
    def __init__(self):
        self._plugins = {}
        self._marketplace_index = None
        self._last_index_fetch = 0
        self._load_plugins()

    def _init_db(self):
        import sqlite3
        self._db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        c = self._db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS plugins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            version TEXT DEFAULT '1.0.0',
            author TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            enabled INTEGER DEFAULT 1,
            installed_path TEXT DEFAULT '',
            dependencies TEXT DEFAULT '[]',
            homepage TEXT DEFAULT '',
            license TEXT DEFAULT '',
            created TEXT DEFAULT (datetime('now')),
            last_updated TEXT DEFAULT (datetime('now')),
            last_version_check TEXT DEFAULT '',
            update_available TEXT DEFAULT ''
        )""")
        for col in ["rating", "rating_count"]:
            try:
                c.execute(f"ALTER TABLE plugins ADD COLUMN {col} DEFAULT 0")
            except:
                pass
        c.execute("""CREATE TABLE IF NOT EXISTS plugin_reviews(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plugin_name TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            review TEXT DEFAULT '',
            created TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS marketplace_index(
            name TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            fetched TEXT DEFAULT (datetime('now'))
        )""")
        self._db.commit()

    def _load_plugins(self):
        self._init_db()
        c = self._db.cursor()
        c.execute("SELECT * FROM plugins WHERE enabled=1")
        for row in c.fetchall():
            name = row["name"]
            path = row["installed_path"]
            if path and os.path.exists(path):
                try:
                    spec = importlib.util.spec_from_file_location(name, path)
                    if spec:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        self._plugins[name] = mod
                except Exception as e:
                    print(f"  [Plugins] Failed to load {name}: {e}")

    def _fetch_marketplace_index(self, force=False):
        """Fetch real marketplace index from GitHub, fallback a locale."""
        if not force and self._marketplace_index:
            return True
        try:
            resp = requests.get(MARKETPLACE_INDEX_URL, timeout=10)
            if resp.ok:
                data = resp.json()
                self._marketplace_index = data if isinstance(data, list) else data.get("plugins", [data])
                self._last_index_fetch = time.time()
                MARKETPLACE_CACHE.write_text(json.dumps(self._marketplace_index, indent=2))
                c = self._db.cursor()
                for p in self._marketplace_index:
                    c.execute("""INSERT OR REPLACE INTO marketplace_index (name, data)
                                  VALUES (?, ?)""", (p.get("name", "unknown"), json.dumps(p)))
                self._db.commit()
                return True
        except:
            pass
        # Fallback a cache locale
        if MARKETPLACE_CACHE.exists():
            try:
                self._marketplace_index = json.loads(MARKETPLACE_CACHE.read_text())
                return True
            except:
                pass
        # Fallback a indice built-in
        self._marketplace_index = LOCAL_PLUGIN_INDEX
        return True

    def list_plugins(self, include_disabled=False):
        c = self._db.cursor()
        if include_disabled:
            c.execute("SELECT * FROM plugins ORDER BY category, name")
        else:
            c.execute("SELECT * FROM plugins WHERE enabled=1 ORDER BY category, name")
        plugins = [dict(r) for r in c.fetchall()]
        if not plugins:
            return "Nessun plugin installato"
        lines = ["📦 Plugin Store:"]
        current_cat = ""
        for p in plugins:
            cat_label = CATEGORIES.get(p["category"], p["category"])
            if p["category"] != current_cat:
                lines.append(f"\n  {cat_label}:")
                current_cat = p["category"]
            loaded = "🟢" if p["name"] in self._plugins else "⚪"
            update = " ⬆" if p.get("update_available") else ""
            rating = f" ⭐{p['rating']:.1f}" if p.get("rating_count", 0) else ""
            lines.append(f"    {loaded} {p['name']} v{p['version']}{update}{rating}")
            lines.append(f"       {p['description'][:70]}")
        return "\n".join(lines)

    def install(self, source, name=None):
        """Install a plugin from marketplace, URL, or file path."""
        if source in [p.get("name") for p in (self._marketplace_index or [])]:
            return self._install_from_marketplace(source, name)
        if source.startswith(("http://", "https://")):
            return self._install_from_url(source, name)
        if os.path.exists(source):
            return self._install_from_file(source, name)
        self._fetch_marketplace_index()
        if self._marketplace_index:
            for p in self._marketplace_index:
                if p.get("name") == source or p.get("name", "").lower() == source.lower():
                    return self._install_from_marketplace(p["name"], name)
            matches = [p for p in self._marketplace_index
                       if source.lower() in p.get("name", "").lower()
                       or source.lower() in p.get("description", "").lower()]
            if matches:
                return self._install_from_marketplace(matches[0]["name"], name)
        return f"Plugin '{source}' non trovato nel marketplace"

    def _install_from_marketplace(self, name, alias=None):
        if not self._marketplace_index:
            self._fetch_marketplace_index()
        info = None
        for p in (self._marketplace_index or []):
            if p.get("name") == name:
                info = p
                break
        if not info:
            return f"Plugin '{name}' non trovato nel marketplace"
        url = info.get("url", "") or info.get("download_url", "")
        if not url:
            return f"Nessun URL per '{name}'"
        target_name = alias or info.get("name", name)
        return self._install_from_url(url, target_name, info)

    def _install_from_url(self, url, name, info=None):
        try:
            resp = requests.get(url, timeout=30)
            if not resp.ok:
                return f"Download fallito: HTTP {resp.status_code}"
            code = resp.text
            target_path = PLUGINS_DIR / f"{name}.py"
            target_path.write_text(code)
            deps = (info or {}).get("dependencies", [])
            dep_results = []
            for dep in deps:
                try:
                    subprocess.run([sys.executable, "-m", "pip", "install", dep, "--quiet"],
                                   capture_output=True, timeout=60)
                    dep_results.append(f"{dep} ok")
                except:
                    dep_results.append(f"{dep} fallito")
            c = self._db.cursor()
            info_version = (info or {}).get("version", "1.0.0")
            c.execute("""INSERT OR REPLACE INTO plugins
                          (name, description, version, author, category, installed_path, dependencies, homepage, license)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (name,
                       (info or {}).get("description", "Plugin installato da URL"),
                       info_version,
                       (info or {}).get("author", "Sconosciuto"),
                       (info or {}).get("category", "general"),
                       str(target_path),
                       json.dumps(deps),
                       (info or {}).get("homepage", ""),
                       (info or {}).get("license", "")))
            self._db.commit()
            try:
                spec = importlib.util.spec_from_file_location(name, str(target_path))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self._plugins[name] = mod
            except Exception as e:
                return f"Installato ma caricamento fallito: {e}"
            dep_str = f" + dipendenze: {', '.join(dep_results)}" if dep_results else ""
            return f"✅ Plugin '{name}' v{info_version} installato{dep_str}"
        except Exception as e:
            return f"❌ Installazione fallita: {e}"

    def _install_from_file(self, file_path, name):
        name = name or Path(file_path).stem
        target_path = PLUGINS_DIR / f"{name}.py"
        if os.path.abspath(file_path) == os.path.abspath(str(target_path)):
            return self._register_local(name, str(target_path))
        shutil.copy2(file_path, str(target_path))
        return self._register_local(name, str(target_path))

    def _register_local(self, name, path):
        c = self._db.cursor()
        c.execute("""INSERT OR REPLACE INTO plugins (name, installed_path)
                      VALUES (?, ?)""", (name, path))
        self._db.commit()
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._plugins[name] = mod
        except Exception as e:
            return f"Registrato ma caricamento fallito: {e}"
        return f"✅ Plugin '{name}' registrato da {path}"

    def uninstall(self, name):
        c = self._db.cursor()
        c.execute("SELECT installed_path FROM plugins WHERE name=?", (name,))
        row = c.fetchone()
        if not row:
            return f"Plugin '{name}' non trovato"
        path = row["installed_path"]
        c.execute("DELETE FROM plugins WHERE name=?", (name,))
        self._db.commit()
        if path and os.path.exists(path):
            os.unlink(path)
        if name in self._plugins:
            del self._plugins[name]
        return f"🗑 Plugin '{name}' disinstallato"

    def enable(self, name):
        c = self._db.cursor()
        c.execute("UPDATE plugins SET enabled=1 WHERE name=?", (name,))
        self._db.commit()
        self._load_plugins()
        return f"✅ Plugin '{name}' attivato"

    def disable(self, name):
        c = self._db.cursor()
        c.execute("UPDATE plugins SET enabled=0 WHERE name=?", (name,))
        self._db.commit()
        if name in self._plugins:
            del self._plugins[name]
        return f"⏹ Plugin '{name}' disattivato"

    def search_marketplace(self, query=""):
        """Cerca nel marketplace remoto per nome, descrizione, categoria."""
        self._fetch_marketplace_index()
        results = []
        if not self._marketplace_index:
            return results
        for p in self._marketplace_index:
            name = p.get("name", "")
            desc = p.get("description", "")
            cat = p.get("category", "")
            if not query or query.lower() in name.lower() or query.lower() in desc.lower() or query.lower() in cat.lower():
                installed = self._is_installed(name)
                p["_installed"] = installed
                p["_installed_version"] = self._get_installed_version(name) if installed else ""
                results.append(p)
        return results

    def marketplace_catalog(self, category=""):
        """Mostra catalogo marketplace con categorie."""
        self._fetch_marketplace_index()
        if not self._marketplace_index:
            return "Impossibile caricare il marketplace. Riprova più tardi."
        plugins = self._marketplace_index
        if category:
            plugins = [p for p in plugins if p.get("category", "").lower() == category.lower()]
        if not plugins:
            return f"Nessun plugin trovato{f' in {category}' if category else ''}"
        lines = ["🏪 JARVIS Plugin Marketplace:"]
        if not category:
            by_cat = {}
            for p in plugins:
                by_cat.setdefault(p.get("category", "general"), []).append(p)
            for cat, items in sorted(by_cat.items()):
                cat_label = CATEGORIES.get(cat, cat.capitalize())
                lines.append(f"\n  📂 {cat_label} ({len(items)}):")
                for p in items:
                    ver = p.get("version", "1.0")
                    rating = f" ⭐{p.get('rating', 0):.1f}" if p.get("rating") else ""
                    installed = "📥" if p.get("_installed") else "  "
                    lines.append(f"    {installed} {p['name']} v{ver}{rating}")
                    lines.append(f"       {p.get('description', '')[:70]}")
                    lines.append(f"       Autore: {p.get('author', '?')} | Install: plugins_install(\"{p['name']}\")")
        else:
            for p in plugins:
                ver = p.get("version", "1.0")
                lines.append(f"\n  📦 {p['name']} v{ver}")
                lines.append(f"     {p.get('description', '')}")
                lines.append(f"     Autore: {p.get('author', '?')} | Categoria: {p.get('category', 'general')}")
        return "\n".join(lines)

    def get_plugin_info(self, name):
        c = self._db.cursor()
        c.execute("SELECT * FROM plugins WHERE name=?", (name,))
        row = c.fetchone()
        if row:
            p = dict(row)
            status = "🟢 caricato" if p["name"] in self._plugins else "⚪ disattivato"
            update = f"\n  ⬆ Aggiornamento: {p['update_available']}" if p.get("update_available") else ""
            rating = f"\n  ⭐ {p['rating']:.1f} ({p['rating_count']} voti)" if p["rating_count"] else ""
            return (f"📦 {p['name']} v{p['version']}{update}{rating}\n"
                    f"  {p['description']}\n"
                    f"  Autore: {p['author']} | Categoria: {CATEGORIES.get(p['category'], p['category'])}\n"
                    f"  Stato: {status}\n"
                    f"  Path: {p['installed_path']}")
        self._fetch_marketplace_index()
        if self._marketplace_index:
            for p in self._marketplace_index:
                if p.get("name") == name:
                    return (f"📦 {p['name']} v{p.get('version', '1.0')}\n"
                            f"  {p.get('description', '')}\n"
                            f"  Autore: {p.get('author', '?')} | Categoria: {p.get('category', 'general')}\n"
                            f"  Homepage: {p.get('homepage', '—')}\n"
                            f"  Licenza: {p.get('license', '—')}\n"
                            f"  Dipendenze: {', '.join(p.get('dependencies', [])) or 'nessuna'}\n"
                            f"  Stato: non installato")
        return f"Plugin '{name}' non trovato"

    def check_updates(self):
        """Controlla aggiornamenti per tutti i plugin installati."""
        self._fetch_marketplace_index()
        if not self._marketplace_index:
            return "Marketplace non disponibile per check aggiornamenti"
        c = self._db.cursor()
        c.execute("SELECT * FROM plugins")
        installed = [dict(r) for r in c.fetchall()]
        if not installed:
            return "Nessun plugin installato"
        updates = []
        for p in installed:
            for mp in self._marketplace_index:
                if mp.get("name") == p["name"] and mp.get("version", "") > p["version"]:
                    updates.append({"name": p["name"], "current": p["version"], "available": mp["version"]})
                    c.execute("UPDATE plugins SET update_available=? WHERE name=?", (mp["version"], p["name"]))
        self._db.commit()
        if not updates:
            return "✅ Tutti i plugin sono aggiornati"
        lines = ["⬆ Aggiornamenti disponibili:"]
        for u in updates:
            lines.append(f"  • {u['name']}: {u['current']} → {u['available']}")
            lines.append(f"    plugins_install(\"{u['name']}\") per aggiornare")
        return "\n".join(lines)

    def update_all(self):
        """Aggiorna tutti i plugin con versione più recente."""
        self._fetch_marketplace_index()
        if not self._marketplace_index:
            return "Marketplace non disponibile"
        c = self._db.cursor()
        c.execute("SELECT * FROM plugins WHERE update_available != ''")
        outdated = [dict(r) for r in c.fetchall()]
        if not outdated:
            return "Nessun plugin da aggiornare"
        results = []
        for p in outdated:
            result = self.install(p["name"])
            results.append(f"  {p['name']}: {result}")
        c.execute("UPDATE plugins SET update_available=''")
        self._db.commit()
        return "✅ Aggiornamento completato:\n" + "\n".join(results)

    def rate_plugin(self, name, rating, review=""):
        """Aggiunge una valutazione a un plugin."""
        rating = max(1, min(5, int(rating)))
        c = self._db.cursor()
        c.execute("INSERT INTO plugin_reviews (plugin_name, rating, review) VALUES (?, ?, ?)",
                  (name, rating, review[:500]))
        c.execute("""UPDATE plugins SET
                      rating=(SELECT COALESCE(AVG(rating), 0) FROM plugin_reviews WHERE plugin_name=?),
                      rating_count=(SELECT COUNT(*) FROM plugin_reviews WHERE plugin_name=?)
                      WHERE name=?""", (name, name, name))
        self._db.commit()
        return f"⭐ Valutazione {rating}/5 registrata per '{name}'"

    def get_reviews(self, name):
        c = self._db.cursor()
        c.execute("SELECT * FROM plugin_reviews WHERE plugin_name=? ORDER BY created DESC", (name,))
        reviews = [dict(r) for r in c.fetchall()]
        if not reviews:
            return f"Nessuna recensione per '{name}'"
        lines = [f"⭐ Recensioni per '{name}':"]
        for r in reviews:
            stars = "⭐" * r["rating"]
            lines.append(f"  {stars} ({r['created'][:10]})")
            if r["review"]:
                lines.append(f"     {r['review'][:100]}")
        return "\n".join(lines)

    def _is_installed(self, name):
        c = self._db.cursor()
        c.execute("SELECT name FROM plugins WHERE name=?", (name,))
        return c.fetchone() is not None

    def _get_installed_version(self, name):
        c = self._db.cursor()
        c.execute("SELECT version FROM plugins WHERE name=?", (name,))
        row = c.fetchone()
        return row["version"] if row else ""

    def run_plugin(self, name, func_name=None, **kwargs):
        """Execute a function from an installed plugin."""
        if name not in self._plugins:
            return f"Plugin '{name}' non caricato. Installalo e attivalo prima."
        plugin = self._plugins[name]
        if func_name:
            func = getattr(plugin, func_name, None)
            if not func:
                return f"Funzione '{func_name}' non trovata in '{name}'"
            try:
                return func(**kwargs)
            except Exception as e:
                return f"Errore plugin: {e}"
        for attr_name in dir(plugin):
            if not attr_name.startswith("_") and callable(getattr(plugin, attr_name)):
                try:
                    return getattr(plugin, attr_name)(**kwargs)
                except Exception as e:
                    return f"Errore plugin: {e}"
        return f"Nessuna funzione trovata in '{name}'"

    def plugins_health(self):
        c = self._db.cursor()
        c.execute("SELECT * FROM plugins")
        installed = [dict(r) for r in c.fetchall()]
        if not installed:
            return "Nessun plugin installato"
        healthy = sum(1 for p in installed if p["name"] in self._plugins)
        total = len(installed)
        updates = sum(1 for p in installed if p.get("update_available"))
        lines = [f"🔌 Plugin: {healthy}/{total} sani"]
        if updates:
            lines.append(f"  ⬆ {updates} aggiornamenti disponibili (plugins_check_updates)")
        if total - healthy > 0:
            lines.append(f"  ⚠ {total - healthy} falliti al caricamento")
        return "\n".join(lines)


plugins = PluginManager()
