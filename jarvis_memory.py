#!/usr/bin/env python3
"""jarvis_memory.py — memoria persistente SQLite con FTS5"""
import sqlite3, json, os
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "jarvis_memory.db"

class JarvisMemory:
    def __init__(self):
        DB_PATH.parent.mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS memories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT 'fact',
            content TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            importance INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, content_rowid=id, tokenize='unicode61')""")
        c.execute("""CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
        END""")
        c.execute("""CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
        END""")
        c.execute("""CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
        END""")
        c.execute("""CREATE TABLE IF NOT EXISTS preferences(
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS conversation_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        self.db.commit()

    def remember(self, content, category="fact", tags=None, importance=1):
        tags = json.dumps(tags or [])
        c = self.db.cursor()
        c.execute("INSERT INTO memories (category, content, tags, importance) VALUES (?,?,?,?)",
                  (category, content, tags, importance))
        self.db.commit()
        return f"Ricordato: {content[:60]}..." if len(content) > 60 else f"Ricordato: {content}"

    def _escape_fts(self, query):
        """Escapes special chars for FTS5 MATCH"""
        import re
        # Wrap in quotes to prevent column interpretation
        escaped = re.sub(r'["\\]', '', query)
        return f'"{escaped}"'

    def search(self, query, limit=10, category=None):
        c = self.db.cursor()
        safe_query = self._escape_fts(query)
        if category:
            c.execute("""SELECT m.* FROM memories m JOIN memories_fts f ON m.id=f.rowid
                WHERE f.content MATCH ? AND m.category=? ORDER BY rank LIMIT ?""",
                (safe_query, category, limit))
        else:
            c.execute("""SELECT m.* FROM memories m JOIN memories_fts f ON m.id=f.rowid
                WHERE f.content MATCH ? ORDER BY rank LIMIT ?""", (safe_query, limit))
        rows = [dict(r) for r in c.fetchall()]
        return rows if rows else [{"content": f"Nessun ricordo per: {query}"}]

    def get_all(self, category=None, limit=50):
        c = self.db.cursor()
        if category:
            c.execute("SELECT * FROM memories WHERE category=? ORDER BY created_at DESC LIMIT ?",
                      (category, limit))
        else:
            c.execute("SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def delete_memory(self, memory_id):
        c = self.db.cursor()
        c.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        self.db.commit()
        return f"Memoria {memory_id} eliminata"

    def set_preference(self, key, value):
        c = self.db.cursor()
        c.execute("INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                  (key, json.dumps(value) if not isinstance(value, str) else value))
        self.db.commit()
        return f"Preferenza salvata: {key} = {value}"

    def get_preference(self, key, default=None):
        c = self.db.cursor()
        c.execute("SELECT value FROM preferences WHERE key=?", (key,))
        row = c.fetchone()
        if row:
            try: return json.loads(row["value"])
            except: return row["value"]
        return default

    def get_all_preferences(self):
        c = self.db.cursor()
        c.execute("SELECT key, value FROM preferences ORDER BY updated_at DESC")
        result = {}
        for r in c.fetchall():
            try: result[r["key"]] = json.loads(r["value"])
            except: result[r["key"]] = r["value"]
        return result

    def log_conversation(self, role, content):
        c = self.db.cursor()
        c.execute("INSERT INTO conversation_log (role, content) VALUES (?, ?)", (role, content))
        self.db.commit()

    def get_recent_conversations(self, limit=20):
        c = self.db.cursor()
        c.execute("SELECT * FROM conversation_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_context_for_prompt(self, query="", max_items=5):
        facts = self.search(query, limit=max_items) if query else self.get_all(limit=max_items)
        prefs = self.get_all_preferences()
        context = "PREFERENZE UTENTE:\n"
        for k, v in prefs.items():
            context += f"- {k}: {v}\n"
        context += "\nRICORDI RECENTI:\n"
        for f in facts:
            context += f"- [{f.get('category','fact')}] {f['content']}\n"
        return context.strip()

    def stats(self):
        c = self.db.cursor()
        c.execute("SELECT COUNT(*) as total FROM memories")
        total = c.fetchone()["total"]
        c.execute("SELECT category, COUNT(*) as cnt FROM memories GROUP BY category ORDER BY cnt DESC")
        by_cat = {r["category"]: r["cnt"] for r in c.fetchall()}
        c.execute("SELECT COUNT(*) as total FROM conversation_log")
        convos = c.fetchone()["total"]
        return {"total_memories": total, "by_category": by_cat, "conversation_entries": convos}

    def close(self):
        self.db.close()
