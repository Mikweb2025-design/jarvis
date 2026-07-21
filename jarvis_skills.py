#!/usr/bin/env python3
"""jarvis_skills.py — Self-Learning Skills System v1.0
Inspirato da Hermes Agent e OpenClaw.
Capacità:
  - LLM genera codice Python da descrizione
  - Test in sandbox temporanea
  - Auto-migliora da feedback di esecuzione
  - Rileva task ripetitivi e suggerisce skill
  - Import runtime delle skill nel tool system
"""
import json, os, sys, re, time, traceback, subprocess, tempfile, importlib, textwrap
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent / "data"
SKILLS_DIR = Path(__file__).parent / "auto_skills"
DB_PATH = DATA_DIR / "skills.db"

SKILLS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
CONFIG_PATH = Path(__file__).parent / "config.json"

def _load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}

def _call_llm(system_prompt, user_prompt, temperature=0.3, max_tokens=1500):
    cfg = _load_config()
    api_key = cfg.get("groq", {}).get("api_key", "")
    model = cfg.get("groq", {}).get("model", "llama-3.3-70b-versatile")
    if not api_key:
        return None, "NO_API_KEY: Groq API key non configurata"
    try:
        import requests
        resp = requests.post(GROQ_URL, json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }, timeout=60)
        if not resp.ok:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        content = resp.json()["choices"][0]["message"]["content"].strip()
        return content, None
    except Exception as e:
        return None, str(e)


class SkillsDB:
    def __init__(self):
        import sqlite3
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS skills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            code TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            version INTEGER DEFAULT 1,
            created TEXT DEFAULT (datetime('now')),
            updated TEXT DEFAULT (datetime('now')),
            enabled INTEGER DEFAULT 1,
            auto_generated INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            avg_duration_ms REAL DEFAULT 0,
            last_used TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            input_schema TEXT DEFAULT '{}'
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS skill_feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL,
            execution_id TEXT NOT NULL,
            success INTEGER DEFAULT 1,
            duration_ms REAL DEFAULT 0,
            input_summary TEXT DEFAULT '',
            output_summary TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS skill_suggestions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            source TEXT DEFAULT 'auto_detect',
            frequency INTEGER DEFAULT 1,
            created TEXT DEFAULT (datetime('now')),
            implemented INTEGER DEFAULT 0,
            dismissed INTEGER DEFAULT 0
        )""")
        self.db.commit()

    def add_skill(self, name, description, code, category="general", tags=None, input_schema=None):
        c = self.db.cursor()
        try:
            c.execute("""INSERT INTO skills (name, description, code, category, tags, input_schema)
                          VALUES (?, ?, ?, ?, ?, ?)""",
                      (name, description, code, category,
                       json.dumps(tags or []), json.dumps(input_schema or {})))
            self.db.commit()
            return True
        except:
            c.execute("""UPDATE skills SET code=?, description=?, version=version+1,
                          updated=datetime('now'), enabled=1
                          WHERE name=?""", (code, description, name))
            self.db.commit()
            return False

    def get_skill(self, name):
        c = self.db.cursor()
        c.execute("SELECT * FROM skills WHERE name=?", (name,))
        row = c.fetchone()
        return dict(row) if row else None

    def list_skills(self, enabled_only=True, category=""):
        c = self.db.cursor()
        where = "WHERE enabled=1" if enabled_only else "WHERE 1=1"
        params = []
        if category:
            where += " AND category=?"
            params.append(category)
        c.execute(f"SELECT * FROM skills {where} ORDER BY usage_count DESC", params)
        return [dict(r) for r in c.fetchall()]

    def log_execution(self, skill_name, execution_id, success, duration_ms, input_summary="", output_summary="", error_message=""):
        c = self.db.cursor()
        c.execute("""INSERT INTO skill_feedback
                      (skill_name, execution_id, success, duration_ms, input_summary, output_summary, error_message)
                      VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (skill_name, execution_id, success, duration_ms,
                   str(input_summary)[:200], str(output_summary)[:200], str(error_message)[:500]))
        if success:
            c.execute("""UPDATE skills SET usage_count=usage_count+1, success_count=success_count+1,
                          avg_duration_ms=(avg_duration_ms * usage_count + ?) / (usage_count + 1),
                          last_used=datetime('now')
                          WHERE name=?""", (duration_ms, skill_name))
        else:
            c.execute("""UPDATE skills SET usage_count=usage_count+1, failure_count=failure_count+1,
                          last_used=datetime('now')
                          WHERE name=?""", (skill_name,))
        self.db.commit()

    def add_suggestion(self, description, source="auto_detect"):
        c = self.db.cursor()
        try:
            c.execute("INSERT INTO skill_suggestions (description, source) VALUES (?, ?)", (description, source))
        except:
            c.execute("UPDATE skill_suggestions SET frequency=frequency+1 WHERE description=? AND source=? AND implemented=0", (description, source))
        self.db.commit()

    def get_suggestions(self, include_implemented=False):
        c = self.db.cursor()
        where = "WHERE 1=1" if include_implemented else "WHERE implemented=0 AND dismissed=0"
        c.execute(f"SELECT * FROM skill_suggestions {where} ORDER BY frequency DESC")
        return [dict(r) for r in c.fetchall()]

    def get_stats(self):
        c = self.db.cursor()
        c.execute("SELECT COUNT(*) as total, SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) as active FROM skills")
        total = c.fetchone()
        c.execute("SELECT COALESCE(SUM(usage_count), 0) as total_uses FROM skills")
        uses = c.fetchone()
        c.execute("SELECT COALESCE(SUM(success_count), 0) as total_success, COALESCE(SUM(failure_count), 0) as total_fail FROM skills")
        sf = c.fetchone()
        return {
            "total": total["total"] if total else 0,
            "active": total["active"] if total else 0,
            "total_uses": uses["total_uses"] if uses else 0,
            "total_success": sf["total_success"] if sf else 0,
            "total_failures": sf["total_fail"] if sf else 0,
        }


