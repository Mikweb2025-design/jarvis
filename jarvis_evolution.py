#!/usr/bin/env python3
"""jarvis_evolution.py — Self-Evolution Engine v1.0
Ispirato a: ClawdAgent, Ramsbaby/jarvis, Hermes Agent, vierisid/jarvis
Capacità:
  - Failure Analysis: traccia errori tool, rate limit, crash
  - Pattern Recognition: cosa chiede l'utente, cosa fallisce, cosa funziona
  - Insight Layer: report comportamentali giornalieri/settimanali
  - Prompt Optimizer: impara preferenze e ottimizza i prompt
  - Skill Generator: crea nuovi tool Python al volo
  - Self-Healer: rileva e risolve problemi comuni automaticamente
"""
import json, os, time, re, sqlite3, subprocess, traceback
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "evolution.db"

class EvolutionDB:
    """Database SQLite per i dati di evoluzione."""

    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.db.cursor()
        # Errori / Fallimenti
        c.execute("""CREATE TABLE IF NOT EXISTS error_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL DEFAULT 'tool',
            source TEXT NOT NULL DEFAULT 'unknown',
            message TEXT NOT NULL,
            context TEXT DEFAULT '',
            severity INTEGER DEFAULT 1,
            timestamp TEXT DEFAULT (datetime('now')),
            resolved INTEGER DEFAULT 0,
            fix_applied TEXT DEFAULT ''
        )""")
        # Metriche di utilizzo
        c.execute("""CREATE TABLE IF NOT EXISTS usage_metrics(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            label TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        # Pattern di conversazione
        c.execute("""CREATE TABLE IF NOT EXISTS conversation_patterns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_key TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            last_seen TEXT DEFAULT (datetime('now')),
            metadata TEXT DEFAULT '{}',
            UNIQUE(pattern_type, pattern_key)
        )""")
        # Skills generate automaticamente
        c.execute("""CREATE TABLE IF NOT EXISTS auto_skills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            code TEXT NOT NULL,
            created TEXT DEFAULT (datetime('now')),
            enabled INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0
        )""")
        # Self-healing actions
        c.execute("""CREATE TABLE IF NOT EXISTS healing_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue TEXT NOT NULL,
            fix_action TEXT NOT NULL,
            status TEXT DEFAULT 'applied',
            result TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        # Prompt optimization history
        c.execute("""CREATE TABLE IF NOT EXISTS prompt_optimizations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT NOT NULL,
            old_text TEXT DEFAULT '',
            new_text TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        self.db.commit()

    def log_error(self, category, source, message, context="", severity=1):
        c = self.db.cursor()
        c.execute("""INSERT INTO error_log (category, source, message, context, severity)
                      VALUES (?, ?, ?, ?, ?)""", (category, source, message[:500], context[:500], severity))
        self.db.commit()
        return c.lastrowid

    def log_metric(self, metric, value, label=""):
        c = self.db.cursor()
        c.execute("INSERT INTO usage_metrics (metric, value, label) VALUES (?, ?, ?)",
                  (metric, float(value), str(label)[:200]))
        self.db.commit()

    def track_pattern(self, pattern_type, pattern_key, metadata=None):
        c = self.db.cursor()
        try:
            c.execute("""INSERT INTO conversation_patterns (pattern_type, pattern_key, metadata)
                          VALUES (?, ?, ?)""",
                      (pattern_type, pattern_key, json.dumps(metadata or {})))
        except sqlite3.IntegrityError:
            c.execute("""UPDATE conversation_patterns
                          SET count = count + 1, last_seen = datetime('now')
                          WHERE pattern_type=? AND pattern_key=?""",
                      (pattern_type, pattern_key))
        self.db.commit()

    def get_recent_errors(self, limit=20, resolved=None):
        c = self.db.cursor()
        where = "WHERE 1=1"
        params = []
        if resolved is not None:
            where += " AND resolved=?"
            params.append(1 if resolved else 0)
        c.execute(f"SELECT * FROM error_log {where} ORDER BY timestamp DESC LIMIT ?",
                  params + [limit])
        return [dict(r) for r in c.fetchall()]

    def get_top_errors(self, limit=10):
        c = self.db.cursor()
        c.execute("""SELECT category, source, message, COUNT(*) as cnt
                      FROM error_log GROUP BY message ORDER BY cnt DESC LIMIT ?""", (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_usage_stats(self, metric="", hours=24):
        c = self.db.cursor()
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        if metric:
            c.execute("""SELECT AVG(value) as avg, MAX(value) as max, MIN(value) as min,
                              COUNT(*) as count FROM usage_metrics
                          WHERE metric=? AND timestamp>=?""", (metric, cutoff))
        else:
            c.execute("""SELECT metric, AVG(value) as avg, MAX(value) as max,
                              MIN(value) as min, COUNT(*) as count FROM usage_metrics
                          WHERE timestamp>=? GROUP BY metric""", (cutoff,))
        return [dict(r) for r in c.fetchall()]

    def get_top_patterns(self, pattern_type="", limit=10):
        c = self.db.cursor()
        where = "WHERE 1=1"
        params = []
        if pattern_type:
            where += " AND pattern_type=?"
            params.append(pattern_type)
        c.execute(f"""SELECT * FROM conversation_patterns {where}
                      ORDER BY count DESC LIMIT ?""", params + [limit])
        return [dict(r) for r in c.fetchall()]

    def add_auto_skill(self, name, description, code):
        c = self.db.cursor()
        try:
            c.execute("""INSERT INTO auto_skills (name, description, code)
                          VALUES (?, ?, ?)""", (name, description, code))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_auto_skills(self, enabled_only=True):
        c = self.db.cursor()
        where = "WHERE enabled=1" if enabled_only else "WHERE 1=1"
        c.execute(f"SELECT * FROM auto_skills {where} ORDER BY usage_count DESC")
        return [dict(r) for r in c.fetchall()]

    def log_healing(self, issue, fix_action, status="applied", result=""):
        c = self.db.cursor()
        c.execute("""INSERT INTO healing_log (issue, fix_action, status, result)
                      VALUES (?, ?, ?, ?)""", (issue, fix_action, status, result[:500]))
        self.db.commit()

    def resolve_error(self, error_id, fix_applied=""):
        c = self.db.cursor()
        c.execute("UPDATE error_log SET resolved=1, fix_applied=? WHERE id=?",
                  (fix_applied, error_id))
        self.db.commit()

    def close(self):
        self.db.close()


class FailureAnalyzer:
    """Analizza errori e fallimenti per identificare pattern di crash."""

    def __init__(self, db):
        self.db = db

    def analyze(self):
        """Analizza gli errori recenti e ritorna raccomandazioni."""
        top = self.db.get_top_errors(limit=5)
        recent = self.db.get_recent_errors(limit=10, resolved=False)
        if not top and not recent:
            return {"status": "clean", "message": "Nessun errore recente", "recommendations": []}

        recommendations = []
        # Tool errori frequenti
        for e in top:
            if e["cnt"] >= 3:
                recommendations.append({
                    "issue": f"Tool '{e['source']}' fallito {e['cnt']} volte: {e['message'][:80]}",
                    "severity": "high" if e["cnt"] >= 5 else "medium",
                    "suggestion": f"Verifica configurazione o sostituisci tool",
                })

        # Rate limit
        rate_errors = [e for e in recent if "rate" in e["message"].lower() or "429" in e["message"]]
        if len(rate_errors) >= 3:
            recommendations.append({
                "issue": f"Rate limit colpito {len(rate_errors)} volte",
                "severity": "medium",
                "suggestion": "Aggiungi backoff o passa a provider premium",
            })

        return {
            "status": "issues_found" if recommendations else "minor",
            "total_errors": len(top),
            "unresolved": len(recent),
            "recommendations": recommendations,
        }


class PatternAnalyzer:
    """Analizza i pattern di conversazione e utilizzo."""

    def __init__(self, db):
        self.db = db

    def analyze(self, conversation_history=None):
        """Identifica cosa chiede l'utente più spesso e come si comporta."""
        patterns = self.db.get_top_patterns(limit=20)
        if not patterns:
            return {"status": "no_data", "message": "Ancora pochi dati per analisi pattern"}

        result = {"status": "ok", "topics": [], "tools": [], "behaviors": []}

        for p in patterns:
            entry = {"key": p["pattern_key"], "count": p["count"]}
            if p["pattern_type"] == "topic":
                entry["description"] = f"Argomento frequente: {p['pattern_key']}"
                result["topics"].append(entry)
            elif p["pattern_type"] == "tool":
                entry["description"] = f"Tool usato spesso: {p['pattern_key']}"
                result["tools"].append(entry)
            elif p["pattern_type"] == "request_type":
                entry["description"] = f"Tipo richiesta comune: {p['pattern_key']}"
                result["behaviors"].append(entry)

        # Preferenze orarie
        metrics = self.db.get_usage_stats(metric="response_time_ms")
        if metrics:
            avg_time = metrics[0]["avg"]
            result["avg_response_time_ms"] = round(avg_time, 0) if avg_time else None

        return result


class InsightLayer:
    """Genera report comportamentali e insight."""

    def __init__(self, db, memory_module=None):
        self.db = db
        self.memory = memory_module

    def daily_report(self):
        """Report giornaliero delle performance e attività."""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0).isoformat()

        c = self.db.db.cursor()
        # Errori oggi
        c.execute("""SELECT COUNT(*) as cnt FROM error_log
                      WHERE timestamp>=? AND resolved=0""", (today_start,))
        errors_today = c.fetchone()["cnt"]

        # Errori risolti oggi
        c.execute("""SELECT COUNT(*) as cnt FROM error_log
                      WHERE timestamp>=? AND resolved=1""", (today_start,))
        fixed_today = c.fetchone()["cnt"]

        # Metriche oggi
        c.execute("""SELECT metric, AVG(value) as avg, MAX(value) as max
                      FROM usage_metrics WHERE timestamp>=?
                      GROUP BY metric""", (today_start,))
        metrics = {r["metric"]: {"avg": round(r["avg"], 1), "max": r["max"]}
                   for r in c.fetchall()}

        # Healing oggi
        c.execute("""SELECT COUNT(*) as cnt FROM healing_log
                      WHERE timestamp>=?""", (today_start,))
        healing_today = c.fetchone()["cnt"]

        return {
            "date": now.strftime("%Y-%m-%d"),
            "errors_today": errors_today,
            "fixed_today": fixed_today,
            "healing_actions": healing_today,
            "metrics": metrics,
            "health_score": max(0, min(100, 100 - errors_today * 10 + fixed_today * 5)),
        }

    def weekly_report(self):
        """Report settimanale completo."""
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        c = self.db.db.cursor()

        c.execute("""SELECT COUNT(*) as cnt FROM error_log
                      WHERE timestamp>=? AND resolved=0""", (week_ago,))
        unresolved = c.fetchone()["cnt"]

        c.execute("""SELECT COUNT(*) as cnt FROM healing_log
                      WHERE timestamp>=? AND status='applied'""", (week_ago,))
        auto_fixes = c.fetchone()["cnt"]

        # Top error categories
        c.execute("""SELECT category, COUNT(*) as cnt FROM error_log
                      WHERE timestamp>=? GROUP BY category ORDER BY cnt DESC""", (week_ago,))
        error_categories = [dict(r) for r in c.fetchall()]

        # Top patterns
        patterns = self.db.get_top_patterns(limit=5)

        # Healing success rate
        c.execute("""SELECT status, COUNT(*) as cnt FROM healing_log
                      WHERE timestamp>=? GROUP BY status""", (week_ago,))
        healing_stats = {r["status"]: r["cnt"] for r in c.fetchall()}

        return {
            "period": "7 giorni",
            "unresolved_errors": unresolved,
            "auto_fixes": auto_fixes,
            "error_categories": error_categories,
            "top_patterns": patterns,
            "healing_stats": healing_stats,
        }


