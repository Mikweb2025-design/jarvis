"""jarvis_gitnexus.py — GitNexus Knowledge Graph Integration (zero-server code intelligence)"""
import json, os, subprocess, time, threading
from pathlib import Path
from typing import Optional

GITNEXUS_BIN = None
_GITNEXUS_AVAILABLE = False
_GITNEXUS_LOCK = threading.Lock()

def _find_gitnexus():
    global GITNEXUS_BIN, _GITNEXUS_AVAILABLE
    candidates = [
        "npx",  # Try npx first (most reliable across Node versions)
        "gitnexus",
        os.path.expanduser("~/.cargo/bin/gitnexus"),
        os.path.expanduser("~/.local/bin/gitnexus"),
        "/usr/local/bin/gitnexus",
    ]
    for c in candidates:
        if c == "npx":
            try:
                r = subprocess.run(["npx", "gitnexus", "--version"],
                    capture_output=True, text=True, timeout=10)
                if r.returncode == 0 and r.stdout.strip():
                    GITNEXUS_BIN = ("npx", "gitnexus")
                    _GITNEXUS_AVAILABLE = True
                    return True
            except:
                continue
        elif c and os.path.isfile(c) and os.access(c, os.X_OK):
            GITNEXUS_BIN = c
            _GITNEXUS_AVAILABLE = True
            return True
    _GITNEXUS_AVAILABLE = False
    return False

_find_gitnexus()

REPO_PATH = Path(__file__).parent

def _run_gitnexus(args: list, timeout: int = 30, cwd: Optional[str] = None):
    if not _GITNEXUS_AVAILABLE:
        return {"error": "GitNexus CLI not found. Install: npx gitnexus analyze"}
    try:
        cmd = [*GITNEXUS_BIN, *args] if isinstance(GITNEXUS_BIN, tuple) else [GITNEXUS_BIN, *args]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout,
            cwd=cwd or str(REPO_PATH),
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        return {
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"error": "GitNexus command timed out", "success": False}
    except FileNotFoundError:
        _find_gitnexus()
        return {"error": "GitNexus CLI not found", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}

def analyze_repo(path: Optional[str] = None) -> dict:
    target = path or str(REPO_PATH)
    if not _GITNEXUS_AVAILABLE:
        return _fallback_analysis(target)
    result = _run_gitnexus(["status"], timeout=15, cwd=target)
    if result.get("success"):
        stdout = result.get("stdout", "")
        indexed = "up-to-date" in stdout or "Indexed" in stdout
        return {
            "gitnexus_enabled": True,
            "indexed": indexed,
            "raw_status": stdout,
            "repo_path": target,
        }
    return _fallback_analysis(target)

def build_knowledge_graph(path: Optional[str] = None) -> dict:
    target = path or str(REPO_PATH)
    if not _GITNEXUS_AVAILABLE:
        return _fallback_graph(target)
    result = _run_gitnexus(["list"], timeout=15)
    if result.get("success"):
        return {"raw": result["stdout"], "gitnexus_enabled": True}
    return _fallback_graph(target)

def get_symbols(path: Optional[str] = None) -> dict:
    target = path or str(REPO_PATH)
    if not _GITNEXUS_AVAILABLE:
        return _fallback_symbols(target)
    result = _run_gitnexus(["query", "symbols", "--content", "--limit", "50"], timeout=30)
    if result.get("success"):
        return {"raw": result["stdout"], "success": True, "gitnexus_enabled": True}
    return _fallback_symbols(target)

def search_code(query: str, path: Optional[str] = None) -> dict:
    target = path or str(REPO_PATH)
    if not _GITNEXUS_AVAILABLE:
        return _fallback_search(query, target)
    result = _run_gitnexus(["query", query, "--limit", "20", "--content"], timeout=30)
    if result.get("success"):
        return {"raw": result["stdout"], "success": True, "gitnexus_enabled": True}
    return _fallback_search(query, target)

def get_status() -> dict:
    _find_gitnexus()
    return {
        "gitnexus_available": _GITNEXUS_AVAILABLE,
        "gitnexus_bin": GITNEXUS_BIN,
        "repo_path": str(REPO_PATH),
    }

def _fallback_analysis(target: str) -> dict:
    """Fallback: analyze repo structure using basic git + file tree."""
    try:
        result = {
            "repo_path": target,
            "gitnexus_available": False,
            "files": [],
            "languages": {},
            "total_files": 0,
            "total_lines": 0,
        }
        repo = Path(target)
        if not (repo / ".git").exists():
            return {**result, "error": "Not a git repository"}
        for f in repo.rglob("*"):
            if f.is_file() and not any(p.startswith(".") for p in f.relative_to(repo).parts):
                ext = f.suffix.lower()
                result["languages"][ext] = result["languages"].get(ext, 0) + 1
                result["total_files"] += 1
                try:
                    lines = len(f.read_text().splitlines()) if f.stat().st_size < 100000 else 0
                    result["total_lines"] += lines
                except:
                    pass
        return result
    except Exception as e:
        return {"error": str(e), "repo_path": target, "gitnexus_available": False}

def _fallback_graph(target: str) -> dict:
    return {
        "repo_path": target,
        "gitnexus_available": False,
        "note": "Install GitNexus for full knowledge graph. cargo install gitnexus",
        "fallback": _fallback_analysis(target),
    }

def _fallback_symbols(target: str) -> dict:
    symbols = {"functions": [], "classes": [], "imports": []}
    try:
        repo = Path(target)
        import re
        for f in repo.rglob("*.py"):
            if f.stat().st_size > 50000:
                continue
            try:
                content = f.read_text()
                symbols["imports"].extend(
                    re.findall(r"^import\s+(\S+)|^from\s+(\S+)\s+import", content, re.MULTILINE)
                )
                symbols["functions"].extend(
                    [{"name": m.group(1), "file": str(f.relative_to(repo))}
                     for m in re.finditer(r"^def\s+(\w+)\s*\(", content, re.MULTILINE)]
                )
                symbols["classes"].extend(
                    [{"name": m.group(1), "file": str(f.relative_to(repo))}
                     for m in re.finditer(r"^class\s+(\w+)\s*[:(]", content, re.MULTILINE)]
                )
            except:
                pass
        symbols["total_functions"] = len(symbols["functions"])
        symbols["total_classes"] = len(symbols["classes"])
    except:
        pass
    return {"symbols": symbols, "gitnexus_available": False}

def _fallback_search(query: str, target: str) -> dict:
    results = []
    try:
        repo = Path(target)
        for f in repo.rglob("*.py"):
            if f.stat().st_size > 100000:
                continue
            try:
                for i, line in enumerate(f.read_text().splitlines(), 1):
                    if query.lower() in line.lower():
                        results.append({
                            "file": str(f.relative_to(repo)),
                            "line": i,
                            "content": line.strip(),
                        })
            except:
                pass
        return {"results": results[:50], "total": len(results), "gitnexus_available": False}
    except Exception as e:
        return {"error": str(e), "gitnexus_available": False}