class SkillGenerator:
    """Usa LLM per generare codice skill Python da linguaggio naturale."""

    GENERATOR_SYSTEM_PROMPT = """Sei un engineer Python che genera skill per un assistente AI personale.
Genera UNA FUNZIONE Python che:
1. Ha un nome descriptivo in snake_case
2. Accetta **kwargs e li usa come parametri
3. Restituisce SEMPRE una stringa (il risultato o messaggio di errore)
4. Usa solo librerie standard Python (os, sys, json, subprocess, pathlib, datetime, re, math, random, typing, itertools, collections, hashlib, base64, tempfile, shutil, textwrap, urllib)
5. Se servono librerie esterne, includi un try/except con messaggio chiaro
6. È completamente autosufficiente (tutta la logica nella funzione)
7. Gestisce errori con try/except robusto
8. Ha un if __name__ == "__main__" con test rapido

Output: SOLO codice Python, niente spiegazioni, niente markdown, niente ```."""

    def __init__(self, db):
        self.db = db

    def generate_from_description(self, name, description, category="general"):
        """Usa LLM per generare una skill completa da descrizione."""
        prompt = f"""Nome skill: {name}
Descrizione: {description}
Categoria: {category}

Genera una funzione Python chiamata '{name}' che realizza esattamente questa descrizione.
La funzione deve essere concreta e funzionante. Non usare placeholders o TODO."""
        code, error = _call_llm(self.GENERATOR_SYSTEM_PROMPT, prompt, temperature=0.3)
        if error:
            return None, error
        code = self._clean_code(code)
        if not code:
            return None, "LLM non ha prodotto codice valido"
        return code, None

    def generate_from_request(self, name, description, hint="", category="general", input_schema=None):
        """Genera, testa e registra una skill."""
        code, error = self.generate_from_description(name, description, category)
        if error:
            return None, error
        valid, test_result = self._test_code(name, code)
        if not valid:
            code, error = self._self_heal(name, description, code, test_result)
            if error:
                return None, error
            valid, test_result = self._test_code(name, code)
            if not valid:
                return None, f"Skill non supera i test dopo healing: {test_result}"
        filepath = SKILLS_DIR / f"{name}.py"
        filepath.write_text(code)
        is_new = self.db.add_skill(name, description, code, category, input_schema=input_schema)
        return {"name": name, "path": str(filepath), "new": is_new, "test": test_result}, None

    def _clean_code(self, code):
        code = re.sub(r'^```[a-zA-Z]*\n?', '', code.strip())
        code = re.sub(r'\n?```$', '', code).strip()
        if not code.startswith("def ") and not code.startswith("import ") and not code.startswith("from "):
            code = "import os, sys, json, subprocess, re, math, random, datetime\nfrom pathlib import Path\n\n" + code
        return code

    def _test_code(self, name, code):
        """Testa la skill in ambiente isolato."""
        try:
            compile(code, f"<{name}>", "exec")
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"
        test_code = code + f"\n\nif __name__ == '__main__':\n    print({name}())"
        try:
            result = subprocess.run(
                [sys.executable, "-c", test_code],
                capture_output=True, text=True, timeout=15,
                cwd=str(SKILLS_DIR),
                env={**os.environ, "PYTHONPATH": str(Path(__file__).parent)}
            )
            if result.returncode != 0:
                return False, result.stderr[:500] or result.stdout[:500]
            return True, result.stdout.strip()[:200]
        except subprocess.TimeoutExpired:
            return False, "Timeout (15s)"

    def _self_heal(self, name, description, broken_code, error_message):
        """Chiede all'LLM di correggere la skill rotta."""
        prompt = f"""La skill '{name}' ({description}) ha questo errore:

{error_message}

CODICE ATTUALE (rotto):
```python
{broken_code}
```

Correggi il codice. Output: SOLO codice Python funzionante."""
        code, error = _call_llm(self.GENERATOR_SYSTEM_PROMPT, prompt, temperature=0.5)
        if error:
            return None, error
        code = self._clean_code(code)
        return code, None

    def improve_from_feedback(self, name, feedback):
        """Migliora una skill basandosi sui feedback di esecuzione."""
        skill = self.db.get_skill(name)
        if not skill:
            return None, "Skill non trovata"
        prompt = f"""Migliora questa skill Python:

NOME: {name}
DESCRIZIONE: {skill['description']}
FEEDBACK: {feedback}

CODICE ATTUALE:
```python
{skill['code']}
```

Output: SOLO codice Python migliorato."""
        code, error = _call_llm(self.GENERATOR_SYSTEM_PROMPT, prompt, temperature=0.4)
        if error:
            return None, error
        code = self._clean_code(code)
        valid, test_result = self._test_code(name, code)
        if not valid:
            return None, f"Miglioramento non supera test: {test_result}"
        filepath = SKILLS_DIR / f"{name}.py"
        filepath.write_text(code)
        self.db.add_skill(name, skill["description"], code, skill.get("category", "general"))
        return {"name": name, "path": str(filepath), "test": test_result}, None


