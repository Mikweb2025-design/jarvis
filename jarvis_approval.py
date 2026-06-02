#!/usr/bin/env python3
"""jarvis_approval.py — approval flow per azioni importanti v1.0
Ispirato a manikv12/OpenAssist e novynlabs-repo/Jarvey"""
import json, time, threading
from pathlib import Path
from datetime import datetime

APPROVAL_STATE_FILE = Path(__file__).parent / "data" / "approval_state.json"

class ApprovalManager:
    """Gestisce richieste di approvazione per azioni sensibili"""
    
    def __init__(self):
        self._pending = {}
        self._lock = threading.Lock()
        self._callbacks = {}
        self._auto_approve = set()
        self._load_state()
    
    def _load_state(self):
        if APPROVAL_STATE_FILE.exists():
            try:
                with open(APPROVAL_STATE_FILE) as f:
                    state = json.load(f)
                    self._auto_approve = set(state.get("auto_approve", []))
            except:
                pass
    
    def _save_state(self):
        APPROVAL_STATE_FILE.parent.mkdir(exist_ok=True)
        with open(APPROVAL_STATE_FILE, "w") as f:
            json.dump({"auto_approve": list(self._auto_approve)}, f, indent=2)
    
    def needs_approval(self, action: str, tool: str) -> bool:
        """Determina se un'azione richiede approvazione"""
        if tool in self._auto_approve:
            return False
        
        sensitive_actions = {
            "files_delete", "files_move", "run_terminal_command",
            "lock_screen", "quit_app", "keyboard_shortcut",
            "computer_use", "browser_automation"
        }
        
        high_risk_patterns = ["delete", "remove", "kill", "shutdown", "restart", "format", "rm -rf"]
        
        if tool in sensitive_actions:
            return True
        
        action_lower = action.lower()
        if any(pattern in action_lower for pattern in high_risk_patterns):
            return True
        
        return False
    
    def request_approval(self, action: str, tool: str, details: str = "", timeout=30) -> dict:
        """Richiede approvazione per un'azione"""
        request_id = f"{int(time.time())}_{tool}"
        
        request = {
            "id": request_id,
            "action": action,
            "tool": tool,
            "details": details,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "timeout": timeout
        }
        
        with self._lock:
            self._pending[request_id] = request
        
        return request
    
    def approve(self, request_id: str, auto_future=False) -> bool:
        """Approva una richiesta"""
        with self._lock:
            if request_id in self._pending:
                self._pending[request_id]["status"] = "approved"
                self._pending[request_id]["approved_at"] = datetime.now().isoformat()
                
                if auto_future:
                    tool = self._pending[request_id]["tool"]
                    self._auto_approve.add(tool)
                    self._save_state()
                return True
        return False
    
    def deny(self, request_id: str) -> bool:
        """Nega una richiesta"""
        with self._lock:
            if request_id in self._pending:
                self._pending[request_id]["status"] = "denied"
                self._pending[request_id]["denied_at"] = datetime.now().isoformat()
                return True
        return False
    
    def check_status(self, request_id: str) -> dict:
        """Controlla stato di una richiesta"""
        with self._lock:
            return self._pending.get(request_id, {"status": "not_found"})
    
    def wait_for_approval(self, request_id: str, timeout=30) -> bool:
        """Attende approvazione (blocking)"""
        start = time.time()
        while time.time() - start < timeout:
            status = self.check_status(request_id)
            if status.get("status") == "approved":
                return True
            if status.get("status") == "denied":
                return False
            time.sleep(0.5)
        return False
    
    def get_pending(self) -> list:
        """Lista richieste pending"""
        with self._lock:
            return [r for r in self._pending.values() if r["status"] == "pending"]
    
    def get_all_requests(self, limit=20) -> list:
        """Lista tutte le richieste recenti"""
        with self._lock:
            requests = list(self._pending.values())
            requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return requests[:limit]
    
    def clear_expired(self):
        """Rimuove richieste scadute"""
        with self._lock:
            expired = []
            for rid, req in self._pending.items():
                if req["status"] == "pending":
                    created = datetime.fromisoformat(req["created_at"])
                    age = (datetime.now() - created).total_seconds()
                    if age > req.get("timeout", 30):
                        req["status"] = "expired"
                        expired.append(rid)
            return expired
    
    def set_auto_approve(self, tools: list):
        """Impatta tool che non richiedono approvazione"""
        self._auto_approve.update(tools)
        self._save_state()
    
    def get_auto_approve(self) -> list:
        return list(self._auto_approve)

# Singleton
approval = ApprovalManager()

def check_and_approve(action: str, tool: str, details: str = "", auto_mode=False) -> tuple:
    """Helper: controlla se serve approvazione e la gestisce
    Returns: (approved: bool, request_id: str|None)"""
    if not approval.needs_approval(action, tool):
        return True, None
    
    if auto_mode:
        return True, None
    
    request = approval.request_approval(action, tool, details)
    return False, request["id"]
