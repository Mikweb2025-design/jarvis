#!/usr/bin/env python3
"""jarvis_files.py — file management avanzato"""
import os, shutil, subprocess
from pathlib import Path
from datetime import datetime

def _run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()

def list_directory(path="~/Desktop", show_hidden=False):
    p = os.path.expanduser(path)
    if not os.path.isdir(p):
        return f"⚠ Directory non trovata: {p}"
    flag = "-a" if show_hidden else ""
    rc, out = _run(f"ls {flag} -la '{p}' | head -50")
    return out if out else "Directory vuota"

def create_file(path, content=""):
    p = os.path.expanduser(path)
    parent = Path(p).parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(p, "w") as f:
            f.write(content)
        return f"✅ File creato: {p}"
    except Exception as e:
        return f"⚠ Errore: {e}"

def create_directory(path):
    p = os.path.expanduser(path)
    try:
        os.makedirs(p, exist_ok=True)
        return f"✅ Directory creata: {p}"
    except Exception as e:
        return f"⚠ Errore: {e}"

def rename_file(old_path, new_path):
    old = os.path.expanduser(old_path)
    new = os.path.expanduser(new_path)
    if not os.path.exists(old):
        return f"⚠ File non trovato: {old}"
    try:
        os.rename(old, new)
        return f"✅ Rinominato: {old} → {new}"
    except Exception as e:
        return f"⚠ Errore: {e}"

def delete_file(path):
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return f"⚠ File non trovato: {p}"
    try:
        if os.path.isdir(p):
            shutil.rmtree(p)
            return f"✅ Directory eliminata: {p}"
        else:
            os.remove(p)
            return f"✅ File eliminato: {p}"
    except Exception as e:
        return f"⚠ Errore: {e}"

def copy_file(src, dst):
    s = os.path.expanduser(src)
    d = os.path.expanduser(dst)
    if not os.path.exists(s):
        return f"⚠ File non trovato: {s}"
    try:
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
        return f"✅ Copiato: {s} → {d}"
    except Exception as e:
        return f"⚠ Errore: {e}"

def move_file(src, dst):
    s = os.path.expanduser(src)
    d = os.path.expanduser(dst)
    if not os.path.exists(s):
        return f"⚠ File non trovato: {s}"
    try:
        shutil.move(s, d)
        return f"✅ Spostato: {s} → {d}"
    except Exception as e:
        return f"⚠ Errore: {e}"

def read_file(path, max_lines=100):
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return f"⚠ File non trovato: {p}"
    try:
        with open(p) as f:
            lines = f.readlines()[:max_lines]
        content = "".join(lines)
        total = len(open(p).readlines())
        suffix = f"\n... ({total - max_lines} righe in più)" if total > max_lines else ""
        return f"📄 {p} ({total} righe)\n{content}{suffix}"
    except Exception as e:
        return f"⚠ Errore lettura: {e}"

def search_files(query, path="~", type_filter=None):
    p = os.path.expanduser(path)
    name_flag = f"-name '*{query}*'"
    type_flag = f"-type f" if type_filter == "file" else f"-type d" if type_filter == "dir" else ""
    cmd = f"find '{p}' {type_flag} {name_flag} 2>/dev/null | head -30"
    rc, out = _run(cmd)
    if not out:
        return f"🔍 Nessun risultato per '{query}'"
    files = out.strip().split("\n")
    return f"🔍 Trovati {len(files)} risultati:\n" + "\n".join(f"  {f}" for f in files[:30])

def get_file_info(path):
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return f"⚠ File non trovato: {p}"
    stat = os.stat(p)
    size = stat.st_size
    if size > 1024*1024:
        size_str = f"{size/1024/1024:.1f} MB"
    elif size > 1024:
        size_str = f"{size/1024:.1f} KB"
    else:
        size_str = f"{size} B"
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
    return f"📄 {os.path.basename(p)}\n   Path: {p}\n   Size: {size_str}\n   Modificato: {mtime}\n   Tipo: {'Directory' if os.path.isdir(p) else 'File'}"

def organize_downloads():
    """Organizza la cartella Downloads per tipo di file"""
    dl = os.path.expanduser("~/Downloads")
    categories = {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp"],
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".pages", ".odt"],
        "Archives": [".zip", ".tar", ".gz", ".rar", ".7z", ".dmg"],
        "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".md"],
        "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
        "Video": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
    }
    moved = 0
    for f in os.listdir(dl):
        fp = os.path.join(dl, f)
        if not os.path.isfile(fp):
            continue
        ext = os.path.splitext(f)[1].lower()
        for cat, exts in categories.items():
            if ext in exts:
                dest = os.path.join(dl, cat)
                os.makedirs(dest, exist_ok=True)
                shutil.move(fp, os.path.join(dest, f))
                moved += 1
                break
    return f"✅ Organizzati {moved} file in ~/Downloads"
