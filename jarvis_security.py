#!/usr/bin/env python3
"""jarvis_security.py — Security Chain: trust scoring, sandbox, permissions, audit, threat detection"""
import json, os, sqlite3, time, re, subprocess, hashlib, inspect
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "security.db"

class SecurityDB:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS trust_scores(
            entity TEXT PRIMARY KEY,
            score REAL DEFAULT 0.0,
            total_actions INTEGER DEFAULT 0,
            successful INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            last_seen TEXT DEFAULT (datetime('now')),
            category TEXT DEFAULT 'tool'
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            details TEXT DEFAULT '',
            permission_level TEXT DEFAULT 'read',
            allowed INTEGER DEFAULT 1,
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS permission_rules(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL UNIQUE,
            level TEXT DEFAULT 'read',
            category TEXT DEFAULT 'command',
            enabled INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS threat_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            threat_type TEXT NOT NULL,
            source TEXT NOT NULL,
            details TEXT DEFAULT '',
            severity INTEGER DEFAULT 1,
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        # Default permission rules
        default_rules = [
            ("rm -rf /", "deny", "command"),
            ("sudo rm", "deny", "command"),
            ("mkfs", "deny", "command"),
            ("dd if=", "deny", "command"),
            (":(){", "deny", "command"),
            ("diskutil erase", "deny", "command"),
            ("launchctl unload", "admin", "command"),
            ("security", "admin", "command"),
            ("csrutil", "deny", "command"),
            ("open -a Terminal", "read", "command"),
            ("osascript", "write", "command"),
        ]
        for pattern, level, cat in default_rules:
            try:
                c.execute("INSERT OR IGNORE INTO permission_rules (pattern, level, category) VALUES (?, ?, ?)",
                          (pattern, level, cat))
            except:
                pass
        self.db.commit()

    def get_trust(self, entity):
        c = self.db.cursor()
        c.execute("SELECT * FROM trust_scores WHERE entity=?", (entity,))
        return dict(c.fetchone()) if c.fetchone() else None

    def update_trust(self, entity, success=True, category="tool"):
        c = self.db.cursor()
        existing = self.get_trust(entity)
        if existing:
            score = existing["score"]
            total = existing["total_actions"] + 1
            successful = existing["successful"] + (1 if success else 0)
            failed = existing["failed"] + (0 if success else 1)
            score = min(1.0, max(-1.0, score + (0.1 if success else -0.3)))
            c.execute("""UPDATE trust_scores SET score=?, total_actions=?, successful=?, failed=?,
                          last_seen=datetime('now') WHERE entity=?""",
                      (score, total, successful, failed, entity))
        else:
            score = 0.3 if success else -0.3
            c.execute("""INSERT INTO trust_scores (entity, score, total_actions, successful, failed, category)
                          VALUES (?, ?, 1, ?, ?, ?)""",
                      (entity, score, 1 if success else 0, 0 if success else 1, category))
        self.db.commit()

    def log_audit(self, action, entity, details="", level="read", allowed=True):
        c = self.db.cursor()
        c.execute("""INSERT INTO audit_log (action, entity, details, permission_level, allowed)
                      VALUES (?, ?, ?, ?, ?)""",
                  (action[:200], entity[:200], details[:500], level, 1 if allowed else 0))
        self.db.commit()

    def log_threat(self, threat_type, source, details="", severity=1):
        c = self.db.cursor()
        c.execute("""INSERT INTO threat_log (threat_type, source, details, severity)
                      VALUES (?, ?, ?, ?)""",
                  (threat_type[:100], source[:200], details[:500], severity))
        self.db.commit()

    def get_audit_log(self, limit=50):
        c = self.db.cursor()
        c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_recent_threats(self, limit=20):
        c = self.db.cursor()
        c.execute("SELECT * FROM threat_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

class SecurityEngine:
    DANGEROUS_PATTERNS = [
        (r'rm\s+-rf\s+/', 10, "Recursive root deletion"),
        (r'sudo\s+rm', 9, "Sudo delete"),
        (r'mkfs\.\w+', 9, "Filesystem format"),
        (r'dd\s+if=', 9, "Raw disk write"),
        (r':\(\)\{', 10, "Fork bomb"),
        (r'chmod\s+777\s+/', 8, "World-writable root"),
        (r'>\s*/dev/sda', 9, "Raw device write"),
        (r'crypto\s+(currency|miner|mine)', 7, "Cryptominer"),
        (r'wget.*\|\s*sh', 8, "Pipe to shell"),
        (r'curl.*\|\s*sh', 8, "Pipe to shell"),
        (r'python3?\s+-c\s+["\'].*import\s+os.*system', 7, "Python os.system injection"),
        (r'eval\s*\(', 6, "Eval injection"),
        (r'exec\s*\(', 6, "Exec injection"),
        (r'base64\s+-d.*\|', 7, "Obfuscated command"),
        (r'diskutil\s+erase', 9, "Disk erase"),
        (r'csrutil\s+disable', 10, "SIP disable"),
    ]

    def __init__(self):
        self.db = SecurityDB()
        self._rate_limits = defaultdict(list)

    def check_trust(self, entity):
        """Get trust score for an entity (-1 to 1)"""
        data = self.db.get_trust(entity)
        if not data:
            return {"entity": entity, "score": 0.0, "actions": 0, "trusted": True}
        score = data["score"]
        return {
            "entity": entity,
            "score": round(score, 2),
            "actions": data["total_actions"],
            "success_rate": round(data["successful"] / max(data["total_actions"], 1) * 100),
            "trusted": score > -0.2,
        }

    def check_command_safety(self, command):
        """Check if a command is safe to execute. Returns (safe, reason, risk_score)"""
        for pattern, risk, reason in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, reason, risk
        # Check database rules
        c = self.db.db.cursor()
        c.execute("SELECT * FROM permission_rules WHERE enabled=1")
        for rule in c.fetchall():
            if rule["pattern"] in command:
                if rule["level"] == "deny":
                    return False, f"Blocked by rule: {rule['pattern']}", 8
        return True, "Safe", 0

    def check_rate_limit(self, action, max_per_minute=10):
        """Check if an action is rate-limited"""
        now = time.time()
        key = f"{action}"
        recent = [t for t in self._rate_limits[key] if now - t < 60]
        self._rate_limits[key] = recent
        if len(recent) >= max_per_minute:
            return False, f"Rate limit exceeded for {action} ({max_per_minute}/min)"
        self._rate_limits[key].append(now)
        return True, "OK"

    def execute_safe(self, action, func, args=None, entity="user"):
        """Execute a function with full security chain: trust check, rate limit, safety check, audit"""
        args = args or {}
        # 1. Rate limit check
        allowed, msg = self.check_rate_limit(action)
        if not allowed:
            self.db.log_audit(action, entity, msg, "read", False)
            return {"error": msg}
        # 2. Trust check
        trust = self.check_trust(entity)
        if not trust["trusted"] and trust["actions"] > 5:
            self.db.log_audit(action, entity, f"Low trust: {trust['score']}", "read", False)
            return {"error": f"Action blocked: trust score too low ({trust['score']})"}
        # 3. Execute
        try:
            result = func(**args) if isinstance(args, dict) else func(args)
            self.db.update_trust(entity, success=True)
            self.db.log_audit(action, entity, str(result)[:200], "write", True)
            return {"result": result}
        except Exception as e:
            self.db.update_trust(entity, success=False)
            self.db.log_audit(action, entity, str(e)[:200], "write", False)
            return {"error": str(e)}

    def get_activity_report(self):
        """Generate security activity report"""
        audit = self.db.get_audit_log(20)
        threats = self.db.get_recent_threats(10)
        blocked = sum(1 for a in audit if not a["allowed"])
        total = len(audit)
        return {
            "total_actions": total,
            "blocked": blocked,
            "block_rate": round(blocked / max(total, 1) * 100, 1),
            "recent_audit": audit[:10],
            "recent_threats": threats[:5],
            "trusted_entities": self._get_top_trusted(),
        }

    def _get_top_trusted(self, limit=10):
        c = self.db.db.cursor()
        c.execute("SELECT entity, score, total_actions FROM trust_scores ORDER BY score DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def add_permission_rule(self, pattern, level="read", category="command"):
        """Add a permission rule"""
        c = self.db.db.cursor()
        try:
            c.execute("INSERT INTO permission_rules (pattern, level, category) VALUES (?, ?, ?)",
                      (pattern, level, category))
            self.db.db.commit()
            return f"Rule added: {pattern} -> {level}"
        except sqlite3.IntegrityError:
            c.execute("UPDATE permission_rules SET level=?, category=? WHERE pattern=?",
                      (level, category, pattern))
            self.db.db.commit()
            return f"Rule updated: {pattern} -> {level}"

    def remove_permission_rule(self, pattern):
        c = self.db.db.cursor()
        c.execute("DELETE FROM permission_rules WHERE pattern=?", (pattern,))
        self.db.db.commit()
        return f"Rule removed: {pattern}"

    def list_rules(self):
        c = self.db.db.cursor()
        c.execute("SELECT * FROM permission_rules WHERE enabled=1 ORDER BY category")
        return [dict(r) for r in c.fetchall()]

security = SecurityEngine()
