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


# ═══════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH — grafo di entità e relazioni tra memorie
# ═══════════════════════════════════════════════════════════════

class KnowledgeGraph:
    """Memoria a grafo: estrae entità dalle conversazioni e le collega tra loro."""

    TOPIC_KEYWORDS = {
        "code": ["codice", "programma", "python", "script", "function", "bug", "debug",
                 "repo", "git", "commit", "branch", "api", "server", "database", "sql",
                 "algoritmo", "classe", "metodo", "variabile", "refactor", "test"],
        "business": ["riunione", "meeting", "progetto", "scadenza", "cliente", "fattura",
                     "budget", "obiettivo", "kpi", "report", "strategia", "business",
                     "lavoro", "ufficio", "team", "manager", "presentazione"],
        "wellbeing": ["benessere", "salute", "relax", "pausa", "meditazione", "yoga",
                      "palestra", "corsa", "dieta", "sonno", "stress", "ansia",
                      "tranquillo", "calma", "respiro", "energia", "umore"],
        "casual": ["ciao", "come stai", "che fai", "raga", "amico", "bella",
                   "tutto bene", "che si dice", "novità", "weekend", "serata"],
    }

    def __init__(self, db_conn):
        self.db = db_conn
        self._init_tables()

    def _init_tables(self):
        c = self.db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS graph_entities(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            entity_type TEXT DEFAULT 'concept',
            first_seen TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now')),
            importance INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS graph_relations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            last_seen TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(source_id) REFERENCES graph_entities(id),
            FOREIGN KEY(target_id) REFERENCES graph_entities(id),
            UNIQUE(source_id, target_id, relation)
        )""")
        self.db.commit()

    def _ensure_entity(self, name, entity_type="concept"):
        c = self.db.cursor()
        try:
            c.execute("INSERT INTO graph_entities (name, entity_type) VALUES (?, ?)",
                      (name.strip().lower(), entity_type))
        except sqlite3.IntegrityError:
            c.execute("UPDATE graph_entities SET last_seen=datetime('now'), "
                      "importance = MIN(importance + 1, 10) WHERE name=?",
                      (name.strip().lower(),))
        self.db.commit()
        c.execute("SELECT id FROM graph_entities WHERE name=?", (name.strip().lower(),))
        return c.fetchone()["id"]

    def add_triple(self, subject, relation, obj, subject_type="concept", obj_type="concept"):
        """Aggiunge una tripla (soggetto → relazione → oggetto) al grafo."""
        sid = self._ensure_entity(subject, subject_type)
        oid = self._ensure_entity(obj, obj_type)
        c = self.db.cursor()
        try:
            c.execute("""INSERT INTO graph_relations (source_id, target_id, relation, weight)
                         VALUES (?, ?, ?, 1.0)""", (sid, oid, relation.lower()))
        except sqlite3.IntegrityError:
            c.execute("""UPDATE graph_relations SET weight = MIN(weight + 0.5, 5.0),
                         last_seen = datetime('now')
                         WHERE source_id=? AND target_id=? AND relation=?""",
                      (sid, oid, relation.lower()))
        self.db.commit()

    def extract_from_text(self, text):
        """Estrae triplette semplici dal testo (senza LLM, basato su pattern)."""
        import re
        triples = []
        text_lower = text.lower()

        # Pattern: "NAME è/è un TYPE" → (NAME, is_a, TYPE)
        for m in re.finditer(r'(\w+)\s+è\s+(?:un|una|uno)?\s*(\w+)', text_lower):
            triples.append((m.group(1), "is_a", m.group(2)))

        # Pattern: "NAME ha/ha TYPE" o "NAME preferisce TYPE"
        for m in re.finditer(r'(\w+)\s+(?:ha|ama|odia|usa|preferisce|vuole|sa|conosce|lavora con|studia)\s+(\w+)', text_lower):
            verb = m.group(0).split()[1]
            triples.append((m.group(1), verb, m.group(2)))

        # Pattern: "NAME di TYPE" / "NAME in TYPE"
        for m in re.finditer(r'(\w+)\s+(?:di|del|della|dei)\s+(\w+)', text_lower):
            triples.append((m.group(1), "di", m.group(2)))

        # Estrai topic dal testo
        topics = self._detect_topic(text)
        for topic in topics:
            triples.append(("conversazione", "topic", topic))

        for s, r, o in triples:
            if len(s) > 1 and len(o) > 1:
                self.add_triple(s, r, o)
        return triples

    def _detect_topic(self, text):
        topics = set()
        low = text.lower()
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            if any(k in low for k in keywords):
                topics.add(topic)
        return topics or {"general"}

    def extract_from_conversation(self, user_msg, assistant_reply):
        """Estrae e registra triplette da una coppia di messaggi."""
        triples = []
        triples.extend(self.extract_from_text(user_msg))
        triples.extend(self.extract_from_text(assistant_reply))
        return triples

    def get_context_for_prompt(self, query="", max_relations=10):
        """Restituisce un blocco di testo con le entità e relazioni rilevanti."""
        c = self.db.cursor()
        if query:
            # Cerca entità correlate alla query
            c.execute("""SELECT e.name, e.entity_type, e.importance
                         FROM graph_entities e
                         WHERE e.name LIKE ? OR e.name IN (
                            SELECT DISTINCT e2.name FROM graph_entities e2
                            JOIN graph_relations r ON r.source_id=e2.id OR r.target_id=e2.id
                            WHERE e2.name LIKE ?
                         )
                         ORDER BY e.importance DESC LIMIT 15""",
                      (f'%{query.lower()}%', f'%{query.lower()}%'))
        else:
            c.execute("""SELECT name, entity_type, importance FROM graph_entities
                         ORDER BY importance DESC, last_seen DESC LIMIT 15""")

        entities = [dict(r) for r in c.fetchall()]
        if not entities:
            return ""

        entity_names = [e["name"] for e in entities]
        placeholders = ",".join("?" for _ in entity_names)
        c.execute(f"""SELECT e1.name AS src, r.relation, e2.name AS tgt, r.weight
                      FROM graph_relations r
                      JOIN graph_entities e1 ON r.source_id=e1.id
                      JOIN graph_entities e2 ON r.target_id=e2.id
                      WHERE e1.name IN ({placeholders}) OR e2.name IN ({placeholders})
                      ORDER BY r.weight DESC LIMIT {max_relations}""",
                  entity_names + entity_names)

        relations = [dict(r) for r in c.fetchall()]
        if not relations:
            return ""

        context = "GRAFO DI CONOSCENZA:\n"
        for rel in relations:
            context += f"- {rel['src']} → {rel['relation']} → {rel['tgt']} (peso: {rel['weight']})\n"
        return context.strip()

    def get_stats(self):
        c = self.db.cursor()
        c.execute("SELECT COUNT(*) as c FROM graph_entities")
        entities = c.fetchone()["c"]
        c.execute("SELECT COUNT(*) as c FROM graph_relations")
        relations = c.fetchone()["c"]
        return {"entities": entities, "relations": relations}
