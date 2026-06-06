#!/usr/bin/env python3
"""jarvis_mcp.py — MCP (Model Context Protocol) Client v1.0
Ispirato a isair/jarvis (MCP integration con Home Assistant, GitHub, Slack, ecc.)
Permette di connettere Jarvis a server MCP esterni per estendere le capacità:
GitHub, Slack, Discord, Notion, Home Assistant, database, ecc."""
import json, subprocess, os, sys
from pathlib import Path

MCP_CONFIG_FILE = Path(__file__).parent / "data" / "mcp_servers.json"

BUILTIN_SERVERS = {
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "description": "GitHub: issues, PRs, reviews, code search",
        "enabled": False,
        "env": {},
    },
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", str(Path.home())],
        "description": "Filesystem: accesso controllato ai file",
        "enabled": False,
        "env": {},
    },
    "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "description": "Slack: messaggi, canali, ricerca",
        "enabled": False,
        "env": {},
    },
}

def _ensure():
    MCP_CONFIG_FILE.parent.mkdir(exist_ok=True)

def _load():
    _ensure()
    if MCP_CONFIG_FILE.exists():
        with open(MCP_CONFIG_FILE) as f:
            data = json.load(f)
        for k, v in BUILTIN_SERVERS.items():
            if k not in data:
                data[k] = v
        return data
    _save(BUILTIN_SERVERS)
    return BUILTIN_SERVERS.copy()

def _save(data):
    _ensure()
    with open(MCP_CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def list_servers():
    data = _load()
    result = []
    for name, cfg in data.items():
        status = "✅ attivo" if cfg.get("enabled") else "⬇ spento"
        desc = cfg.get("description", name)
        has_env = " 🔑" if cfg.get("env") else ""
        result.append(f"  {status} {name}{has_env}: {desc}")
    return "\n".join(result) if result else "  Nessun server MCP configurato"

def enable_server(name, env_vars=None):
    data = _load()
    if name not in data:
        available = ", ".join(data.keys())
        return f"Server MCP '{name}' non trovato. Disponibili: {available}"
    data[name]["enabled"] = True
    if env_vars:
        data[name]["env"].update(env_vars)
    _save(data)
    return f"✅ Server MCP '{name}' attivato"

def disable_server(name):
    data = _load()
    if name not in data:
        return f"Server MCP '{name}' non trovato"
    data[name]["enabled"] = False
    _save(data)
    return f"Server MCP '{name}' disattivato"

def add_server(name, command, args=None, description="", env=None):
    data = _load()
    data[name] = {
        "command": command,
        "args": args or [],
        "description": description or name,
        "enabled": True,
        "env": env or {},
    }
    _save(data)
    return f"✅ Server MCP '{name}' aggiunto (comando: {command})"

def remove_server(name):
    data = _load()
    if name not in data:
        return f"Server MCP '{name}' non trovato"
    if name in BUILTIN_SERVERS:
        return f"Impossibile rimuovere server built-in '{name}' (usa disable)"
    desc = data.pop(name, {}).get("description", name)
    _save(data)
    return f"Server MCP '{desc}' rimosso"

def call_tool(server_name, tool_name, arguments=None):
    """Chiama un tool su un server MCP via stdio JSON-RPC"""
    data = _load()
    cfg = data.get(server_name)
    if not cfg:
        return f"Server MCP '{server_name}' non trovato"
    if not cfg.get("enabled"):
        return f"Server MCP '{server_name}' non attivo (usa enable)"
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {},
        },
    }
    
    try:
        env = os.environ.copy()
        env.update(cfg.get("env", {}))
        proc = subprocess.run(
            [cfg["command"]] + cfg.get("args", []),
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if proc.returncode == 0:
            try:
                result = json.loads(proc.stdout)
                if "result" in result:
                    content = result["result"].get("content", [])
                    return "\n".join(c.get("text", "") for c in content if "text" in c)
                return json.dumps(result, indent=2)
            except json.JSONDecodeError:
                return proc.stdout[:2000] or "Eseguito (nessun output)"
        return f"Errore MCP ({proc.returncode}): {proc.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return f"Timeout: server MCP '{server_name}' non risponde (30s)"
    except FileNotFoundError:
        return f"Comando '{cfg['command']}' non trovato. Installa le dipendenze necessarie."
    except Exception as e:
        return f"Errore MCP '{server_name}': {e}"

def list_tools(server_name):
    """Elenca i tools disponibili su un server MCP"""
    data = _load()
    cfg = data.get(server_name)
    if not cfg:
        return f"Server MCP '{server_name}' non trovato"
    if not cfg.get("enabled"):
        return f"Server MCP '{server_name}' non attivo"
    
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    
    try:
        env = os.environ.copy()
        env.update(cfg.get("env", {}))
        proc = subprocess.run(
            [cfg["command"]] + cfg.get("args", []),
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        if proc.returncode == 0:
            try:
                result = json.loads(proc.stdout)
                tools = result.get("result", {}).get("tools", [])
                if not tools:
                    return f"Nessun tool trovato su '{server_name}'"
                lines = [f"Tool disponibili su {server_name}:"]
                for t in tools:
                    desc = t.get("description", "")
                    lines.append(f"  🔧 {t['name']}: {desc[:100]}")
                return "\n".join(lines)
            except json.JSONDecodeError:
                return proc.stdout[:2000]
        return f"Errore ({proc.returncode}): {proc.stderr[:500]}"
    except Exception as e:
        return f"Errore: {e}"