class PatternDetector:
    """Rileva task ripetitivi e suggerisce skill automatiche."""

    def __init__(self, db):
        self.db = db
        self.known_patterns = {
            "search_and_summarize": ["cerca", "trova", "search", "find", "summarize", "riassumi"],
            "file_organizer": ["organizza", "ordina", "pulisci", "clean", "organize"],
            "email_smart_reply": ["rispondi", "reply", "email", "mail", "posta"],
            "report_generator": ["report", "genera report", "genera documento", "generate report"],
            "translator": ["traduci", "translate", "lingua", "language"],
            "data_extractor": ["estrai", "extract", "parse", "parse"],
        }

    def analyze_conversation_history(self, history=None):
        """Analizza cronologia conversazioni per pattern ripetitivi."""
        if not history:
            return []
        suggestions = []
        user_requests = []
        pattern_counts = {}
        for msg in history:
            if isinstance(msg, dict) and msg.get("role") == "user":
                text = msg.get("content", "").lower()
                user_requests.append(text)
                for pattern_name, keywords in self.known_patterns.items():
                    if any(kw in text for kw in keywords):
                        pattern_counts[pattern_name] = pattern_counts.get(pattern_name, 0) + 1
        for pattern, count in pattern_counts.items():
            if count >= 3:
                suggestions.append({"pattern": pattern, "count": count, "source": "auto_detect"})
        return suggestions

    def record_request(self, user_message):
        """Registra una richiesta utente e controlla se merita una skill."""
        low = user_message.lower()
        for pattern_name, keywords in self.known_patterns.items():
            if any(kw in low for kw in keywords):
                clean = re.sub(r'(per favore|grazie|ciao|salve|ok|si|sì)', '', low).strip()
                desc = f"Skill per: {clean[:100]}"
                self.db.add_suggestion(desc, f"pattern:{pattern_name}")
                return True
        return False


