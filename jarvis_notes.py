#!/usr/bin/env python3
"""jarvis_notes.py — integrazione Apple Notes via AppleScript"""
import subprocess

def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() or r.stderr.strip()

def create_note(title, body="", folder=""):
    folder_clause = f'folder "{folder}"' if folder else ""
    body_clause = f', body:"{body}"' if body else ""
    script = f'''
    tell application "Notes"
        tell account "iCloud" {folder_clause}
            make new note with properties {{name:"{title}"{body_clause}}}
        end tell
    end tell
    '''
    _osa(script)
    return f"✅ Nota creata: '{title}'"

def search_notes(query, limit=5):
    script = f'''
    set noteList to ""
    tell application "Notes"
        set foundNotes to (notes of account "iCloud" whose name contains "{query}" or body contains "{query}")
        set countNotes to count of foundNotes
        if countNotes > {limit} then set countNotes to {limit}
        repeat with i from 1 to countNotes
            set n to item i of foundNotes
            set noteList to noteList & (name of n) & "|" & (plaintext of n) & "\\n---\\n"
        end repeat
    end tell
    return noteList
    '''
    result = _osa(script)
    if not result:
        return f"📝 Nessuna nota per: '{query}'"
    notes = []
    for block in result.strip().split("---"):
        block = block.strip()
        if "|" in block:
            parts = block.split("|", 1)
            notes.append({"title": parts[0], "body": parts[1][:200] if len(parts) > 1 else ""})
    if not notes:
        return f"📝 Nessuna nota per: '{query}'"
    return "\n".join(f"📝 {n['title']}\n   {n['body'][:150]}..." for n in notes[:limit])

def list_notes(limit=10):
    script = f'''
    set noteList to ""
    tell application "Notes"
        set allNotes to notes of account "iCloud"
        set countNotes to count of allNotes
        if countNotes > {limit} then set countNotes to {limit}
        repeat with i from 1 to countNotes
            set n to item i of allNotes
            set noteList to noteList & (name of n) & "\\n"
        end repeat
    end tell
    return noteList
    '''
    result = _osa(script)
    notes = [n.strip() for n in result.strip().split("\n") if n.strip()]
    if not notes:
        return "📝 Nessuna nota"
    return "\n".join(f"📝 {n}" for n in notes[:limit])

def read_note(title):
    script = f'''
    tell application "Notes"
        set foundNotes to (notes of account "iCloud" whose name is "{title}")
        if count of foundNotes > 0 then
            return plaintext of item 1 of foundNotes
        else
            return "NOT FOUND"
        end if
    end tell
    '''
    result = _osa(script)
    if result == "NOT FOUND":
        return f"📝 Nota '{title}' non trovata"
    return f"📝 {title}\n{result[:500]}"
