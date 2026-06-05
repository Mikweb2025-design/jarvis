"""jarvis_homeassistant.py — Home Assistant REST API integration"""
import os, json, requests
from functools import lru_cache

HA_URL = os.environ.get("HA_URL", "http://mikweb.info:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJlMGYzZjA2NGRlNTQ0YjI5YWUzZDJmNjg4MWU1YTAzYiIsImlhdCI6MTc4MDYzODIzMCwiZXhwIjoyMDk1OTk4MjMwfQ.pZxxgqKxYQd00qe4UJQ0VQ27VcKD4QWfPUXxJ8waCSs")

def _headers():
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }

def _get(path):
    try:
        r = requests.get(f"{HA_URL}{path}", headers=_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": f"Impossibile connettersi a {HA_URL}. Home Assistant è in esecuzione?"}
    except Exception as e:
        return {"error": str(e)}

def _post(path, data=None):
    try:
        r = requests.post(f"{HA_URL}{path}", headers=_headers(), json=data or {}, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": f"Impossibile connettersi a {HA_URL}"}
    except Exception as e:
        return {"error": str(e)}

def ha_get_config():
    return _get("/api/config")

def ha_get_states():
    return _get("/api/states")

def ha_get_state(entity_id):
    data = _get(f"/api/states/{entity_id}")
    if isinstance(data, dict) and "error" in data:
        return data
    return {
        "entity_id": data.get("entity_id"),
        "state": data.get("state"),
        "attributes": data.get("attributes", {}),
        "last_changed": data.get("last_changed"),
        "last_updated": data.get("last_updated"),
    }

def ha_call_service(domain, service, data=None):
    return _post(f"/api/services/{domain}/{service}", data or {})

def ha_fire_event(event_type, data=None):
    return _post(f"/api/events/{event_type}", data or {})

def ha_get_services():
    return _get("/api/services")

def ha_get_history(entity_id=None):
    path = "/api/history/period"
    if entity_id:
        path += f"?filter_entity_id={entity_id}"
    return _get(path)

def ha_get_logbook(entity_id=None):
    path = "/api/logbook"
    if entity_id:
        path += f"?entity={entity_id}"
    return _get(path)