class SkillRuntime:
    """Carica ed esegue skill in runtime."""

    def __init__(self, db):
        self.db = db
        self._loaded = {}
        self._load_all()

    def _load_all(self):
        skills = self.db.list_skills(enabled_only=True)
        for s in skills:
            self._load_one(s["name"], s["code"])

    def _load_one(self, name, code):
        try:
            module_name = f"_skill_{name}"
            spec = importlib.util.spec_from_loader(module_name, None)
            mod = importlib.util.module_from_spec(spec) if spec else type(sys)(module_name)
            if spec:
                exec(compile(code, f"<skill:{name}>", "exec"), mod.__dict__)
            else:
                mod = type(sys)(module_name)
                exec(compile(code, f"<skill:{name}>", "exec"), mod.__dict__)
            self._loaded[name] = mod
            return True
        except Exception as e:
            print(f"  [Skills] Load fail {name}: {e}")
            return False

    def reload(self, name=None):
        if name:
            if name in self._loaded:
                del self._loaded[name]
            skill = self.db.get_skill(name)
            if skill:
                filepath = SKILLS_DIR / f"{name}.py"
                if filepath.exists():
                    code = filepath.read_text()
                    self._load_one(name, code)
        else:
            self._loaded = {}
            self._load_all()

    def call(self, skill_name, **kwargs):
        """Chiama una skill per nome con argomenti."""
        if skill_name not in self._loaded:
            skill = self.db.get_skill(skill_name)
            if not skill:
                return f"⚠ Skill '{skill_name}' non trovata"
            ok = self._load_one(skill_name, skill["code"])
            if not ok:
                return f"⚠ Skill '{skill_name}' non caricabile"
        mod = self._loaded[skill_name]
        func = getattr(mod, skill_name, None)
        if not func:
            funcs = [a for a in dir(mod) if not a.startswith("_") and callable(getattr(mod, a))]
            if funcs:
                func = getattr(mod, funcs[0])
            else:
                return f"⚠ Funzione '{skill_name}' non trovata nella skill"
        safe_kwargs = {k: v for k, v in kwargs.items() if k != "skill_name"}
        import uuid
        exec_id = str(uuid.uuid4())[:8]
        start = time.time()
        try:
            result = func(**safe_kwargs)
            elapsed = (time.time() - start) * 1000
            self.db.log_execution(skill_name, exec_id, success=True, duration_ms=elapsed,
                                  input_summary=str(safe_kwargs)[:200], output_summary=str(result)[:200])
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            tb = traceback.format_exc()
            self.db.log_execution(skill_name, exec_id, success=False, duration_ms=elapsed,
                                  error_message=str(e)[:500])
            return f"⚠ Skill '{skill_name}' errore: {e}"

    def list_loaded(self):
        return list(self._loaded.keys())

    def get_function_schema(self, name):
        """Genera uno schema tipo OpenAI function calling per una skill."""
        skill = self.db.get_skill(name)
        if not skill:
            return None
        try:
            schema = json.loads(skill.get("input_schema", "{}"))
        except:
            schema = {}
        return {
            "type": "function",
            "function": {
                "name": f"skill_{name}",
                "description": skill.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                }
            }
        }


