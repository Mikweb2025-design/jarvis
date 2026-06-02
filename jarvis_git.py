#!/usr/bin/env python3
"""jarvis_git.py — Git integration per JARVIS"""
import subprocess, os
from pathlib import Path

def _run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return (r.stdout + r.stderr).strip()

def _detect_repo():
    """Trova la root del repo git più vicina"""
    p = Path.cwd()
    while p != p.parent:
        if (p / ".git").exists():
            return str(p)
        p = p.parent
    return None

def git_status(path=None):
    repo = path or _detect_repo()
    if not repo:
        return "⚠ Nessun repository git trovato"
    branch = _run("git branch --show-current", cwd=repo)
    status = _run("git status --short", cwd=repo)
    if not status:
        return f"✅ Repo: {repo}\n📍 Branch: {branch}\n🟢 Working tree pulita"
    lines = status.split("\n")
    added = sum(1 for l in lines if l.startswith("A ") or l.startswith("M "))
    deleted = sum(1 for l in lines if l.startswith("D "))
    untracked = sum(1 for l in lines if l.startswith("??"))
    return f"📍 Repo: {repo}\n🔀 Branch: {branch}\n📝 Modificati: {added} | 🗑 Eliminati: {deleted} | ❓ Nuovi: {untracked}\n\n{status[:500]}"

def git_branches(path=None):
    repo = path or _detect_repo()
    if not repo: return "⚠ Nessun repo git"
    branches = _run("git branch -a", cwd=repo)
    current = _run("git branch --show-current", cwd=repo)
    return f"🔀 Branch corrente: {current}\n\n{branches[:500]}"

def git_log(path=None, count=10):
    repo = path or _detect_repo()
    if not repo: return "⚠ Nessun repo git"
    log = _run(f'git log --oneline -{count} --pretty=format:"%h %s (%ar)"', cwd=repo)
    return f"📋 Ultimi {count} commit:\n\n{log}"

def git_execute(command, path=None):
    """Esegue un comando git arbitrario"""
    repo = path or _detect_repo()
    if not repo: return "⚠ Nessun repo git"
    BLOCKED = ["rm -rf","push --force","reset --hard HEAD"]
    for b in BLOCKED:
        if b in command.lower():
            return f"⛔ Comando bloccato per sicurezza: '{b}'"
    result = _run(f"git {command}", cwd=repo)
    return f"✅ git {command}\n\n{result[:1000]}" if result else f"✅ git {command} — ok"

def git_diff(path=None):
    repo = path or _detect_repo()
    if not repo: return "⚠ Nessun repo git"
    diff = _run("git diff --stat", cwd=repo)
    return f"📊 Diff stat:\n\n{diff[:500]}" if diff else "🟢 Nessuna modifica"

def git_create_branch(name, path=None):
    repo = path or _detect_repo()
    if not repo: return "⚠ Nessun repo git"
    _run(f"git checkout -b {name}", cwd=repo)
    return f"✅ Branch '{name}' creato e attivato"

def git_commit(message, path=None):
    repo = path or _detect_repo()
    if not repo: return "⚠ Nessun repo git"
    _run("git add -A", cwd=repo)
    result = _run(f'git commit -m "{message}"', cwd=repo)
    return f"✅ Commit: {message}\n{result[:200]}"
