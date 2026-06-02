#!/usr/bin/env python3
"""jarvis_planner.py — multi-step task planning"""
import json
from datetime import datetime
from pathlib import Path

PLANS_FILE = Path(__file__).parent / "data" / "plans.json"

def _ensure_data_dir():
    PLANS_FILE.parent.mkdir(exist_ok=True)

def _load_plans():
    _ensure_data_dir()
    if PLANS_FILE.exists():
        with open(PLANS_FILE) as f:
            return json.load(f)
    return []

def _save_plans(plans):
    _ensure_data_dir()
    with open(PLANS_FILE, "w") as f:
        json.dump(plans, f, indent=2)

def create_plan(title, steps, priority="medium"):
    """Crea un piano multi-step"""
    plans = _load_plans()
    plan_id = len(plans) + 1
    plan = {
        "id": plan_id,
        "title": title,
        "steps": [{"step": i+1, "description": s, "done": False} for i, s in enumerate(steps)],
        "priority": priority,
        "created": datetime.now().isoformat(),
        "status": "active"
    }
    plans.append(plan)
    _save_plans(plans)
    return f"✅ Piano creato: '{title}' ({len(steps)} step)"

def get_active_plans():
    """Elenca piani attivi"""
    plans = _load_plans()
    active = [p for p in plans if p["status"] == "active"]
    if not active:
        return "Nessun piano attivo"
    result = []
    for p in active:
        done = sum(1 for s in p["steps"] if s["done"])
        total = len(p["steps"])
        pct = int(done/total*100) if total > 0 else 0
        result.append(f"📋 {p['title']} [{p['priority']}] {done}/{total} step ({pct}%)")
    return "\n".join(result)

def complete_step(plan_id, step_num):
    """Segna uno step come completato"""
    plans = _load_plans()
    for p in plans:
        if p["id"] == plan_id:
            for s in p["steps"]:
                if s["step"] == step_num:
                    s["done"] = True
                    break
            all_done = all(s["done"] for s in p["steps"])
            if all_done:
                p["status"] = "completed"
                p["completed"] = datetime.now().isoformat()
                _save_plans(plans)
                return f"✅ Step {step_num} completato — Piano '{p['title']}' terminato!"
            _save_plans(plans)
            return f"✅ Step {step_num} completato per '{p['title']}'"
    return f"⚠ Piano {plan_id} non trovato"

def delete_plan(plan_id):
    """Elimina un piano"""
    plans = _load_plans()
    plans = [p for p in plans if p["id"] != plan_id]
    _save_plans(plans)
    return f"✅ Piano {plan_id} eliminato"

def get_plan_detail(plan_id):
    """Dettaglio di un piano"""
    plans = _load_plans()
    for p in plans:
        if p["id"] == plan_id:
            status_icon = "✅" if p["status"] == "completed" else "🔄"
            result = f"{status_icon} {p['title']} [{p['priority']}]\n"
            for s in p["steps"]:
                icon = "✅" if s["done"] else "⬜"
                result += f"  {icon} Step {s['step']}: {s['description']}\n"
            return result.strip()
    return f"⚠ Piano {plan_id} non trovato"

def generate_plan_from_query(query):
    """Genera un piano strutturato da una richiesta naturale (l'AI lo chiama)"""
    return {
        "suggestion": f"Piano per: {query}",
        "steps": [
            "Analizza la richiesta",
            "Identifica le azioni necessarie",
            "Esegui le azioni in sequenza",
            "Verifica il risultato"
        ]
    }