class SkillsEngine:
    """Orchestratore principale del Self-Learning Skills System."""

    def __init__(self):
        self.db = SkillsDB()
        self.generator = SkillGenerator(self.db)
        self.detector = PatternDetector(self.db)
        self.runtime = SkillRuntime(self.db)

    def create_skill(self, skill_name, description, category="general"):
        """Crea una nuova skill da descrizione (LLM genera, testa, installa)."""
        result, error = self.generator.generate_from_request(skill_name, description, category=category)
        if error:
            return f"⚠ {error}"
        self.runtime.reload(skill_name)
        return f"✅ Skill '{skill_name}' creata e testata\n  {result['path']}\n  Test: {result['test'][:100]}"

    def improve_skill(self, skill_name, feedback):
        """Migliora una skill esistente con feedback."""
        result, error = self.generator.improve_from_feedback(skill_name, feedback)
        if error:
            return f"⚠ {error}"
        self.runtime.reload(skill_name)
        return f"✅ Skill '{skill_name}' migliorata\n  {result['test'][:100]}"

    def run_skill(self, skill_name, **kwargs):
        """Esegue una skill per nome."""
        return self.runtime.call(skill_name, **kwargs)

    def list_skills(self, category=""):
        skills = self.db.list_skills(category=category)
        if not skills:
            return "Nessuna skill installata"
        lines = ["🧠 Self-Learning Skills:"]
        for s in skills:
            usage = f"usata {s['usage_count']}x" if s['usage_count'] else "mai usata"
            success_rate = f"{(s['success_count']/(s['usage_count'] or 1))*100:.0f}%" if s['usage_count'] else "—"
            lines.append(f"  • {s['name']} v{s['version']} [{s['category']}]")
            lines.append(f"    {s['description'][:80]}")
            lines.append(f"    {usage} | success: {success_rate} | v{s['version']}")
        return "\n".join(lines)

    def get_skill_info(self, name):
        s = self.db.get_skill(name)
        if not s:
            return f"⚠ Skill '{name}' non trovata"
        loaded = "🟢" if name in self.runtime.list_loaded() else "⚪"
        success_rate = f"{(s['success_count']/(s['usage_count'] or 1))*100:.0f}%" if s['usage_count'] else "—"
        return (f"{loaded} {s['name']} v{s['version']}\n"
                f"  {s['description']}\n"
                f"  Categoria: {s['category']} | Usata: {s['usage_count']}x\n"
                f"  Success: {success_rate} | Avg: {s['avg_duration_ms']:.0f}ms\n"
                f"  Auto-generata: {'si' if s['auto_generated'] else 'no'}\n"
                f"  Creata: {s['created']} | Ultimo uso: {s['last_used'] or 'mai'}")

    def get_code(self, name):
        s = self.db.get_skill(name)
        return s["code"] if s else None

    def delete_skill(self, name):
        s = self.db.get_skill(name)
        if not s:
            return f"⚠ Skill '{name}' non trovata"
        filepath = SKILLS_DIR / f"{name}.py"
        if filepath.exists():
            filepath.unlink()
        c = self.db.db.cursor()
        c.execute("DELETE FROM skills WHERE name=?", (name,))
        self.db.db.commit()
        self.runtime.reload(name)
        return f"🗑 Skill '{name}' eliminata"

    def get_suggestions(self):
        suggestions = self.db.get_suggestions()
        if not suggestions:
            return "Nessun suggerimento skill al momento"
        lines = ["💡 Skill suggerite:"]
        for s in suggestions:
            lines.append(f"  • [{s['frequency']}x] {s['description'][:80]}")
            lines.append(f"    Fonte: {s['source']} | /skills_create \"{s['description'][:50]}\"")
        return "\n".join(lines)

    def record_request(self, msg):
        return self.detector.record_request(msg)

    def get_all_function_schemas(self):
        schemas = []
        for name in self.runtime.list_loaded():
            schema = self.runtime.get_function_schema(name)
            if schema:
                schemas.append(schema)
        return schemas

    def get_stats(self):
        return self.db.get_stats()

    def toggle_skill(self, name, enabled=None):
        s = self.db.get_skill(name)
        if not s:
            return f"⚠ Skill '{name}' non trovata"
        new_enabled = enabled if enabled is not None else not s["enabled"]
        c = self.db.db.cursor()
        c.execute("UPDATE skills SET enabled=? WHERE name=?", (1 if new_enabled else 0, name))
        self.db.db.commit()
        self.runtime.reload(name)
        return f"{'✅' if new_enabled else '⏹'} Skill '{name}' {'attivata' if new_enabled else 'disattivata'}"

    def register_as_tools(self, tool_schema_list, handler_dict):
        """Registra tutte le skill attive come tool chiamabili."""
        for name in self.runtime.list_loaded():
            schema = self.runtime.get_function_schema(name)
            if schema:
                tool_name = f"skill_{name}"
                if not any(t.get("function", {}).get("name") == tool_name for t in tool_schema_list):
                    tool_schema_list.append(schema)
                    handler_dict[tool_name] = lambda n=name, **kw: self.run_skill(n, **kw)


skills = SkillsEngine()