class PromptOptimizer:
    """Impara dalle conversazioni e ottimizza i prompt."""

    def __init__(self, db, memory_module=None):
        self.db = db
        self.memory = memory_module

    def learn_preference(self, key, value):
        """Impara una preferenza dell'utente da una conversazione."""
        if self.memory:
            self.memory.set_preference(f"learned_{key}", value)
        self.db.log_metric("preference_learned", 1, f"{key}={value}")

    def get_optimizations(self):
        """Ritorna suggerimenti di ottimizzazione prompt basati su pattern."""
        suggestions = []
        patterns = self.db.get_top_patterns(pattern_type="correction", limit=5)
        for p in patterns:
            meta = json.loads(p.get("metadata", "{}"))
            if meta.get("context"):
                suggestions.append({
                    "pattern": p["pattern_key"],
                    "count": p["count"],
                    "suggestion": f"L'utente corregge spesso '{p['pattern_key']}'. "
                                  f"Aggiungi regola: {meta.get('context', '')}",
                })
        return suggestions


class SkillGenerator:
    """Genera nuovi tool/skill Python basati su necessità rilevate."""

    def __init__(self, db, tools_path=None):
        self.db = db
        self.tools_path = tools_path or Path(__file__).parent / "auto_skills"

    def generate_from_request(self, name, description, implementation_hint=""):
        """Genera una nuova skill Python e la registra."""
        self.tools_path.mkdir(exist_ok=True)
        filepath = self.tools_path / f"{name}.py"

        code = f'''#!/usr/bin/env python3
"""Skill auto-generata: {description}"""
import subprocess, json
from pathlib import Path

def {name}(**kwargs):
    """
    {description}
    
    Args generati automaticamente da kwargs.
    """
    try:
        {implementation_hint or "# TODO: implementa qui la logica"}
        return f"✅ {description} eseguito"
    except Exception as e:
        return f"⚠ Errore in {name}: {{e}}"

if __name__ == "__main__":
    print({name}())
'''
        filepath.write_text(code)
        success = self.db.add_auto_skill(name, description, code)
        if success:
            self.db.log_metric("skill_generated", 1, name)
            return f"Skill '{name}' creata: {filepath}"
        return f"Skill '{name}' già esistente"

    def list_skills(self):
        return self.db.get_auto_skills()

    def get_skill_code(self, name):
        skills = self.db.get_auto_skills(enabled_only=False)
        for s in skills:
            if s["name"] == name:
                return s["code"]
        return None


