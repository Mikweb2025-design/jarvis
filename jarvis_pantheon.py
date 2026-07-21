#!/usr/bin/env python3
"""jarvis_pantheon.py — Multi-Agent Orchestration & Agent Economy: sub-agent registry, task delegation, economy, communication bus"""
import json, os, sqlite3, time, uuid, threading, requests
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "pantheon.db"

class PantheonDB:
    def __init__(self):
        DATA_DIR.mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        c = self.db.cursor()
        # Agent registry
        c.execute("""CREATE TABLE IF NOT EXISTS agents(
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            capabilities TEXT DEFAULT '[]',
            endpoint TEXT DEFAULT '',
            status TEXT DEFAULT 'idle',
            credits REAL DEFAULT 100.0,
            total_tasks INTEGER DEFAULT 0,
            completed_tasks INTEGER DEFAULT 0,
            created TEXT DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now'))
        )""")
        # Task queue
        c.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            result TEXT DEFAULT '',
            error TEXT DEFAULT '',
            created TEXT DEFAULT (datetime('now')),
            started TEXT,
            completed TEXT,
            credits_cost REAL DEFAULT 1.0,
            FOREIGN KEY(agent_id) REFERENCES agents(id)
        )""")
        # Communication bus
        c.execute("""CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            subject TEXT DEFAULT '',
            body TEXT DEFAULT '',
            read INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        # Economy ledger
        c.execute("""CREATE TABLE IF NOT EXISTS economy(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            amount REAL NOT NULL,
            reason TEXT DEFAULT '',
            timestamp TEXT DEFAULT (datetime('now'))
        )""")
        self.db.commit()

    def register_agent(self, name, capabilities, endpoint=""):
        c = self.db.cursor()
        aid = str(uuid.uuid4())[:8]
        try:
            c.execute("""INSERT INTO agents (id, name, capabilities, endpoint)
                          VALUES (?, ?, ?, ?)""",
                      (aid, name, json.dumps(capabilities), endpoint))
            self.db.commit()
            return {"id": aid, "name": name}
        except sqlite3.IntegrityError:
            c.execute("UPDATE agents SET last_seen=datetime('now'), capabilities=?, endpoint=? WHERE name=?",
                      (json.dumps(capabilities), endpoint, name))
            self.db.commit()
            c.execute("SELECT id FROM agents WHERE name=?", (name,))
            row = c.fetchone()
            return {"id": row["id"], "name": name, "updated": True}

    def list_agents(self):
        c = self.db.cursor()
        c.execute("SELECT * FROM agents ORDER BY completed_tasks DESC")
        return [dict(r) for r in c.fetchall()]

    def find_agents_by_capability(self, capability):
        c = self.db.cursor()
        c.execute("SELECT * FROM agents WHERE capabilities LIKE ?", (f'%{capability}%',))
        return [dict(r) for r in c.fetchall()]

    def create_task(self, description, agent_id=None, priority=0, credits_cost=1.0):
        c = self.db.cursor()
        tid = str(uuid.uuid4())[:12]
        c.execute("""INSERT INTO tasks (id, agent_id, description, priority, credits_cost)
                      VALUES (?, ?, ?, ?, ?)""",
                  (tid, agent_id, description, priority, credits_cost))
        self.db.commit()
        return tid

    def get_pending_tasks(self, agent_id=None, limit=10):
        c = self.db.cursor()
        if agent_id:
            c.execute("SELECT * FROM tasks WHERE status='pending' AND agent_id=? ORDER BY priority DESC, created ASC LIMIT ?",
                      (agent_id, limit))
        else:
            c.execute("SELECT * FROM tasks WHERE status='pending' ORDER BY priority DESC, created ASC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def complete_task(self, task_id, result="", error=""):
        c = self.db.cursor()
        status = "completed" if not error else "failed"
        c.execute("""UPDATE tasks SET status=?, result=?, error=?, completed=datetime('now')
                      WHERE id=?""", (status, result[:1000], error[:500], task_id))
        if not error:
            c.execute("UPDATE agents SET completed_tasks=completed_tasks+1 WHERE id=(SELECT agent_id FROM tasks WHERE id=?)", (task_id,))
        self.db.commit()

    def send_message(self, from_agent, to_agent, subject, body=""):
        c = self.db.cursor()
        c.execute("""INSERT INTO messages (from_agent, to_agent, subject, body)
                      VALUES (?, ?, ?, ?)""",
                  (from_agent, to_agent, subject, body[:1000]))
        self.db.commit()

    def get_messages(self, agent_name, unread_only=False, limit=20):
        c = self.db.cursor()
        if unread_only:
            c.execute("SELECT * FROM messages WHERE to_agent=? AND read=0 ORDER BY timestamp DESC LIMIT ?",
                      (agent_name, limit))
        else:
            c.execute("SELECT * FROM messages WHERE to_agent=? ORDER BY timestamp DESC LIMIT ?",
                      (agent_name, limit))
        return [dict(r) for r in c.fetchall()]

    def mark_read(self, msg_id):
        c = self.db.cursor()
        c.execute("UPDATE messages SET read=1 WHERE id=?", (msg_id,))
        self.db.commit()

    def transfer_credits(self, from_agent, to_agent, amount, reason=""):
        c = self.db.cursor()
        c.execute("SELECT credits FROM agents WHERE name=?", (from_agent,))
        from_row = c.fetchone()
        if not from_row or from_row["credits"] < amount:
            return False, "Insufficient credits"
        c.execute("UPDATE agents SET credits=credits-? WHERE name=?", (amount, from_agent))
        c.execute("UPDATE agents SET credits=credits+? WHERE name=?", (amount, to_agent))
        c.execute("""INSERT INTO economy (from_agent, to_agent, amount, reason)
                      VALUES (?, ?, ?, ?)""", (from_agent, to_agent, amount, reason[:200]))
        self.db.commit()
        return True, "Transfer completed"

    def get_economy(self, limit=20):
        c = self.db.cursor()
        c.execute("SELECT * FROM economy ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

class Pantheon:
    """Multi-Agent Orchestration: delegate tasks, communicate, economy"""

    def __init__(self):
        self.db = PantheonDB()
        self._workers = {}

    # ── Agent Registration ──

    def register_agent(self, name, capabilities=None, endpoint=""):
        caps = capabilities or ["general"]
        return self.db.register_agent(name, caps, endpoint)

    def unregister_agent(self, name):
        c = self.db.db.cursor()
        c.execute("DELETE FROM agents WHERE name=?", (name,))
        self.db.db.commit()
        return f"Agent '{name}' removed"

    def list_agents(self):
        agents = self.db.list_agents()
        if not agents:
            return "No agents registered"
        lines = ["Pantheon Agents:"]
        for a in agents:
            status_icon = "🟢" if a["status"] == "idle" else "🔴" if a["status"] == "busy" else "⚪"
            lines.append(f"  {status_icon} {a['name']} — {a['status']}, tasks: {a['completed_tasks']}, credits: {a['credits']}")
        return "\n".join(lines)

    def agent_info(self, name):
        agents = self.db.list_agents()
        for a in agents:
            if a["name"] == name:
                caps = json.loads(a["capabilities"])
                return (f"Agent: {a['name']}\n"
                        f"  ID: {a['id']}\n"
                        f"  Status: {a['status']}\n"
                        f"  Capabilities: {', '.join(caps)}\n"
                        f"  Tasks completed: {a['completed_tasks']}/{a['total_tasks']}\n"
                        f"  Credits: {a['credits']}\n"
                        f"  Created: {a['created']}\n"
                        f"  Last seen: {a['last_seen']}")
        return f"Agent '{name}' not found"

    # ── Task Delegation ──

    def delegate(self, description, agent_name=None, priority=0):
        """Delegate a task to an agent (or auto-select best agent)"""
        if agent_name:
            tid = self.db.create_task(description, agent_name, priority)
            return {"task_id": tid, "agent": agent_name, "status": "pending"}
        # Auto-select: find agent with matching capabilities
        agents = self.db.list_agents()
        best = None
        best_score = -1
        for a in agents:
            caps = json.loads(a["capabilities"])
            score = sum(1 for c in caps if c.lower() in description.lower())
            if score > best_score and a["status"] != "busy":
                best = a
                best_score = score
        if not best:
            return {"error": "No available agents found"}
        tid = self.db.create_task(description, best["id"], priority)
        return {"task_id": tid, "agent": best["name"], "status": "pending"}

    def complete_task(self, task_id, result="", error=""):
        self.db.complete_task(task_id, result, error)
        return f"Task {task_id} {'completed' if not error else 'failed'}"

    def task_status(self, task_id):
        c = self.db.db.cursor()
        c.execute("""SELECT t.*, a.name as agent_name FROM tasks t
                      LEFT JOIN agents a ON t.agent_id = a.id
                      WHERE t.id=?""", (task_id,))
        row = c.fetchone()
        if not row:
            return f"Task {task_id} not found"
        task = dict(row)
        return (f"Task: {task['description'][:80]}\n"
                f"  Status: {task['status']}\n"
                f"  Agent: {task.get('agent_name', 'unassigned')}\n"
                f"  Priority: {task['priority']}\n"
                f"  Created: {task['created']}\n"
                f"  Cost: {task['credits_cost']} credits")

    def list_tasks(self, status="pending", limit=10):
        tasks = self.db.get_pending_tasks(limit=limit)
        if not tasks:
            return f"No {status} tasks"
        lines = [f"Tasks ({status}):"]
        for t in tasks:
            lines.append(f"  [{t['id'][:8]}] {t['description'][:60]} — priority {t['priority']}")
        return "\n".join(lines)

    # ── Economy ──

    def get_balance(self, agent_name):
        agents = self.db.list_agents()
        for a in agents:
            if a["name"] == agent_name:
                return f"{agent_name} balance: {a['credits']} credits"
        return f"Agent '{agent_name}' not found"

    def transfer_credits(self, from_agent, to_agent, amount, reason=""):
        ok, msg = self.db.transfer_credits(from_agent, to_agent, amount, reason)
        return msg

    def economy_report(self):
        ledger = self.db.get_economy(10)
        agents = self.db.list_agents()
        lines = ["Agent Economy:"]
        for a in agents:
            lines.append(f"  {a['name']}: {a['credits']} credits ({a['completed_tasks']} tasks)")
        if ledger:
            lines.append("\nRecent transactions:")
            for e in ledger[:5]:
                lines.append(f"  {e['from_agent']} -> {e['to_agent']}: {e['amount']} ({e['reason']})")
        return "\n".join(lines)

    # ── Communication Bus ──

    def send_message(self, to_agent, subject, body="", from_agent="jarvis"):
        self.db.send_message(from_agent, to_agent, subject, body)
        return f"Message sent to {to_agent}"

    def read_messages(self, agent_name, unread_only=True):
        msgs = self.db.get_messages(agent_name, unread_only=unread_only, limit=10)
        if not msgs:
            return f"No messages for {agent_name}"
        lines = [f"Messages for {agent_name}:"]
        for m in msgs:
            icon = "📩" if not m["read"] else "📨"
            lines.append(f"  {icon} [{m['id']}] {m['subject']} — from {m['from_agent']} ({m['timestamp']})")
        return "\n".join(lines)

    def broadcast(self, subject, body=""):
        agents = self.db.list_agents()
        for a in agents:
            self.db.send_message("jarvis", a["name"], subject, body)
        return f"Broadcast sent to {len(agents)} agents"

    # ── Orchestration ──

    def orchestrate(self, high_level_task):
        """Break down a high-level task and delegate to multiple agents"""
        from jarvis_tools import TOOLS_SCHEMA
        agents = self.db.list_agents()
        if not agents:
            return "No agents available for orchestration"
        lines = [f"Pantheon orchestrating: {high_level_task}"]
        lines.append(f"  Using {len(agents)} agents")
        for a in agents:
            tid = self.db.create_task(f"Sub-task: {high_level_task}", a["id"])
            lines.append(f"  Delegated to {a['name']}: task {tid[:8]}")
        return "\n".join(lines)

pantheon = Pantheon()
