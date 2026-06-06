#!/usr/bin/env python3
"""jarvis_goals.py — Goal/OKR Tracking System v1.0
Ispirato a vierisid/jarvis (OKR goal pursuit) e Ramsbaby/jarvis (insight layer)
Permette di creare obiettivi con Key Results misurabili e tracciare progressi."""
import json, os
from pathlib import Path
from datetime import datetime, timedelta

DATA_FILE = Path(__file__).parent / "data" / "goals.json"

def _ensure():
    DATA_FILE.parent.mkdir(exist_ok=True)

def _load():
    _ensure()
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []

def _save(goals):
    _ensure()
    with open(DATA_FILE, "w") as f:
        json.dump(goals, f, indent=2)

def create_goal(title, description="", key_results=None, deadline=None, priority="medium"):
    goals = _load()
    goal = {
        "id": len(goals) + 1,
        "title": title,
        "description": description,
        "key_results": [],
        "progress": 0,
        "priority": priority,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "deadline": deadline,
        "updated_at": datetime.now().isoformat(),
    }
    if key_results:
        for i, kr in enumerate(key_results):
            goal["key_results"].append({
                "id": i + 1,
                "description": kr if isinstance(kr, str) else kr.get("description", ""),
                "target": kr.get("target", 100) if isinstance(kr, dict) else 100,
                "current": kr.get("current", 0) if isinstance(kr, dict) else 0,
                "unit": kr.get("unit", "%") if isinstance(kr, dict) else "%",
            })
    goals.append(goal)
    _save(goals)
    return f"Obiettivo creato: '{title}' con {len(goal['key_results'])} key results"

def list_goals(status=None):
    goals = _load()
    if status:
        goals = [g for g in goals if g["status"] == status]
    if not goals:
        return "Nessun obiettivo trovato" if not status else f"Nessun obiettivo con stato '{status}'"
    result = []
    for g in goals:
        kr_done = sum(1 for kr in g["key_results"] if kr["current"] >= kr["target"])
        kr_total = len(g["key_results"])
        result.append(f"{'🎯' if g['status']=='active' else '✅' if g['status']=='completed' else '❌'} {g['title']} [{g['priority']}] — {g['progress']}% ({kr_done}/{kr_total} KR)")
    return "\n".join(result)

def update_key_result(goal_id, kr_id, current_value):
    goals = _load()
    for g in goals:
        if g["id"] == goal_id:
            for kr in g["key_results"]:
                if kr["id"] == kr_id:
                    kr["current"] = min(current_value, kr["target"])
                    g["updated_at"] = datetime.now().isoformat()
                    done = sum(1 for k in g["key_results"] if k["current"] >= k["target"])
                    g["progress"] = int(done / len(g["key_results"]) * 100) if g["key_results"] else 0
                    if g["progress"] >= 100:
                        g["status"] = "completed"
                    _save(goals)
                    return f"KR '{kr['description']}' aggiornato a {kr['current']}{kr['unit']} (target: {kr['target']}{kr['unit']})"
            return f"KR {kr_id} non trovato"
    return f"Obiettivo {goal_id} non trovato"

def add_key_result(goal_id, description, target=100, unit="%"):
    goals = _load()
    for g in goals:
        if g["id"] == goal_id:
            nid = max((kr["id"] for kr in g["key_results"]), default=0) + 1
            g["key_results"].append({"id": nid, "description": description, "target": target, "current": 0, "unit": unit})
            g["updated_at"] = datetime.now().isoformat()
            _save(goals)
            return f"KR aggiunto: '{description}' (target: {target}{unit})"
    return f"Obiettivo {goal_id} non trovato"

def get_goal_detail(goal_id):
    goals = _load()
    for g in goals:
        if g["id"] == goal_id:
            lines = [f"{'🎯' if g['status']=='active' else '✅'} {g['title']}"]
            if g["description"]:
                lines.append(f"   {g['description']}")
            lines.append(f"   Priorità: {g['priority']} | Progresso: {g['progress']}% | Stato: {g['status']}")
            if g["deadline"]:
                lines.append(f"   Scadenza: {g['deadline']}")
            for kr in g["key_results"]:
                pct = int(kr["current"] / kr["target"] * 100) if kr["target"] else 0
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                lines.append(f"   {bar} {kr['description']}: {kr['current']}/{kr['target']}{kr['unit']}")
            return "\n".join(lines)
    return f"Obiettivo {goal_id} non trovato"

def delete_goal(goal_id):
    goals = _load()
    for i, g in enumerate(goals):
        if g["id"] == goal_id:
            title = g["title"]
            goals.pop(i)
            _save(goals)
            return f"Obiettivo '{title}' eliminato"
    return f"Obiettivo {goal_id} non trovato"

def archive_goal(goal_id):
    goals = _load()
    for g in goals:
        if g["id"] == goal_id:
            g["status"] = "archived"
            g["updated_at"] = datetime.now().isoformat()
            _save(goals)
            return f"Obiettivo '{g['title']}' archiviato"
    return f"Obiettivo {goal_id} non trovato"