class SelfHealer:
    """Rileva e risolve automaticamente problemi comuni."""

    HEALING_RULES = [
        {
            "id": "blender_mcp_restart",
            "check": lambda: subprocess.run(
                ["pgrep", "-f", "blender_mcp_autostart"],
                capture_output=True
            ).returncode != 0,
            "fix": 'bash start_blender_mcp.sh &',
            "description": "Blender MCP server non in esecuzione",
        },
        {
            "id": "disk_space",
            "check": lambda: subprocess.run(
                'df / | tail -1 | awk \'{print int($5)}\'',
                shell=True, capture_output=True, text=True
            ).stdout.strip() and int(subprocess.run(
                'df / | tail -1 | awk \'{print int($5)}\'',
                shell=True, capture_output=True, text=True
            ).stdout.strip()) > 90,
            "fix": 'echo "⚠ Attenzione: disco quasi pieno"',
            "description": "Spazio disco basso (>90%)",
        },
        {
            "id": "ollama_running",
            "check": lambda: subprocess.run(
                ["pgrep", "ollama"], capture_output=True
            ).returncode != 0,
            "fix": 'ollama serve &',
            "description": "Ollama server non attivo",
        },
    ]

    def __init__(self, db):
        self.db = db

    def check_all(self):
        """Esegue tutti i controlli e applica fix automatici."""
        results = []
        for rule in self.HEALING_RULES:
            try:
                needs_fix = rule["check"]()
                if needs_fix:
                    result = self._apply_fix(rule)
                    results.append(result)
                else:
                    results.append({
                        "id": rule["id"],
                        "status": "healthy",
                        "description": rule["description"],
                    })
            except Exception as e:
                results.append({
                    "id": rule["id"],
                    "status": "check_failed",
                    "error": str(e),
                })
        return results

    def _apply_fix(self, rule):
        try:
            subprocess.run(rule["fix"], shell=True, timeout=30, capture_output=True)
            # Verifica che il fix abbia funzionato
            time.sleep(2)
            if rule["check"]():
                status, result = "failed", "Il fix non ha risolto il problema"
            else:
                status, result = "applied", "Fix applicato con successo"
        except subprocess.TimeoutExpired:
            status, result = "timeout", "Fix timeout (30s)"
        except Exception as e:
            status, result = "error", str(e)

        self.db.log_healing(rule["description"], rule["fix"], status, result)
        return {"id": rule["id"], "status": status, "description": rule["description"], "result": result}

    def dawn_audit(self):
        """Audit completo all'avvio del giorno."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "checks": self.check_all(),
            "errors_since_midnight": len(self.db.get_recent_errors(limit=50, resolved=False)),
        }
        self.db.log_metric("dawn_audit", 1)
        return report


class EvolutionEngine:
    """Orchestratore principale del Self-Evolution System."""

    def __init__(self, memory_module=None):
        self.db = EvolutionDB()
        self.failure = FailureAnalyzer(self.db)
        self.patterns = PatternAnalyzer(self.db)
        self.insight = InsightLayer(self.db, memory_module)
        self.prompts = PromptOptimizer(self.db, memory_module)
        self.skills = SkillGenerator(self.db)
        self.healer = SelfHealer(self.db)
        self.memory = memory_module

    # ── API PUBBLICA ──

    def track_error(self, category, source, message, context=""):
        severity = 3 if "crash" in message.lower() or "traceback" in message.lower() else \
                   2 if "error" in message.lower() else 1
        error_id = self.db.log_error(category, source, message, context, severity)
        self.db.log_metric("error_count", 1, f"{category}:{source}")
        return error_id

    def track_success(self, tool_name, response_time_ms=0):
        self.db.log_metric("tool_success", 1, tool_name)
        if response_time_ms > 0:
            self.db.log_metric("response_time_ms", response_time_ms, tool_name)
        # Pattern: tool usato
        self.db.track_pattern("tool", tool_name)

    def track_conversation(self, user_message, reply=""):
        """Analizza la conversazione e registra pattern."""
        low = user_message.lower()
        # Topic detection
        topics = self._detect_topics(low)
        for t in topics:
            self.db.track_pattern("topic", t)
        # Tipo richiesta
        req_type = self._detect_request_type(low)
        if req_type:
            self.db.track_pattern("request_type", req_type)
        # Lunghezza messaggio
        self.db.log_metric("user_message_length", len(user_message))
        if reply:
            self.db.log_metric("assistant_reply_length", len(reply))

    def _detect_topics(self, text):
        topics = []
        keywords = {
            "coding": ["codice", "python", "programma", "script", "git", "debug", "bug",
                       "function", "classe", "algoritmo", "test", "api", "server"],
            "system": ["sistema", "mac", "apple", "app", "file", "cartella", "download",
                       "volume", "schermo", "screenshot"],
            "blender_3d": ["blender", "3d", "render", "modello", "avatar", "oggetto 3d",
                           "scena", "animazione", "materiale"],
            "web": ["internet", "browser", "cerca su", "google", "youtube", "sito",
                    "url", "pagina web", "notizie"],
            "smart_home": ["luce", "luci", "termostato", "home assistant", "accendi",
                           "spegni", "temperatura", "stanza"],
            "email": ["email", "mail", "posta", "messaggio", "invia", "leggi email"],
            "calendar": ["calendario", "evento", "appuntamento", "riunione", "promemoria"],
            "music": ["musica", "canzone", "playlist", "spotify", "apple music"],
            "wellbeing": ["benessere", "salute", "relax", "meditazione", "yoga",
                          "palestra", "dieta", "sonno", "stress"],
            "goals": ["obiettivo", "goal", "okr", "key result", "traguardo", "migliorare"],
        }
        for topic, kws in keywords.items():
            if any(k in text for k in kws):
                topics.append(topic)
        return topics or ["general"]

    def _detect_request_type(self, text):
        if any(w in text for w in ["crea", "fai", "genera", "costruisci", "scrivi"]):
            return "creation"
        if any(w in text for w in ["cerca", "trova", "dove", "chi", "cosa", "quando"]):
            return "search"
        if any(w in text for w in ["apri", "lancia", "avvia", "mostra"]):
            return "navigation"
        if any(w in text for w in ["spiega", "descrivi", "cos'è", "come funziona"]):
            return "explanation"
        if any(w in text for w in ["modifica", "cambia", "aggiorna", "elimina"]):
            return "modification"
        if any(w in text for w in ["ciao", "salve", "buongiorno", "buonasera"]):
            return "greeting"
        return ""

    def get_status_summary(self):
        """Report sintetico dello stato di evoluzione."""
        failure_report = self.failure.analyze()
        daily = self.insight.daily_report()
        skills = self.skills.list_skills()
        healing = self.db.get_usage_stats(metric="healing_count", hours=168)

        lines = [
            "🧬 SELF-EVOLUTION ENGINE STATUS",
            f"  🏥 Salute: {daily['health_score']}/100",
            f"  ❌ Errori oggi: {daily['errors_today']} (risolti: {daily['fixed_today']})",
            f"  🔧 Auto-healing: {daily['healing_actions']} azioni",
            f"  🧠 Skills generate: {len(skills)}",
            f"  📊 Pattern tracciati: {len(failure_report.get('recommendations', []))} issues",
        ]
        if failure_report.get("recommendations"):
            lines.append("  ⚠ Raccomandazioni:")
            for r in failure_report["recommendations"][:3]:
                lines.append(f"    • {r['issue']}")
        return "\n".join(lines)

    def run_healing_check(self):
        """Esegue check di auto-riparazione."""
        results = self.healer.check_all()
        fixed = sum(1 for r in results if r["status"] == "applied")
        self.db.log_metric("healing_count", fixed)
        return results

    def run_dawn_audit(self):
        """Esegue audit completo all'avvio."""
        report = self.healer.dawn_audit()
        return report

    def generate_daily_report(self):
        return self.insight.daily_report()

    def generate_weekly_report(self):
        return self.insight.weekly_report()

    def analyze_patterns(self):
        return self.patterns.analyze()

    def get_auto_skills(self):
        return self.skills.list_skills()

    def generate_skill(self, name, description, hint=""):
        return self.skills.generate_from_request(name, description, hint)

    def get_prompt_suggestions(self):
        return self.prompts.get_optimizations()

    def track_correction(self, user_message, context=""):
        """Traccia quando l'utente corregge JARVIS."""
        self.db.track_pattern("correction", user_message[:100],
                              {"context": context[:200]})
        self.prompts.learn_preference("correction_pattern", user_message[:100])


evol = EvolutionEngine()
